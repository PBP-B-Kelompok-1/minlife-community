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

from .models import Post, Vote, Comment
from .forms import PostForm, CommentForm

# Create your views here.
def frontpage(request):
    return render(request, "posts/frontpage.html")

@require_GET
def show_post(request, post_id):
    context = {
        "post_id": post_id,
        "comment_form": CommentForm()
    }
    return render(request, "posts/show_post.html", context)

# universal method to be used by other views
def get_post(post_id, user):
    post = get_object_or_404(Post, id=post_id)

    tags_data = [{
            "id": str(tag.id),
            "title": tag.title,
        } for tag in post.tags.all()]
    vote_count = post.votes.aggregate(sum=Sum("value"))["sum"] or 0
    user_vote_value = 0
    if user.is_authenticated:
        user_vote = post.votes.filter(user=user).first()
        user_vote_value = user_vote.value if user_vote else 0
    comment_count = post.comments.count()
    data = {
        "id": str(post.id),
        "title": post.title,
        "content": post.content,
        "tags": tags_data,
        "vote_count": vote_count,
        "user_vote_value": user_vote_value,
        "comment_count": comment_count,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }
    return data

@require_GET
def get_post_json(request, post_id):
    post_data = get_post(post_id, request.user)

    payload = {
        "data": post_data,
    }
    return JsonResponse(payload)

@require_GET
def get_posts_json(request):
    # page = request.GET.get("page", "").strip() # TODO: as finishing touches
    post_ids = Post.objects.values_list("id", flat=True)
    data = []
    for post_id in post_ids:
        data.append(get_post(post_id, request.user))
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
        form.save_m2m()
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

# === COMMENTS ===
@require_GET
def get_comments_json(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    comments = Comment.objects.filter(post=post, replies_to_comment__isnull=True)
    payload = {
        "data": get_comments_recursive(comments, request.user)
    }
    return JsonResponse(payload)

def get_comments_recursive(comments, user):
    data = []
    for comment in comments:
        replies = get_comments_recursive(comment.replies.all(), user)
        vote_count = comment.votes.aggregate(sum=Sum("value"))["sum"] or 0
        user_vote_value = 0
        if user.is_authenticated:
            user_vote = comment.votes.filter(user=user).first()
            user_vote_value = user_vote.value if user_vote else 0
        data.append({
            "id": comment.id,
            "username": comment.user.username,
            "content": comment.content,
            "user_vote_value": user_vote_value,
            "replies": replies,
            "vote_count": vote_count,
        })
    return data

@require_POST
def create_comment(request, post_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            data={
                "message": "Please log in first!",
                "login_url": reverse("login"),
            },
            status=401,
        )

    form = CommentForm(request.POST or None)
    
    if not form.is_valid():
        return JsonResponse({
                "message": "Please fill the fields as specified!",
                "errors": form.errors
            }, status=400)
    
    # TODO: reply creation
    post = get_object_or_404(Post, id=post_id)
    comment = form.save(commit=False)
    comment.user = request.user
    comment.post = post
    comment.save()
    return JsonResponse(
        {"message": "Successfully posted comment!"},
        status=201,
    )

@require_POST
def vote_comment(request, comment_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            data={
                "message": "Please log in first!",
                "login_url": reverse("login"),
            },
            status=401,
        )

    comment = get_object_or_404(Comment, pk=comment_id)
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
        vote = Vote.objects.filter(user=request.user, comment=comment).first()
        if not vote:
            Vote.objects.create(user=request.user, comment=comment, value=vote_value)
        elif vote.value != vote_value:
            vote.value = vote_value
            vote.save()
        elif vote.value == vote_value:
            vote_value = 0
            vote.delete()

        vote_count = comment.votes.aggregate(sum=Sum("value"))["sum"] or 0

    return JsonResponse(
        data={
            "message": "Upvoted successfully!",
            "vote_value": vote_value,
            "vote_count": vote_count,
        },
        status=200,
    )


