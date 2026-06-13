"""URL routes for Odoo synchronization APIs."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from odoo_sync.views import (
    OdooProductViewSet,
    SyncConfigViewSet,
    SyncLogViewSet,
    SyncTriggerViewSet,
    odoo_health_view,
)

router = DefaultRouter()
router.register("products", OdooProductViewSet, basename="odoo-product")
router.register("logs", SyncLogViewSet, basename="sync-log")
router.register("config", SyncConfigViewSet, basename="sync-config")
router.register("sync", SyncTriggerViewSet, basename="sync-trigger")

urlpatterns = [
    path("health/", odoo_health_view, name="odoo-health"),
    path("", include(router.urls)),
]
