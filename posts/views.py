from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.views.decorators.http import require_GET
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Post, Tag
from .forms import PostForm, CommentForm
from announcements.models import Announcement
from weeklychallenge.models import CHALLENGE_TAG_NAME, Challenge

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

@login_required
def create_post(request):
    challenge = None
    challenge_id = request.GET.get("challenge")
    form_data = request.POST or None
    initial = None

    if challenge_id:
        try:
            challenge = Challenge.objects.current().get(pk=challenge_id)
        except (Challenge.DoesNotExist, TypeError, ValueError):
            raise Http404("Active challenge not found.")

        challenge_tag, _ = Tag.objects.get_or_create(title=CHALLENGE_TAG_NAME)
        if request.method == "POST":
            form_data = request.POST.copy()
            selected_tag_ids = form_data.getlist("tags")
            challenge_tag_id = str(challenge_tag.pk)
            if challenge_tag_id not in selected_tag_ids:
                form_data.appendlist("tags", challenge_tag_id)
        else:
            initial = {"tags": [challenge_tag.pk]}

    form = PostForm(form_data, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        form.save_m2m()
        messages.success(request, "Post has been created successfully.")
        if challenge:
            return redirect("weeklychallenge:show_weekly_challenge")
        return redirect("frontpage")
    context = {
        "form": form,
        "challenge": challenge,
        "form_action": request.get_full_path(),
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
