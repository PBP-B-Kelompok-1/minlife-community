from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django import forms
from django.forms.models import inlineformset_factory
from .models import SocialLink, SocialPlatform

User = get_user_model()

class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name", "avatar_url", "bio")
        
class UpdateProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'avatar_url', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }
        
SocialLinkFormSet = inlineformset_factory(
    User,
    SocialLink,
    fields=("platform", "url"),
    extra=0,
    max_num=len(SocialPlatform.choices),       # 5 platforms → 5 rows max,          # one blank row for adding a new link
    can_delete=True,  # a Delete checkbox on each existing link
)