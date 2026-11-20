from rest_framework import serializers

from .forms import MAX_AVATAR_SIZE
from .models import Badge, SocialLink, User, UserBadge


class SocialLinkSerializer(serializers.ModelSerializer):
    platform_display = serializers.CharField(source="get_platform_display", read_only=True)

    class Meta:
        model = SocialLink
        fields = ["id", "platform", "platform_display", "url"]

    def validate_platform(self, value):
        # one link per platform per user (also enforced by a database constraint)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            existing = SocialLink.objects.filter(user=request.user, platform=value)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError("You already have a link for this platform.")
        return value


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
    avatar_url = serializers.SerializerMethodField()
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "avatar_url", "is_following"]

    def get_avatar_url(self, obj):
        url = obj.avatar_src
        if not url:
            return ""
        request = self.context.get("request")
        # Flutter needs the full address, not just /media/...
        return request.build_absolute_uri(url) if request else url

    def get_is_following(self, obj):
        return obj.pk in self.context.get("following_ids", set())


class UserDetailSerializer(UserSummarySerializer):
    social_links = SocialLinkSerializer(many=True, read_only=True)
    badges = UserBadgeSerializer(source="user_badges", many=True, read_only=True)
    following_count = serializers.IntegerField(source="following.count", read_only=True)
    followers_count = serializers.IntegerField(source="followers.count", read_only=True)
    is_moderator = serializers.SerializerMethodField()

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + [
            "bio", "date_joined", "is_moderator", "following_count", "followers_count",
            "social_links", "badges",
        ]

    def get_is_moderator(self, obj):
        return obj.groups.filter(name="Moderator").exists()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_owner = bool(request and request.user.is_authenticated and request.user == instance)
        if not is_owner:
            data.pop("followers_count", None)   # followers are private to the owner
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

    def update(self, instance, validated_data):
        # replacing or clearing the photo: drop the old file from disk first
        if "avatar" in validated_data and instance.avatar:
            instance.avatar.delete(save=False)
        return super().update(instance, validated_data)