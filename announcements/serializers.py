from django.utils import timezone
from django.utils.formats import date_format
from rest_framework import serializers

from .models import Announcement


class AnnouncementCreatorSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by = AnnouncementCreatorSerializer(read_only=True)
    created_at_display = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id", "title", "content", "created_by", "created_at",
            "created_at_display", "updated_at",
        ]
        read_only_fields = [
            "id", "created_by", "created_at", "created_at_display", "updated_at",
        ]

    def get_created_at_display(self, obj):
        return date_format(timezone.localtime(obj.created_at), "j M Y")


class InstallationIDField(serializers.CharField):
    def to_internal_value(self, data):
        # Do not silently coerce JSON numbers into device identifiers.
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class NotificationSubscriptionSerializer(serializers.Serializer):
    installation_id = InstallationIDField(max_length=255)
