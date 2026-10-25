from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Follow, User
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login, logout
from .forms import RegisterForm
from django.http import HttpResponse

def show_profile(request, user_id):
    # TODO
    user = get_object_or_404(User, pk=user_id)
    return HttpResponse(f"Profile of {user.username}")
    
@login_required
def show_my_profile(request):
    # TODO
    return HttpResponse(f"Logged in as {request.user.username}")

def login_user(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect("users:show_my_profile") # TODO: Change to posts landing page once the url is set

    return render(request, "login.html", {"form": form})

@require_POST
def logout_user(request):
    logout(request)
    return redirect("users:login") # TODO: Change to posts landing page

def register_user(request):
    form = RegisterForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Account successfully made! Please login")
        return redirect("users:login")

    return render(request, "register.html", {"form": form})

# TODO: Update profile

# TODO: Delete user ??

@login_required
@require_POST
def toggle_follow(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        return HttpResponseBadRequest("You cannot follow yourself.")

    link, created = Follow.objects.get_or_create(
        follower=request.user, following=target
    )
    if not created:          # already following → this click means unfollow
        link.delete()

    return redirect("users:show_profile", user_id=target.id)