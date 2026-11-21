from django.urls import path

from . import api_views

app_name = "weeklychallenge_api"

urlpatterns = [
    path("", api_views.challenge_list_create, name="challenge-list"),
    path("current/", api_views.challenge_current, name="challenge-current"),
    path("capabilities/", api_views.challenge_capabilities, name="challenge-capabilities"),
    path("<int:pk>/submissions/", api_views.challenge_submissions, name="challenge-submissions"),
    path("<int:pk>/", api_views.challenge_detail, name="challenge-detail"),
]
