from django.apps import AppConfig


class WeeklychallengeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'weeklychallenge'

    def ready(self):
        from .signals import connect_signals

        connect_signals()
