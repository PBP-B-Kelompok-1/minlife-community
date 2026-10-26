from django.urls import path
from django.views.generic import RedirectView
from . import views              # then use views.show_profile, etc.

app_name = "users"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="users:show_my_profile")),
    path("<uuid:user_id>/", views.show_profile, name="show_profile"),
    path("me/", views.show_my_profile, name="show_my_profile"),
    path("register/", views.register_user, name="register"),
    path("login/", views.login_user, name="login"),
    path("logout/", views.logout_user, name="logout"),
    path("<uuid:user_id>/follow/", views.toggle_follow, name="toggle_follow"),
    path('profile/edit/', views.update_profile, name='update_profile'),
    path("<uuid:user_id>/following/", views.following_list, name="following_list"),
    path("<uuid:user_id>/followers/", views.followers_list, name="followers_list"),
]