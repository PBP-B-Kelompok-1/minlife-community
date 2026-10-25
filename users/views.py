from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Follow, User
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout, get_user_model
from .forms import RegisterForm
from django.http import HttpResponse


User = get_user_model()

def show_profile(request, user_id):
    profile_user = get_object_or_404(User, id=user_id)
    social_links = profile_user.sociallink_set.all()  # or your related_name

    context = {
        'profile_user': profile_user,
        'social_links': social_links,
    }
    return render(request, 'users/profile.html', context)
    
@login_required
def show_my_profile(request):
    context = {
        'profile_user': request.user,
        'social_links': request.user.sociallink_set.all(),
        'is_owner': True,
    }
    return render(request, 'users/profile.html', context)

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