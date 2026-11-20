from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session login without DRF's CSRF check, so Flutter's CookieRequest can POST/PATCH/DELETE."""
    def enforce_csrf(self, request):
        return