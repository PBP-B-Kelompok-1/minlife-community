from django.urls import path

from . import api_views as views

urlpatterns = [
    path("search/", views.UserSearchView.as_view(), name="user_search"),
    path("me/", views.MeView.as_view(), name="user_me"),
    path("<uuid:user_id>/", views.UserDetailView.as_view(), name="user_detail"),
    path("<uuid:user_id>/follow/", views.FollowView.as_view(), name="user_follow"),
    path("<uuid:user_id>/following/", views.FollowingListView.as_view(), name="user_following"),
    path("<uuid:user_id>/followers/", views.FollowersListView.as_view(), name="user_followers"),
]