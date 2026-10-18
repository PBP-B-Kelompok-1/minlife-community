from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Post
from .forms import PostForm

# Create your views here.
def frontpage(request):
    context = { "tes": "tes" }
    return render(request, "posts/frontpage.html", context)

def get_posts_json(request):
    page = request.GET.get("page", "").strip() # will this error? bc integer.
    posts = Post.objects.prefetch_related("tags").all()
    data = []
    for post in posts:
        tags_data = [{
                "id": str(tag.id),
                "title": tag.title,
            } for tag in post.tags.all()]
        data += {
            "id": str(post.id),
            "title": post.title,
            "content": post.content,
            "tags": tags_data,
            "created_at": post.created_at,
            "updated_at": post.updated_at,
        }
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