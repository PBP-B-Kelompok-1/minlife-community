from .forms import ChallengeForm, ChallengeTaskFormSet
from django.db import transaction
from django.shortcuts import redirect, render
from users.models import Badge


def show_weekly_challenge(request):
    return redirect("")


def challenge_create(request):
    if request.method == "POST":
        form = ChallengeForm(request.POST)
        formset = ChallengeTaskFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                challenge = form.save(commit=False)
                challenge.badge = Badge.objects.create(
                    name=f"{challenge.title} Badge",
                    description=f"Selesaikan challenge: {challenge.title}",
                )  # badge first, because Challenge.badge is NOT NULL
                challenge.created_by = request.user
                challenge.save()
                formset.instance = challenge
                formset.save()
            return redirect("challenge_detail", pk=challenge.pk)
    else:
        form = ChallengeForm()
        formset = ChallengeTaskFormSet()
    return render(request, "challenge_form.html", {"form": form, "formset": formset})
