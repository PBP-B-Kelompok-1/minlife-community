from django.urls import path

from . import api_views as views

urlpatterns = [
    # authentication
    path("login/", views.LoginView.as_view(), name="auth_login"),
    path("register/", views.RegisterView.as_view(), name="auth_register"),
    path("logout/", views.LogoutView.as_view(), name="auth_logout"),

    # the logged-in user
    path("me/", views.MeView.as_view(), name="user_me"),
    path("me/social-links/", views.SocialLinkListCreateView.as_view(), name="user_social_links"),
    path("me/social-links/<int:pk>/", views.SocialLinkDetailView.as_view(), name="user_social_link"),

    # other users
    path("search/", views.UserSearchView.as_view(), name="user_search"),
    path("<uuid:user_id>/", views.UserDetailView.as_view(), name="user_detail"),
    path("<uuid:user_id>/follow/", views.FollowView.as_view(), name="user_follow"),
    path("<uuid:user_id>/following/", views.FollowingListView.as_view(), name="user_following"),
    path("<uuid:user_id>/followers/", views.FollowersListView.as_view(), name="user_followers"),
]