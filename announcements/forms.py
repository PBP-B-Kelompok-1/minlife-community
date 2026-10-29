from django import forms

from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "content"]
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "Announcement title"}
            ),
            "content": forms.Textarea(
                attrs={
                    "placeholder": "Write the community update here",
                    "rows": 8,
                }
            ),
        }
