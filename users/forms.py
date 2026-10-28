from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django import forms
from django.forms.models import inlineformset_factory
from .models import SocialLink, SocialPlatform

User = get_user_model()

class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name", "avatar", "bio")
        
class UpdateProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'avatar', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }
        
    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "size") and avatar.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Image must be 2 MB or smaller.")
        return avatar
        
SocialLinkFormSet = inlineformset_factory(
    User,
    SocialLink,
    fields=("platform", "url"),
    extra=0,
    max_num=len(SocialPlatform.choices),       # 5 platforms → 5 rows max,          # one blank row for adding a new link
    can_delete=True,  # a Delete checkbox on each existing link
)