from rest_framework import serializers

from .forms import MAX_AVATAR_SIZE
from .models import Badge, SocialLink, User, UserBadge


class SocialLinkSerializer(serializers.ModelSerializer):
    platform_display = serializers.CharField(source="get_platform_display", read_only=True)

    class Meta:
        model = SocialLink
        fields = ["id", "platform", "platform_display", "url"]


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ["id", "name", "description", "icon_url"]


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ["badge", "earned_at"]


class UserSummarySerializer(serializers.ModelSerializer):
    """Compact user, used in search results and follow lists."""
    avatar_url = serializers.CharField(source="avatar_src", read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "avatar_url", "is_following"]

    def get_is_following(self, obj):
        return obj.pk in self.context.get("following_ids", set())


class UserDetailSerializer(UserSummarySerializer):
    social_links = SocialLinkSerializer(many=True, read_only=True)
    badges = UserBadgeSerializer(source="user_badges", many=True, read_only=True)
    following_count = serializers.IntegerField(source="following.count", read_only=True)
    followers_count = serializers.IntegerField(source="followers.count", read_only=True)

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + [
            "bio", "date_joined", "following_count", "followers_count",
            "social_links", "badges",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_owner = request and request.user.is_authenticated and request.user == instance
        if not is_owner:
            data.pop("followers_count")   # followers are private to the owner
        return data


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "bio", "avatar"]
        extra_kwargs = {"avatar": {"required": False, "allow_null": True}}   # null clears the photo

    def validate_avatar(self, value):
        if value and value.size > MAX_AVATAR_SIZE:
            raise serializers.ValidationError("Image must be 2 MB or smaller.")
        return value