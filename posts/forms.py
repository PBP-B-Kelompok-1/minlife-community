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
            "content",
        ]
        labels = {
            "title": "Post title",
            "tags": "Tags",            
            "content": "Content",            
        }
        widgets = {
            "content": CKEditor5Widget(config_name="post")
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = [ "content" ]
        widgets = {
            "content": CKEditor5Widget(config_name="comment")
        }
