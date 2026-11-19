from django.utils.html import strip_tags
from rest_framework import serializers

from .models import Challenge, ChallengeTask, MAX_TASKS_PER_CHALLENGE
from .selectors import challenge_status, validate_no_overlap
from .services import user_has_submitted


class BadgeSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    icon_url = serializers.CharField(read_only=True)


class ChallengeTaskSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()

    class Meta:
        model = ChallengeTask
        fields = ["id", "day_number", "date", "title", "description"]
        read_only_fields = ["id", "date"]

    def get_date(self, obj):
        from datetime import timedelta

        return obj.challenge.week_start + timedelta(days=obj.day_number - 1)


class UserSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)


class ChallengeListSerializer(serializers.ModelSerializer):
    week_end = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    submission_count = serializers.IntegerField(read_only=True)
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = Challenge
        fields = [
            "id", "title", "week_start", "week_end", "status",
            "upvote_threshold", "submission_count", "badge",
        ]

    def _is_teaser(self, obj):
        request = self.context["request"]
        return (
            challenge_status(obj, self.context["today"]) == "upcoming"
            and not request.user.has_perm("weeklychallenge.change_challenge")
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self._is_teaser(instance):
            return {
                "id": data["id"],
                "title": data["title"],
                "week_start": data["week_start"],
                "status": data["status"],
                "is_teaser": True,
            }
        return data

    def get_week_end(self, obj):
        return obj.week_end

    def get_status(self, obj):
        return challenge_status(obj, self.context["today"])

class ChallengeDetailSerializer(ChallengeListSerializer):
    background = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    goal = serializers.CharField(read_only=True)
    created_by = UserSummarySerializer(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    current_day = serializers.SerializerMethodField()
    has_submitted = serializers.SerializerMethodField()
    tasks = serializers.SerializerMethodField()
    is_teaser = serializers.SerializerMethodField()

    class Meta(ChallengeListSerializer.Meta):
        fields = ChallengeListSerializer.Meta.fields + [
            "background", "description", "goal", "created_by", "created_at",
            "current_day", "has_submitted", "tasks", "is_teaser",
        ]

    def get_current_day(self, obj):
        status = challenge_status(obj, self.context["today"])
        if status == "upcoming":
            return None
        return min(max((self.context["today"] - obj.week_start).days + 1, 1),
                   MAX_TASKS_PER_CHALLENGE)

    def get_has_submitted(self, obj):
        return user_has_submitted(self.context["request"].user, obj)

    def get_tasks(self, obj):
        if self._is_teaser(obj):
            return []
        current_day = self.get_current_day(obj)
        tasks = obj.tasks.all()
        if not self.context["request"].user.has_perm("weeklychallenge.change_challenge"):
            tasks = tasks.filter(day_number__lte=current_day)
        return ChallengeTaskSerializer(tasks, many=True, context=self.context).data

    def to_representation(self, instance):
        data = super(ChallengeListSerializer, self).to_representation(instance)
        if self._is_teaser(instance):
            return {
                "id": data["id"],
                "title": data["title"],
                "week_start": data["week_start"],
                "status": data["status"],
                "is_teaser": True,
            }
        return data

    def get_is_teaser(self, obj):
        return self._is_teaser(obj)


class ChallengeWriteSerializer(serializers.ModelSerializer):
    tasks = ChallengeTaskSerializer(many=True, required=True)

    class Meta:
        model = Challenge
        fields = [
            "title", "background", "description", "goal",
            "upvote_threshold", "week_start", "tasks",
        ]

    def to_internal_value(self, data):
        writable_fields = set(self.fields) - {
            field_name for field_name, field in self.fields.items() if field.read_only
        }
        return super().to_internal_value({
            key: value for key, value in data.items() if key in writable_fields
        })

    def validate(self, attrs):
        instance = self.instance
        week_start = attrs.get("week_start", instance.week_start if instance else None)
        if week_start and validate_no_overlap(week_start, instance.pk if instance else None):
            raise serializers.ValidationError({
                "week_start": "Rentang tanggal challenge tidak boleh tumpang tindih dengan challenge lain."
            })

        if "tasks" in attrs:
            tasks = attrs["tasks"]
            if len(tasks) > MAX_TASKS_PER_CHALLENGE:
                raise serializers.ValidationError({
                    "tasks": f"Ensure this field has no more than {MAX_TASKS_PER_CHALLENGE} items."
                })
            days = [task["day_number"] for task in tasks]
            if len(days) != len(set(days)):
                raise serializers.ValidationError({"tasks": "Day numbers must be unique."})
        elif not instance:
            raise serializers.ValidationError({"tasks": "This field is required."})
        return attrs

    def _strip_text(self, value):
        return strip_tags(value).strip()

    def validate_title(self, value):
        value = self._strip_text(value)
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_background(self, value):
        return self._strip_text(value)

    def validate_description(self, value):
        return self._strip_text(value)

    def validate_goal(self, value):
        return self._strip_text(value)

    def validate_upvote_threshold(self, value):
        if value < 1:
            raise serializers.ValidationError("Ensure this value is greater than or equal to 1.")
        return value

    def validate_tasks(self, tasks):
        for task in tasks:
            task["title"] = self._strip_text(task["title"])
            task["description"] = self._strip_text(task["description"])
            if not task["title"]:
                raise serializers.ValidationError("Task title may not be blank.")
        return tasks


class SubmissionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    score = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    user = UserSummarySerializer(read_only=True)
    post = serializers.SerializerMethodField()

    def get_post(self, obj):
        request = self.context["request"]
        image_url = obj.post.challenge_image.url if obj.post.challenge_image else None
        if image_url:
            image_url = request.build_absolute_uri(image_url)
        return {
            "id": str(obj.post.id),
            "title": obj.post.title,
            "image_url": image_url,
        }
