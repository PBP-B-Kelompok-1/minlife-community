# forms.py
from django import forms
from django.forms import inlineformset_factory
from .models import Challenge, ChallengeTask, MAX_TASKS_PER_CHALLENGE


class ChallengeForm(forms.ModelForm):
    class Meta:
        model = Challenge
        fields = ["title", "background", "description", "goal",
                  "upvote_threshold", "week_start", "week_end"]
        # badge and created_by are set in the view, not by the moderator


ChallengeTaskFormSet = inlineformset_factory(
    Challenge,
    ChallengeTask,
    fields=["day_number", "title", "description"],
    extra=1,
    max_num=MAX_TASKS_PER_CHALLENGE,
    validate_max=True,
    can_delete=True,
)