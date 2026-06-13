"""WebSocket routes for Odoo sync status updates."""

from django.urls import path

from odoo_sync.consumers import SyncStatusConsumer

websocket_urlpatterns = [
    path("ws/odoo-sync/status/", SyncStatusConsumer.as_asgi()),
]
