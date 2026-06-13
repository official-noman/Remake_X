"""DRF viewsets for Odoo synchronization APIs."""

from __future__ import annotations

from typing import Any

import structlog
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import APIException
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from odoo_sync.filters import OdooProductFilter, SyncLogFilter
from odoo_sync.models import OdooProduct, SyncConfig, SyncLog
from odoo_sync.serializers import (
    OdooProductSerializer,
    SyncConfigSerializer,
    SyncLogSerializer,
    TriggerSyncSerializer,
)
from odoo_sync.tasks import sync_odoo_products_delta, sync_odoo_products_full
from odoo_sync.health import check_odoo_connection

logger = structlog.get_logger(__name__)


class OdooProductCursorPagination(CursorPagination):
    page_size = 50
    ordering = "-last_synced_at"


class OdooProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OdooProductSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = OdooProductCursorPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_class = OdooProductFilter
    search_fields = ("odoo_name", "odoo_sku")
    ordering_fields = ("odoo_price", "odoo_qty_available", "last_synced_at")
    ordering = ("-last_synced_at",)

    def get_queryset(self):
        return OdooProduct.objects.select_related("local_product").all()

    @action(detail=True, methods=["post"])
    def resolve_conflict(self, request: Request, pk: str | None = None) -> Response:
        product = self.get_object()

        with transaction.atomic():
            if product.local_product is not None:
                _apply_local_values_to_odoo_product(product)

            product.sync_status = OdooProduct.SyncStatus.SYNCED
            product.sync_error_message = ""
            product.save(
                update_fields=(
                    "odoo_name",
                    "odoo_sku",
                    "odoo_price",
                    "odoo_qty_available",
                    "odoo_active",
                    "sync_status",
                    "sync_error_message",
                    "updated_at",
                )
            )

        serializer = self.get_serializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SyncLogSerializer
    permission_classes = (IsAuthenticated,)
    queryset = SyncLog.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = SyncLogFilter

    @action(detail=False, methods=["get"])
    def latest(self, request: Request) -> Response:
        sync_log = self.get_queryset().first()
        if sync_log is None:
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = self.get_serializer(sync_log)
        return Response(serializer.data)


class SyncConfigViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SyncConfigSerializer
    queryset = SyncConfig.objects.all()

    def get_permissions(self):
        if self.action in ("update", "partial_update"):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_object(self) -> SyncConfig:
        sync_config, _created = SyncConfig.objects.get_or_create(id=1)
        self.check_object_permissions(self.request, sync_config)
        return sync_config


class SyncTriggerViewSet(viewsets.GenericViewSet):
    serializer_class = TriggerSyncSerializer
    permission_classes = (IsAdminUser,)

    @action(detail=False, methods=["post"])
    def trigger(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sync_type = serializer.validated_data["sync_type"]

        health = check_odoo_connection()
        if health["status"] == "down":
            return Response(
                {"detail": "Odoo connection is down."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        triggered_by = serializer.validated_data.get("triggered_by") or _request_username(
            request
        )
        sync_log_type = (
            SyncLog.SyncType.DELTA
            if sync_type == "delta"
            else SyncLog.SyncType.FULL
        )
        sync_log = SyncLog.objects.create(
            sync_type=sync_log_type,
            status=SyncLog.Status.RUNNING,
            triggered_by=triggered_by,
        )

        task_kwargs = {
            "triggered_by": triggered_by,
            "sync_log_id": str(sync_log.id),
        }
        try:
            if sync_type == "delta":
                async_result = sync_odoo_products_delta.delay(**task_kwargs)
            else:
                async_result = sync_odoo_products_full.delay(**task_kwargs)
        except Exception as exc:
            logger.exception(
                "odoo_sync_task_queue_failed",
                sync_log_id=str(sync_log.id),
                sync_type=sync_type,
                error_type=type(exc).__name__,
            )
            sync_log.error_detail = {
                "queue": {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            }
            sync_log.save(update_fields=("error_detail",))
            sync_log.mark_finished(SyncLog.Status.FAILED)
            raise APIException("Unable to queue Odoo sync task.") from exc

        return Response(
            {
                "status": "queued",
                "sync_log_id": str(sync_log.id),
                "task_id": async_result.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


def _request_username(request: Request) -> str:
    user = request.user
    username = getattr(user, "get_username", lambda: "")()
    return username or "manual"


def _apply_local_values_to_odoo_product(odoo_product: OdooProduct) -> None:
    local_product = odoo_product.local_product
    if local_product is None:
        return

    if hasattr(local_product, "name"):
        odoo_product.odoo_name = str(local_product.name)[:512]
    if hasattr(local_product, "sku"):
        odoo_product.odoo_sku = str(local_product.sku or "")[:128]
    if hasattr(local_product, "price"):
        odoo_product.odoo_price = local_product.price
    if hasattr(local_product, "quantity"):
        odoo_product.odoo_qty_available = float(local_product.quantity)
    if hasattr(local_product, "status"):
        odoo_product.odoo_active = str(local_product.status).lower() == "active"
    elif hasattr(local_product, "is_available"):
        odoo_product.odoo_active = bool(local_product.is_available)


@api_view(["GET"])
@permission_classes([AllowAny])
def odoo_health_view(request: Request) -> Response:
    health_data = check_odoo_connection()
    status_code = status.HTTP_200_OK if health_data["status"] == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(health_data, status=status_code)
