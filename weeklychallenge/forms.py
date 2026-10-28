# forms.py
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
            "week_end",
        ]
        # badge and created_by are set in the view, not by the moderator
        widgets = {
            "week_start": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "week_end": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        week_start = cleaned_data.get("week_start")
        week_end = cleaned_data.get("week_end")

        if not week_start or not week_end:
            return cleaned_data

        if week_end < week_start:
            self.add_error("week_end", "Tanggal selesai harus sama atau setelah tanggal mulai.")
            return cleaned_data

        overlapping_challenges = Challenge.objects.filter(
            week_start__lte=week_end,
            week_end__gte=week_start,
        )
        if self.instance.pk:
            overlapping_challenges = overlapping_challenges.exclude(pk=self.instance.pk)

        if overlapping_challenges.exists():
            self.add_error(
                None,
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
