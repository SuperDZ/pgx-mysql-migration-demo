from django.apps import AppConfig


class BanktelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "banktel"

    def ready(self):
        from . import signals  # noqa: F401
