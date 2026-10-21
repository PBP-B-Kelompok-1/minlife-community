import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse

from .models import Post, Vote
from .forms import PostForm

# Create your views here.
def frontpage(request):
    context = { "tes": "tes" }
    return render(request, "posts/frontpage.html", context)

@require_GET
def show_post(request, post_id):
    return

@require_GET
def get_post_json(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    data = []
    tags_data = [{
            "id": str(tag.id),
            "title": tag.title,
        } for tag in post.tags.all()]
    vote_count = post.votes.aggregate(sum=Sum("value"))["sum"] or 0
    user_vote_value = 0
    if request.user.is_authenticated:
        user_vote = post.votes.filter(user=request.user).first()
        user_vote_value = user_vote.value if user_vote else 0
    comment_count = post.comments.count()
    data.append({
        "id": str(post.id),
        "title": post.title,
        "content": post.content,
        "tags": tags_data,
        "vote_count": vote_count,
        "user_vote_value": user_vote_value,
        "comment_count": comment_count,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    })

    payload = {
        "data": data,
    }
    return JsonResponse(payload)

@require_GET
def get_posts_json(request):
    # page = request.GET.get("page", "").strip() # will this error? bc integer.
    posts = Post.objects.prefetch_related("tags").prefetch_related("votes").prefetch_related("comments").all()
    data = []
    for post in posts:
        tags_data = [{
                "id": str(tag.id),
                "title": tag.title,
            } for tag in post.tags.all()]
        vote_count = post.votes.aggregate(sum=Sum("value"))["sum"] or 0
        user_vote_value = 0
        if request.user.is_authenticated:
            user_vote = post.votes.filter(user=request.user).first()
            user_vote_value = user_vote.value if user_vote else 0
        comment_count = post.comments.count()
        data.append({
            "id": str(post.id),
            "title": post.title,
            "content": post.content,
            "tags": tags_data,
            "vote_count": vote_count,
            "user_vote_value": user_vote_value,
            "comment_count": comment_count,
            "created_at": post.created_at,
            "updated_at": post.updated_at,
        })
    payload = {
        "data": data,
    }
    return JsonResponse(payload)

@login_required
def create_post(request):
    form = PostForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        form.save_m2m() # TODO: review (codex's recommendation)
        messages.success(request, "Form has been created successfully.")
        return redirect("frontpage")
    context = {
        "form": form
    }
    return render(request, "posts/create_form.html", context)

@require_POST
def vote_post(request, post_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            data={
                "message": "Please log in first!",
                "login_url": reverse("login"),
            },
            status=401,
        )

    post = get_object_or_404(Post, pk=post_id)
    try:
        payload = json.loads(request.body)
        vote_value = payload["vote_value"]
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "value is required"}, status=400)

    if vote_value not in (1, -1):
        return JsonResponse({"error": "value must be 1 or -1"}, status=400)

    # yes this part was absolutely vibecoded. but thanks codex, now i know about transactions
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        vote = Vote.objects.filter(user=request.user, post=post).first()
        if not vote:
            Vote.objects.create(user=request.user, post=post, value=vote_value)
        elif vote.value != vote_value:
            vote.value = vote_value
            vote.save()
        elif vote.value == vote_value:
            vote_value = 0
            vote.delete()

        vote_count = post.votes.aggregate(sum=Sum("value"))["sum"] or 0

    return JsonResponse(
        data={
            "message": "Upvoted successfully!",
            "vote_value": vote_value,
            "vote_count": vote_count,
        },
        status=200,
    )
