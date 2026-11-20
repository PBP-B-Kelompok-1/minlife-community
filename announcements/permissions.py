from rest_framework.permissions import BasePermission, SAFE_METHODS


class AnnouncementPermission(BasePermission):
    permission_map = {
        "POST": "announcements.add_announcement",
        "PUT": "announcements.change_announcement",
        "PATCH": "announcements.change_announcement",
        "DELETE": "announcements.delete_announcement",
    }

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        permission = self.permission_map.get(request.method)
        return bool(
            permission
            and request.user.is_authenticated
            and request.user.has_perm(permission)
        )
