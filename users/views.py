from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Follow, User
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout, get_user_model
from .forms import RegisterForm, UpdateProfileForm
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied


User = get_user_model()

# Profile show

def show_profile(request, user_id):
    profile_user = get_object_or_404(User, id=user_id)
    social_links = profile_user.social_links.all()  
    context = {
        'profile_user': profile_user,
        'social_links': social_links,
    }
    return render(request, 'users/profile.html', context)
    
@login_required
def show_my_profile(request):
    context = {
        'profile_user': request.user,
        'social_links': request.user.social_links.all(),
        'is_owner': True,
    }
    return render(request, 'users/profile.html', context)

# Authentication

def login_user(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect('frontpage')

    return render(request, 'users/login.html', {'form': form})

@require_POST
def logout_user(request):
    logout(request)
    return redirect('frontpage')

def register_user(request):
    form = RegisterForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Account successfully made! Please login')
        return redirect('users:login')

    return render(request, 'users/register.html', {'form': form})

# Update/Edit, Delete Account

@login_required
def update_profile(request):
    if request.method == 'POST':
        form = UpdateProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('users:show_my_profile')
    else:
        form = UpdateProfileForm(instance=request.user)

    return render(request, 'users/update_profile.html', {'form': form})

@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, 'Your account has been deleted.')
        return redirect('frontpage')
    return render(request, 'users/delete_account.html')


# Following/Followers

@login_required
@require_POST
def toggle_follow(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        return HttpResponseBadRequest('You cannot follow yourself.')

    link, created = Follow.objects.get_or_create(
        follower=request.user, following=target
    )
    if not created:          # already following → this click means unfollow
        link.delete()

    return redirect('users:show_profile', user_id=target.id)

def following_list(request, user_id):
    # Anyone can see who a user follows.
    profile_user = get_object_or_404(User, pk=user_id)
    links = (
        Follow.objects.filter(follower=profile_user)
        .select_related("following")
        .order_by("-created_at")
    )
    return render(request, "users/follow_list.html", {
        "profile_user": profile_user,
        "people": [link.following for link in links],
        "list_type": "following",
    })

@login_required
def followers_list(request, user_id):
    # Only the profile owner can see their own followers.
    profile_user = get_object_or_404(User, pk=user_id)
    if profile_user != request.user:
        raise PermissionDenied

    links = (
        Follow.objects.filter(following=profile_user)
        .select_related("follower")
        .order_by("-created_at")
    )
    return render(request, "users/follow_list.html", {
        "profile_user": profile_user,
        "people": [link.follower for link in links],
        "list_type": "followers",
    })
    
# TODO: view badges that the user owns?