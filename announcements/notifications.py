import base64
import json
import logging
from urllib.parse import urlsplit

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, exceptions, messaging

from .models import FCMSubscription


FCM_BATCH_SIZE = 500
logger = logging.getLogger(__name__)


def _build_firebase_credential():
    encoded_service_account = settings.FIREBASE_SERVICE_ACCOUNT_B64
    if encoded_service_account:
        service_account = json.loads(
            base64.b64decode(encoded_service_account).decode("utf-8")
        )
        return credentials.Certificate(service_account)

    return credentials.ApplicationDefault()


def _get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app(_build_firebase_credential())


def _notification_body(announcement):
    body = f"{announcement.title} — {announcement.content}"
    if len(body) > 180:
        return f"{body[:177].rstrip()}..."
    return body


def _chunks(values, size):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _webpush_config(detail_url):
    if urlsplit(detail_url).scheme != "https":
        return None

    return messaging.WebpushConfig(
        fcm_options=messaging.WebpushFCMOptions(link=detail_url),
    )


def send_announcement_notification(announcement, detail_url):
    if not settings.FIREBASE_PUSH_ENABLED:
        return 0

    subscriptions = FCMSubscription.objects.all()
    if announcement.created_by_id:
        subscriptions = subscriptions.exclude(user_id=announcement.created_by_id)

    installation_ids = list(
        subscriptions.values_list("installation_id", flat=True)
    )
    if not installation_ids:
        return 0

    firebase_app = _get_firebase_app()
    success_count = 0

    for installation_id_batch in _chunks(installation_ids, FCM_BATCH_SIZE):
        message = messaging.MulticastMessage(
            fids=installation_id_batch,
            notification=messaging.Notification(
                title="New announcement",
                body=_notification_body(announcement),
            ),
            data={
                "announcement_id": str(announcement.pk),
                "announcement_url": detail_url,
            },
            webpush=_webpush_config(detail_url),
        )

        try:
            response = messaging.send_each_for_multicast(
                message,
                app=firebase_app,
            )
        except (exceptions.FirebaseError, ValueError):
            logger.exception(
                "Could not send an FCM notification batch for announcement %s.",
                announcement.pk,
            )
            continue

        success_count += response.success_count
        unregistered_ids = [
            installation_id
            for installation_id, send_response in zip(
                installation_id_batch,
                response.responses,
            )
            if not send_response.success
            and isinstance(
                send_response.exception,
                messaging.UnregisteredError,
            )
        ]
        if unregistered_ids:
            FCMSubscription.objects.filter(
                installation_id__in=unregistered_ids
            ).delete()

    return success_count
