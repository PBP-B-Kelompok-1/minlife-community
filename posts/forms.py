from django import forms
from django.utils.html import strip_tags
from django_ckeditor_5.fields import CKEditor5Widget
from .models import Post, Comment

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = [
            "title",
            "tags",
            "challenge_image",
            "content",
        ]
        labels = {
            "title": "Post title",
            "tags": "Tags",
            "challenge_image": "Challenge image",
            "content": "Content",
        }
        widgets = {
            "content": CKEditor5Widget(config_name="post")
        }

    def clean(self):
        cleaned_data = super().clean()
        tags = cleaned_data.get("tags")
        challenge_image = cleaned_data.get("challenge_image")

        if tags and tags.filter(title__iexact="Weekly Challenge").exists() and not challenge_image:
            self.add_error(
                "challenge_image",
                "A challenge image is required for Weekly Challenge posts.",
            )

        return cleaned_data

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = [ "content" ]
        widgets = {
            "content": CKEditor5Widget(config_name="comment")
        }
