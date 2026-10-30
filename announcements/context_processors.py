from django.conf import settings


def firebase_notifications(request):
    web_config = settings.FIREBASE_WEB_CONFIG
    config_is_complete = bool(settings.FIREBASE_VAPID_KEY) and all(
        web_config.values()
    )
    return {
        "firebase_notifications_enabled": (
            request.user.is_authenticated and config_is_complete
        ),
        "firebase_web_config": web_config,
        "firebase_vapid_key": settings.FIREBASE_VAPID_KEY,
    }
