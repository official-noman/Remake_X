"""Database models for Odoo product synchronization."""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class OdooProduct(models.Model):
    """Stores Odoo product data and its optional local product mapping."""

    class SyncStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SYNCED = "SYNCED", "Synced"
        CONFLICT = "CONFLICT", "Conflict"
        ERROR = "ERROR", "Error"
        SKIPPED = "SKIPPED", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    odoo_id = models.PositiveIntegerField(unique=True, db_index=True)
    local_product = models.OneToOneField(
        "myapp.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="odoo_product",
    )
    odoo_name = models.CharField(max_length=512)
    odoo_sku = models.CharField(max_length=128, blank=True)
    odoo_price = models.DecimalField(max_digits=12, decimal_places=2)
    odoo_qty_available = models.FloatField(default=0)
    odoo_active = models.BooleanField(default=True)
    odoo_categ_id = models.PositiveIntegerField(null=True)
    odoo_categ_name = models.CharField(max_length=256, blank=True)
    raw_data = models.JSONField(default=dict)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(
        max_length=16,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
    )
    sync_error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_synced_at",)
        indexes = (
            models.Index(fields=("odoo_id",), name="odoo_product_odoo_id_idx"),
            models.Index(fields=("sync_status",), name="odoo_product_status_idx"),
            models.Index(fields=("last_synced_at",), name="odoo_product_synced_idx"),
        )

    def __str__(self) -> str:
        return f"{self.odoo_name} ({self.odoo_id})"


class SyncLog(models.Model):
    """Tracks each Odoo synchronization run."""

    class SyncType(models.TextChoices):
        FULL = "FULL", "Full"
        DELTA = "DELTA", "Delta"
        MANUAL = "MANUAL", "Manual"
        WEBHOOK = "WEBHOOK", "Webhook"

    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        PARTIAL = "PARTIAL", "Partial"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sync_type = models.CharField(max_length=16, choices=SyncType.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    records_fetched = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    records_skipped = models.PositiveIntegerField(default=0)
    records_errored = models.PositiveIntegerField(default=0)
    error_detail = models.JSONField(default=dict)
    triggered_by = models.CharField(max_length=128, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"{self.sync_type} sync - {self.status} - {self.started_at:%Y-%m-%d %H:%M:%S}"

    def save(self, *args: object, **kwargs: object) -> None:
        if self.started_at and self.finished_at:
            duration = self.finished_at - self.started_at
            self.duration_seconds = max(duration.total_seconds(), 0)

        super().save(*args, **kwargs)

    def get_duration(self) -> str:
        """Return the sync duration as a compact human-readable string."""
        seconds = int(self.duration_seconds or 0)

        if not seconds and self.started_at:
            end_time = self.finished_at or timezone.now()
            seconds = max(int((end_time - self.started_at).total_seconds()), 0)

        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def mark_finished(self, status: str) -> None:
        """Mark this sync log as finished and persist its final status.

        Args:
            status: Final sync status, usually one of ``Status`` choices.
        """
        self.status = status
        self.finished_at = timezone.now()
        self.save(update_fields=("status", "finished_at", "duration_seconds"))


class SyncConfig(models.Model):
    """Singleton configuration for Odoo sync behavior."""

    class ConflictResolution(models.TextChoices):
        ODOO_WINS = "ODOO_WINS", "Odoo wins"
        LOCAL_WINS = "LOCAL_WINS", "Local wins"
        MANUAL = "MANUAL", "Manual"

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    sync_interval_minutes = models.PositiveIntegerField(default=30)
    full_sync_interval_hours = models.PositiveIntegerField(default=24)
    batch_size = models.PositiveIntegerField(default=100)
    odoo_product_domain = models.JSONField(default=list)
    odoo_fields_to_sync = models.JSONField(default=list)
    auto_create_local_products = models.BooleanField(default=True)
    conflict_resolution = models.CharField(
        max_length=16,
        choices=ConflictResolution.choices,
        default=ConflictResolution.ODOO_WINS,
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return "Odoo Sync Configuration"

    def save(self, *args: object, **kwargs: object) -> None:
        self.pk = 1
        self.id = 1
        kwargs.pop("force_insert", None)

        if not SyncConfig.objects.filter(pk=1).exists():
            self._state.adding = True
        else:
            self._state.adding = False

        super().save(*args, **kwargs)
