from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.files.uploadedfile import UploadedFile
from django.forms.models import BaseInlineFormSet, inlineformset_factory

from .models import SocialLink, SocialPlatform

User = get_user_model()

MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB


class AvatarValidationMixin:
    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        # only check a file that was just uploaded; on edits without a new
        # upload, avatar is the existing stored file, and reading its size
        # would hit the disk for no reason
        if isinstance(avatar, UploadedFile) and avatar.size > MAX_AVATAR_SIZE:
            raise forms.ValidationError("Image must be 2 MB or smaller.")
        return avatar


class RegisterForm(AvatarValidationMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "avatar", "bio")


class UpdateProfileForm(AvatarValidationMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'avatar', 'bio']
        widgets = {'bio': forms.Textarea(attrs={'rows': 4})}


class BaseSocialLinkFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        labels = dict(SocialPlatform.choices)
        # links that are part of this submission are covered by the duplicate check below
        submitted_pks = {f.instance.pk for f in self.forms if f.instance.pk}
        seen = set()

        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            platform = form.cleaned_data.get("platform")
            if not platform:
                continue

            # two rows for the same platform in this submission
            if platform in seen:
                raise forms.ValidationError("You can only add one link per platform.")
            seen.add(platform)

            # a new row for a platform the user already has saved
            if form.instance.pk is None and self.instance.pk:
                already_saved = (
                    SocialLink.objects
                    .filter(user=self.instance, platform=platform)
                    .exclude(pk__in=submitted_pks)
                    .exists()
                )
                if already_saved:
                    raise forms.ValidationError(
                        f"You already have a {labels.get(platform, platform)} link. "
                        "Edit it instead of adding another."
                    )


SocialLinkFormSet = inlineformset_factory(
    User,
    SocialLink,
    formset=BaseSocialLinkFormSet,
    fields=("platform", "url"),
    extra=0,
    max_num=len(SocialPlatform.choices),
    validate_max=True,
    can_delete=True,
)