from rest_framework.permissions import BasePermission, SAFE_METHODS


class ChallengePermission(BasePermission):
    permission_map = {
        "POST": "weeklychallenge.add_challenge",
        "PUT": "weeklychallenge.change_challenge",
        "PATCH": "weeklychallenge.change_challenge",
        "DELETE": "weeklychallenge.delete_challenge",
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
