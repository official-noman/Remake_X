"""DRF serializers for Odoo synchronization APIs."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from odoo_sync.models import OdooProduct, SyncConfig, SyncLog


class LocalProductSummarySerializer(serializers.Serializer):
    """Small nested representation of the local product mapped to Odoo."""

    id = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    sku = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    quantity = serializers.IntegerField(read_only=True)

    def get_sku(self, obj: Any) -> str:
        return str(getattr(obj, "sku", "") or "")


class OdooProductSerializer(serializers.ModelSerializer):
    """Read-only serializer for synchronized Odoo product records."""

    local_product = LocalProductSummarySerializer(read_only=True)

    class Meta:
        model = OdooProduct
        fields = "__all__"

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        for field in fields.values():
            field.read_only = True
        return fields


class SyncLogSerializer(serializers.ModelSerializer):
    """Serializer for Odoo synchronization run logs."""

    get_duration = serializers.SerializerMethodField()

    class Meta:
        model = SyncLog
        fields = (
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
            "error_detail",
            "triggered_by",
            "duration_seconds",
            "get_duration",
        )

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        for field in fields.values():
            field.read_only = True
        return fields

    def get_get_duration(self, obj: SyncLog) -> str:
        return obj.get_duration()


class SyncConfigSerializer(serializers.ModelSerializer):
    """Writeable singleton configuration serializer for Odoo sync settings."""

    class Meta:
        model = SyncConfig
        fields = "__all__"
        read_only_fields = ("id", "updated_at")


class TriggerSyncSerializer(serializers.Serializer):
    """Input serializer for queueing manual Odoo sync jobs."""

    sync_type = serializers.ChoiceField(choices=("full", "delta"))
    triggered_by = serializers.CharField(required=False, allow_blank=True, max_length=128)

    def validate_triggered_by(self, value: str) -> str:
        return value.strip() or "manual"
