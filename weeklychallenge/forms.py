from datetime import timedelta

from django import forms
from django.forms import inlineformset_factory

from .models import Challenge, ChallengeTask, MAX_TASKS_PER_CHALLENGE


class ChallengeForm(forms.ModelForm):
    class Meta:
        model = Challenge
        fields = [
            "title",
            "background",
            "description",
            "goal",
            "upvote_threshold",
            "week_start",
        ]
        # badge and created_by are set in the view, not by the moderator
        widgets = {
            "week_start": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        week_start = cleaned_data.get("week_start")
        if not week_start:
            return cleaned_data

        window = timedelta(days=MAX_TASKS_PER_CHALLENGE - 1)
        overlapping = Challenge.objects.filter(
            week_start__gte=week_start - window,
            week_start__lte=week_start + window,
        )
        if self.instance.pk:
            overlapping = overlapping.exclude(pk=self.instance.pk)

        if overlapping.exists():
            self.add_error(
                "week_start",
                "Rentang tanggal challenge tidak boleh tumpang tindih dengan challenge lain.",
            )
        return cleaned_data


ChallengeTaskFormSet = inlineformset_factory(
    Challenge,
    ChallengeTask,
    fields=["day_number", "title", "description"],
    extra=1,
    max_num=MAX_TASKS_PER_CHALLENGE,
    validate_max=True,
    can_delete=True,
)
