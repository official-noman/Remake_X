"""Django app configuration for Odoo synchronization."""

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class OdooSyncConfig(AppConfig):
    """Application configuration for the Odoo sync service."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "odoo_sync"

    def ready(self) -> None:
        """Validate required Odoo settings when Django starts."""
        required_settings = (
            "ODOO_URL",
            "ODOO_DB",
            "ODOO_USERNAME",
            "ODOO_PASSWORD",
        )
        missing_settings = [
            setting_name
            for setting_name in required_settings
            if not getattr(settings, setting_name, None)
        ]

        if missing_settings:
            missing = ", ".join(missing_settings)
            raise ImproperlyConfigured(
                "Missing required Odoo configuration setting(s): "
                f"{missing}. Define them as environment variables."
            )
