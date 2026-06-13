"""Rich admin interface for Odoo synchronization."""

from __future__ import annotations

import json
from typing import Any

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from odoo_sync.models import OdooProduct, SyncConfig, SyncLog
from odoo_sync.tasks import (
    _build_local_product,
    sync_odoo_products_by_ids,
    sync_odoo_products_delta,
    sync_odoo_products_full,
)


# ---------------------------------------------------------------------------
# Custom widgets
# ---------------------------------------------------------------------------


class PrettyJSONWidget(forms.Textarea):
    """Textarea widget that pretty-prints JSON values."""

    def format_value(self, value: Any) -> str:
        if value in (None, ""):
            return "{}"
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return value
        return json.dumps(value, indent=2, sort_keys=True, cls=DjangoJSONEncoder)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _status_badge(value: str) -> str:
    """Return a pill-shaped, color-coded HTML badge for a status value."""
    colors: dict[str, tuple[str, str]] = {
        OdooProduct.SyncStatus.SYNCED: ("#137333", "#e6f4ea"),
        OdooProduct.SyncStatus.PENDING: ("#9a6700", "#fff8c5"),
        OdooProduct.SyncStatus.CONFLICT: ("#9a6700", "#fff8c5"),
        OdooProduct.SyncStatus.ERROR: ("#b3261e", "#fce8e6"),
        OdooProduct.SyncStatus.SKIPPED: ("#5f6368", "#f1f3f4"),
        SyncLog.Status.SUCCESS: ("#137333", "#e6f4ea"),
        SyncLog.Status.RUNNING: ("#0b57d0", "#e8f0fe"),
        SyncLog.Status.PARTIAL: ("#9a6700", "#fff8c5"),
        SyncLog.Status.FAILED: ("#b3261e", "#fce8e6"),
    }
    color, background = colors.get(value, ("#5f6368", "#f1f3f4"))
    return format_html(
        '<span style="display:inline-block;padding:3px 9px;border-radius:999px;'
        'font-weight:600;font-size:0.8em;letter-spacing:0.02em;'
        'color:{};background:{};white-space:nowrap;">{}</span>',
        color,
        background,
        value,
    )


def _bool_icon(value: bool, *, true_label: str = "Yes", false_label: str = "No") -> str:
    """Return a colored icon span for a boolean value."""
    if value:
        return format_html(
            '<span style="color:#137333;font-weight:600;" title="{}">'
            "✔ {}</span>",
            true_label,
            true_label,
        )
    return format_html(
        '<span style="color:#b3261e;font-weight:600;" title="{}">'
        "✘ {}</span>",
        false_label,
        false_label,
    )


# ---------------------------------------------------------------------------
# OdooProductAdmin
# ---------------------------------------------------------------------------


@admin.register(OdooProduct)
class OdooProductAdmin(admin.ModelAdmin):
    list_display = (
        "odoo_id",
        "odoo_name",
        "odoo_sku",
        "odoo_price",
        "odoo_qty_available",
        "sync_status_badge",
        "last_synced_at",
        "has_local_product",
    )
    list_filter = ("sync_status", "odoo_active", "odoo_categ_name")
    search_fields = ("odoo_name", "odoo_sku", "=odoo_id")
    actions = ("mark_as_synced", "trigger_resync", "create_local_products")

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @admin.display(description="Sync status", ordering="sync_status")
    def sync_status_badge(self, obj: OdooProduct) -> str:
        return _status_badge(obj.sync_status)

    @admin.display(description="Local product")
    def has_local_product(self, obj: OdooProduct) -> str:
        """Colored icon showing whether a local Product record exists."""
        return _bool_icon(obj.local_product_id is not None)

    # ------------------------------------------------------------------
    # Readonly behaviour — every field except sync_status is read-only
    # ------------------------------------------------------------------

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: OdooProduct | None = None,
    ) -> tuple[str, ...]:
        readonly = [
            field.name
            for field in self.model._meta.fields
            if field.name != "sync_status"
        ]
        return tuple(readonly)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @admin.action(description="Mark selected products as synced")
    def mark_as_synced(
        self,
        request: HttpRequest,
        queryset: models.QuerySet,
    ) -> None:
        updated = queryset.update(
            sync_status=OdooProduct.SyncStatus.SYNCED,
            sync_error_message="",
        )
        self.message_user(
            request,
            f"{updated} Odoo product(s) marked as synced.",
            messages.SUCCESS,
        )

    @admin.action(description="Re-fetch selected products from Odoo (Celery task)")
    def trigger_resync(
        self,
        request: HttpRequest,
        queryset: models.QuerySet,
    ) -> None:
        odoo_ids = list(queryset.values_list("odoo_id", flat=True))
        if not odoo_ids:
            self.message_user(request, "No Odoo products selected.", messages.WARNING)
            return

        async_result = sync_odoo_products_by_ids.delay(
            odoo_ids=odoo_ids,
            triggered_by=request.user.get_username() or "admin",
        )
        self.message_user(
            request,
            f"Queued resync for {len(odoo_ids)} product(s). Task ID: {async_result.id}",
            messages.SUCCESS,
        )

    @admin.action(description="Create local products for selected Odoo products")
    def create_local_products(
        self,
        request: HttpRequest,
        queryset: models.QuerySet,
    ) -> None:
        created = 0
        skipped = 0

        for odoo_product in queryset.filter(local_product__isnull=True):
            local_product = _build_local_product(
                {
                    "odoo_id": odoo_product.odoo_id,
                    "odoo_name": odoo_product.odoo_name,
                    "odoo_sku": odoo_product.odoo_sku,
                    "odoo_price": odoo_product.odoo_price,
                    "odoo_qty_available": odoo_product.odoo_qty_available,
                    "odoo_active": odoo_product.odoo_active,
                    "odoo_categ_name": odoo_product.odoo_categ_name,
                },
                odoo_product.raw_data or {},
            )
            if local_product is None:
                skipped += 1
                continue

            odoo_product.local_product = local_product
            odoo_product.save(update_fields=("local_product", "updated_at"))
            created += 1

        level = messages.SUCCESS if created else messages.WARNING
        self.message_user(
            request,
            f"Created {created} local product(s); skipped {skipped}.",
            level,
        )


# ---------------------------------------------------------------------------
# SyncLogAdmin
# ---------------------------------------------------------------------------


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = (
        "sync_type",
        "status_badge",
        "started_at",
        "finished_at",
        "get_duration",
        "records_fetched",
        "records_created",
        "records_updated",
        "records_errored",
    )
    list_filter = ("status", "sync_type", "started_at")
    search_fields = ("triggered_by", "=id")
    actions = ("rerun_failed_sync",)
    formfield_overrides = {
        models.JSONField: {"widget": PrettyJSONWidget(attrs={"rows": 16, "cols": 100})},
    }
    readonly_fields = (
        "id",
        "sync_type",
        "status",
        "started_at",
        "finished_at",
        "records_fetched",
        "records_created",
        "records_updated",
        "records_skipped",
        "records_errored",
        "formatted_error_detail",
        "triggered_by",
        "duration_seconds",
        "get_duration",
    )

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj: SyncLog) -> str:
        return _status_badge(obj.status)

    @admin.display(description="Error detail (pretty)")
    def formatted_error_detail(self, obj: SyncLog) -> str:
        formatted = json.dumps(
            obj.error_detail or {},
            indent=2,
            sort_keys=True,
            cls=DjangoJSONEncoder,
        )
        return format_html(
            '<pre style="max-width:960px;white-space:pre-wrap;'
            "background:var(--darkened-bg,#f8f8f8);"
            'border:1px solid var(--border-color,#ddd);border-radius:4px;padding:12px;">{}</pre>',
            formatted,
        )

    # ------------------------------------------------------------------
    # Permissions — read-only model; no add, no change; view & delete only
    # ------------------------------------------------------------------

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: SyncLog | None = None,
    ) -> bool:
        return False

    def has_view_permission(
        self,
        request: HttpRequest,
        obj: SyncLog | None = None,
    ) -> bool:
        return super().has_view_permission(request, obj)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: SyncLog | None = None,
    ) -> bool:
        return super().has_delete_permission(request, obj)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @admin.action(
        description="Rerun failed syncs (queues a new Celery task)",
        permissions=("view",),
    )
    def rerun_failed_sync(
        self,
        request: HttpRequest,
        queryset: models.QuerySet,
    ) -> None:
        failed_logs = queryset.filter(status=SyncLog.Status.FAILED)
        queued = 0
        triggered_by = request.user.get_username() or "admin"

        for sync_log in failed_logs:
            if sync_log.sync_type == SyncLog.SyncType.DELTA:
                sync_odoo_products_delta.delay(triggered_by=triggered_by)
            else:
                sync_odoo_products_full.delay(triggered_by=triggered_by)
            queued += 1

        level = messages.SUCCESS if queued else messages.WARNING
        self.message_user(
            request,
            f"Queued {queued} failed sync rerun(s).",
            level,
        )


# ---------------------------------------------------------------------------
# SyncConfigAdmin — singleton pattern
# ---------------------------------------------------------------------------


@admin.register(SyncConfig)
class SyncConfigAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "sync_interval_minutes",
        "full_sync_interval_hours",
        "batch_size",
        "auto_create_local_products",
        "conflict_resolution",
        "updated_at",
    )
    readonly_fields = ("id", "updated_at")
    formfield_overrides = {
        models.JSONField: {"widget": PrettyJSONWidget(attrs={"rows": 8, "cols": 100})},
    }

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Prevent creation of a second config row."""
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: SyncConfig | None = None,
    ) -> bool:
        """Prevent deletion of the singleton row."""
        return False

    def changelist_view(
        self,
        request: HttpRequest,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Skip the list page and jump straight to the singleton change form."""
        sync_config, _created = SyncConfig.objects.get_or_create(pk=1)
        return redirect(
            reverse(
                "admin:odoo_sync_syncconfig_change",
                args=(sync_config.pk,),
            )
        )


# ---------------------------------------------------------------------------
# Dashboard helpers
# ---------------------------------------------------------------------------


def _sync_log_payload(sync_log: SyncLog | None) -> dict[str, Any] | None:
    if sync_log is None:
        return None

    return {
        "id": str(sync_log.id),
        "sync_type": sync_log.sync_type,
        "status": sync_log.status,
        "started_at": sync_log.started_at,
        "finished_at": sync_log.finished_at,
        "duration": sync_log.get_duration(),
        "records_fetched": sync_log.records_fetched,
        "records_created": sync_log.records_created,
        "records_updated": sync_log.records_updated,
        "records_errored": sync_log.records_errored,
    }


def _dashboard_stats() -> dict[str, Any]:
    counts_by_status = dict(
        OdooProduct.objects.values_list("sync_status")
        .annotate(total=Count("id"))
        .order_by()
    )
    latest_sync = SyncLog.objects.order_by("-started_at").first()

    return {
        "latest_sync": _sync_log_payload(latest_sync),
        "stats": {
            "total": OdooProduct.objects.count(),
            "synced": counts_by_status.get(OdooProduct.SyncStatus.SYNCED, 0),
            "pending": counts_by_status.get(OdooProduct.SyncStatus.PENDING, 0),
            "conflict": counts_by_status.get(OdooProduct.SyncStatus.CONFLICT, 0),
            "error": counts_by_status.get(OdooProduct.SyncStatus.ERROR, 0),
        },
        "sync_logs": [
            _sync_log_payload(log)
            for log in SyncLog.objects.order_by("-started_at")[:10]
        ],
    }


# ---------------------------------------------------------------------------
# Dashboard views
# ---------------------------------------------------------------------------


@staff_member_required
def sync_dashboard_view(request: HttpRequest) -> HttpResponse:
    """Render the Odoo sync management dashboard."""
    context = {
        **admin.site.each_context(request),
        "title": "Odoo Sync Dashboard",
        "dashboard_stats_url": reverse("admin:odoo_sync_dashboard_stats"),
        "api_trigger_url": "/api/v1/odoo-sync/sync/trigger/",
        **_dashboard_stats(),
    }
    return render(request, "admin/odoo_sync/dashboard.html", context)


@staff_member_required
def sync_dashboard_stats_view(request: HttpRequest) -> JsonResponse:
    """Return current dashboard stats as JSON for client-side polling."""
    return JsonResponse(_dashboard_stats(), encoder=DjangoJSONEncoder)


# ---------------------------------------------------------------------------
# Inject custom URLs into the default admin site
# ---------------------------------------------------------------------------

_admin_get_urls_orig = admin.site.get_urls


def _get_odoo_sync_admin_urls():
    custom_urls = [
        path(
            "odoo-sync/dashboard/",
            admin.site.admin_view(sync_dashboard_view),
            name="odoo_sync_dashboard",
        ),
        path(
            "odoo-sync/dashboard/stats/",
            admin.site.admin_view(sync_dashboard_stats_view),
            name="odoo_sync_dashboard_stats",
        ),
    ]
    return custom_urls + _admin_get_urls_orig()


admin.site.get_urls = _get_odoo_sync_admin_urls
