from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django import forms
from django.utils.html import strip_tags
from django_ckeditor_5.fields import CKEditor5Widget
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

from .models import Post, Comment

MAX_CHALLENGE_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_CHALLENGE_IMAGE_PIXELS = 25_000_000

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
            "content": CKEditor5Widget(config_name="post"),
            "challenge_image": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def clean_content(self):
        return sanitize_ckeditor_html(self.cleaned_data["content"])
    
    def clean_title(self):
        title = strip_tags(self.cleaned_data["title"]).strip()
        if not title:
            raise ValidationError("Well well well, someone tried to do XSS! Probably.")
        return title

    def clean_challenge_image(self):
        image = self.cleaned_data.get("challenge_image")
        if not image:
            return image

        # Existing images are already validated when they are uploaded. On an
        # edit with no replacement, Django returns that existing FieldFile.
        if not isinstance(image, UploadedFile):
            return image

        if image.size > MAX_CHALLENGE_IMAGE_SIZE:
            raise ValidationError("Image must be 5 MB or smaller.")

        # ImageField has already verified the image with Pillow. Limit the decoded
        # dimensions too, so a very small compressed file cannot expand excessively.
        width, height = image.image.size
        if width * height > MAX_CHALLENGE_IMAGE_PIXELS:
            raise ValidationError("Image must be 25 megapixels or smaller.")

        return image

    def clean(self):
        cleaned_data = super().clean()
        tags = cleaned_data.get("tags")
        challenge_image = cleaned_data.get("challenge_image")

        if not self.instance._state.adding and tags is not None:
            had_weekly_challenge_tag = self.instance.tags.filter(
                title__iexact="Weekly Challenge"
            ).exists()
            has_weekly_challenge_tag = tags.filter(
                title__iexact="Weekly Challenge"
            ).exists()
            if had_weekly_challenge_tag != has_weekly_challenge_tag:
                self.add_error(
                    "tags",
                    "The Weekly Challenge tag cannot be added or removed when editing a post.",
                )

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

    def clean_content(self):
        return sanitize_ckeditor_html(self.cleaned_data["content"])


# By codex, of course
class CKEditorHTMLSanitizer(HTMLParser):
    """Keep the subset of HTML produced by the post CKEditor configuration."""

    allowed_tags = {
        "a", "blockquote", "br", "code", "em", "figure", "figcaption", "h2", "i",
        "h3", "h4", "h5", "h6", "img", "li", "ol", "p", "pre", "s", "span",
        "strong", "ul",
    }
    allowed_attributes = {
        "a": {"href", "rel", "target"},
        "figure": {"class"},
        "img": {"alt", "class", "height", "src", "width"},
        "span": {"class"},
    }
    # These tags can execute or change how the rest of the document is parsed.
    discard_contents_tags = {"base", "embed", "iframe", "math", "object", "script", "style", "svg", "template"}
    void_tags = {"br", "img"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.discard_depth = 0

    @staticmethod
    def _is_safe_url(value, allowed_schemes):
        # Browsers ignore control characters in URL schemes, so check a normalized
        # version too (for example, "java\tscript:").
        normalized = "".join(char for char in value if ord(char) > 32)
        try:
            scheme = urlsplit(normalized).scheme.lower()
        except ValueError:
            return False
        return not scheme or scheme in allowed_schemes

    def _safe_attributes(self, tag, attrs):
        safe_attributes = []
        for name, value in attrs:
            name = name.lower()
            if value is None or name not in self.allowed_attributes.get(tag, set()):
                continue
            if name == "href" and not self._is_safe_url(value, {"http", "https", "mailto"}):
                continue
            if name == "src" and not self._is_safe_url(value, {"http", "https"}):
                continue
            safe_attributes.append(f' {name}="{escape(value, quote=True)}"')

        # A new browsing context should not get access to this page through opener.
        if tag == "a" and any(name == "target" and value == "_blank" for name, value in attrs):
            safe_attributes = [attribute for attribute in safe_attributes if not attribute.startswith(" rel=")]
            safe_attributes.append(' rel="noopener noreferrer"')
        return "".join(safe_attributes)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.discard_contents_tags:
            self.discard_depth += 1
        if self.discard_depth or tag not in self.allowed_tags:
            return
        self.parts.append(f"<{tag}{self._safe_attributes(tag, attrs)}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() in self.discard_contents_tags and self.discard_depth:
            self.discard_depth -= 1

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.discard_contents_tags and self.discard_depth:
            self.discard_depth -= 1
            return
        if not self.discard_depth and tag in self.allowed_tags and tag not in self.void_tags:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.discard_depth:
            self.parts.append(escape(data))

    def sanitized_html(self):
        return "".join(self.parts)


def sanitize_ckeditor_html(value):
    sanitizer = CKEditorHTMLSanitizer()
    sanitizer.feed(value)
    sanitizer.close()
    return sanitizer.sanitized_html()


