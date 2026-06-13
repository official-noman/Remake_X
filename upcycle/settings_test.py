# Django test settings — inherits from settings.py, overrides for test environment.
from __future__ import annotations

from upcycle.settings import *  # noqa: F401, F403

# ── Fast in-memory database ───────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ── Celery runs tasks synchronously so tests don't need a broker ──────────────
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ── Channels: use an in-memory channel layer (no Redis) ───────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# ── Dummy Odoo credentials (no real server needed) ───────────────────────────
ODOO_URL = "http://mock-odoo.local"
ODOO_DB = "mock_db"
ODOO_USERNAME = "admin"
ODOO_PASSWORD = "mock_password"

# ── Silence noisy logging ─────────────────────────────────────────────────────
import logging  # noqa: E402

logging.disable(logging.CRITICAL)
