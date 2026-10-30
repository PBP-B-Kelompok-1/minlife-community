import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.urls import reverse

from .models import Post, Vote, Comment
from .forms import PostForm, CommentForm
from announcements.models import Announcement
from weeklychallenge.services import award_badge_if_eligible

# Create your views here.
def frontpage(request):
    return render(
        request,
        "posts/frontpage.html",
        {"latest_announcement": Announcement.objects.first()},
    )

@require_GET
def show_post(request, post_id):
    context = {
        "post_id": post_id,
        "comment_form": CommentForm(),
        # This is kept in a template and copied for each reply button press.
        # A different starting ID keeps it separate from the main comment editor.
        "reply_comment_form": CommentForm(auto_id="id_reply_%s"),
    }
    return render(request, "posts/show_post.html", context)

# universal method to be used by other views
def get_post(post_id, user):
    post = get_object_or_404(Post, id=post_id)

    tags_data = [{
            "id": str(tag.id),
            "title": tag.title,
        } for tag in post.tags.all()]
    user_vote_value = post.get_user_vote_value(user);
    comment_count = post.comments.count()
    challenge_image_url = post.challenge_image.url if post.challenge_image else None
    data = {
        "id": str(post.id),
        "user_id": post.author.id,
        "username": post.author.username,
        "avatar_url": post.author.avatar_url,
        "title": post.title,
        "challenge_image_url": challenge_image_url,
        "content": post.content,
        "tags": tags_data,
        "vote_count": post.get_vote_count(),
        "user_vote_value": user_vote_value,
        "comment_count": comment_count,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
        "can_update": user.is_authenticated and (
            user == post.author or user.has_perm("posts.change_post")
        ),
        "can_delete": user.is_authenticated and (
            user == post.author or user.has_perm("posts.delete_post")
        ),
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
    form = PostForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        form.save_m2m()
        messages.success(request, "Post has been created successfully.")
        return redirect("frontpage")
    context = {
        "form": form
    }
    return render(request, "posts/create_form.html", context)

@login_required
def update_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author and not request.user.has_perm("posts.change_post"):
        raise PermissionDenied
    form = PostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        post = form.save()
        messages.success(request, "Post has been edited successfully.")
        return redirect("posts:show_post", post_id=post.id)
    context = {
        "form": form
    }
    return render(request, "posts/edit_form.html", context)

@require_POST
def delete_post(request, post_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            data={
                "message": "Please log in first!",
                "login_url": reverse("login"),
            },
            status=401,
        )
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author and not request.user.has_perm("posts.delete_post"):
        raise PermissionDenied

    post.delete()
    return JsonResponse({"message": "Post deleted successfully."})

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

    award_badge_if_eligible(post)

    return JsonResponse(
        data={
            "message": "Upvoted successfully!",
            "vote_value": vote_value,
            "vote_count": post.get_vote_count(),
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
        reply_count = 0
        for reply in replies:
            reply_count += 1 + reply["reply_count"]
        user_vote_value = comment.get_user_vote_value(user);
        is_deleted = comment.is_deleted
        data.append({
            "id": comment.id,
            "user_id": None if is_deleted else comment.user.id,
            "username": "[deleted comment]" if is_deleted else comment.user.username,
            "avatar_url": "" if is_deleted else comment.user.avatar_url,
            "content": comment.content,
            "is_deleted": is_deleted,
            "user_vote_value": user_vote_value,
            "replies": replies,
            "reply_count": reply_count,
            "vote_count": comment.get_vote_count(),
            "can_delete": not is_deleted and user.is_authenticated and (
                user == comment.user or user.has_perm("posts.delete_comment")
            ),
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
    
    post = get_object_or_404(Post, id=post_id)
    reply_to_id = request.POST.get("replies_to_comment")
    reply_to = None
    if reply_to_id:
        # Make sure somebody cannot reply to a comment from a different post.
        reply_to = get_object_or_404(Comment, id=reply_to_id, post=post)

    comment = form.save(commit=False)
    comment.user = request.user
    comment.post = post
    comment.replies_to_comment = reply_to
    comment.save()
    return JsonResponse({
        "message": "Successfully posted comment!",
        "comment_id": comment.id
        }, status=201,
    )

@require_POST
def delete_comment(request, comment_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "message": "Please log in first!",
                "login_url": reverse("login"),
            },
            status=401,
        )

    comment = get_object_or_404(Comment, pk=comment_id)
    if request.user != comment.user and not request.user.has_perm("posts.delete_comment"):
        raise PermissionDenied

    comment.content = "✖ This comment has been deleted"
    comment.is_deleted = True
    comment.save(update_fields=["content", "is_deleted"])
    return JsonResponse({"message": "Comment deleted successfully."})

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
    if comment.is_deleted:
        return JsonResponse({"error": "can't vote on a deleted comment"}, status=400)
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

    return JsonResponse(
        data={
            "message": "Upvoted successfully!",
            "vote_value": vote_value,
            "vote_count": comment.get_vote_count(),
        },
        status=200,
    )
