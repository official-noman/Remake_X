"""Celery tasks for synchronizing products from Odoo."""

from __future__ import annotations

from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from celery import shared_task
from django.apps import apps
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from odoo_sync.connector import get_connector
from odoo_sync.models import OdooProduct, SyncConfig, SyncLog
from odoo_sync.ws_utils import (
    notify_sync_completed,
    notify_sync_error,
    notify_sync_progress,
    notify_sync_started,
)

logger = structlog.get_logger(__name__)

DEFAULT_ODOO_PRODUCT_FIELDS = [
    "id",
    "name",
    "default_code",
    "list_price",
    "qty_available",
    "active",
    "categ_id",
    "write_date",
]


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_odoo_products_full(
    self: Any,
    triggered_by: str = "celery-beat",
    sync_log_id: str | None = None,
) -> str:
    """Run a complete Odoo product synchronization."""
    return _run_product_sync(
        task=self,
        sync_type=SyncLog.SyncType.FULL,
        triggered_by=triggered_by,
        sync_log_id=sync_log_id,
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_odoo_products_delta(
    self: Any,
    triggered_by: str = "celery-beat",
    sync_log_id: str | None = None,
) -> str:
    """Run an incremental Odoo product synchronization."""
    last_sync = (
        SyncLog.objects.filter(
            status=SyncLog.Status.SUCCESS,
            finished_at__isnull=False,
        )
        .order_by("-finished_at")
        .first()
    )

    if last_sync is None:
        logger.info("odoo_delta_sync_falling_back_to_full", triggered_by=triggered_by)
        return _run_product_sync(
            task=self,
            sync_type=SyncLog.SyncType.FULL,
            triggered_by=triggered_by,
            sync_log_id=sync_log_id,
        )

    return _run_product_sync(
        task=self,
        sync_type=SyncLog.SyncType.DELTA,
        triggered_by=triggered_by,
        delta_since=last_sync.finished_at,
        sync_log_id=sync_log_id,
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_odoo_products_by_ids(
    self: Any,
    odoo_ids: list[int],
    triggered_by: str = "admin",
) -> str:
    """Re-fetch a selected set of Odoo products by Odoo record ID."""
    sync_log = SyncLog.objects.create(
        sync_type=SyncLog.SyncType.MANUAL,
        status=SyncLog.Status.RUNNING,
        triggered_by=triggered_by,
    )
    sync_log_id = str(sync_log.id)
    notify_sync_started(sync_log_id)

    try:
        try:
            config, _created = SyncConfig.objects.get_or_create(pk=1)
            fields = config.odoo_fields_to_sync or DEFAULT_ODOO_PRODUCT_FIELDS
            records = get_connector().search_read(
                model="product.template",
                domain=[["id", "in", odoo_ids]],
                fields=fields,
                limit=max(len(odoo_ids), 1),
                offset=0,
            )
            SyncLog.objects.filter(pk=sync_log.pk).update(records_fetched=len(records))
            _process_product_batch(records, sync_log, config)
            notify_sync_progress(sync_log_id, len(records), len(odoo_ids))

            sync_log.refresh_from_db()
            final_status = (
                SyncLog.Status.PARTIAL
                if sync_log.records_errored > 0
                else SyncLog.Status.SUCCESS
            )
            sync_log.mark_finished(final_status)
            notify_sync_completed(sync_log_id)
            return sync_log_id
        except Exception as exc:
            logger.exception(
                "odoo_selected_product_sync_failed",
                sync_log_id=sync_log_id,
                error_type=type(exc).__name__,
            )
            sync_log.error_detail = {
                "unhandled": {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "timestamp": timezone.now().isoformat(),
                }
            }
            sync_log.save(update_fields=("error_detail",))
            sync_log.mark_finished(SyncLog.Status.FAILED)
            notify_sync_error(sync_log_id, str(exc))

            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc)

            raise
    finally:
        sync_log.refresh_from_db()
        if sync_log.status == SyncLog.Status.RUNNING:
            sync_log.mark_finished(SyncLog.Status.FAILED)
            notify_sync_error(sync_log_id, "Task aborted unexpectedly.")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def trigger_manual_sync(
    self: Any,
    sync_type: str = "full",
    triggered_by: str = "manual",
) -> str:
    """Trigger a manual full or delta sync and return the created SyncLog ID."""
    normalized_sync_type = sync_type.lower().strip()
    logger.info(
        "odoo_manual_sync_triggered",
        sync_type=normalized_sync_type,
        triggered_by=triggered_by,
    )

    if normalized_sync_type == "delta":
        result = sync_odoo_products_delta.apply(kwargs={"triggered_by": triggered_by})
    elif normalized_sync_type == "full":
        result = sync_odoo_products_full.apply(kwargs={"triggered_by": triggered_by})
    else:
        raise ValueError("sync_type must be either 'full' or 'delta'.")

    return str(result.get(propagate=True))


def _run_product_sync(
    *,
    task: Any,
    sync_type: str,
    triggered_by: str,
    delta_since: datetime | None = None,
    sync_log_id: str | None = None,
) -> str:
    if sync_log_id:
        sync_log = SyncLog.objects.get(pk=sync_log_id)
        sync_log.sync_type = sync_type
        sync_log.status = SyncLog.Status.RUNNING
        sync_log.triggered_by = triggered_by
        sync_log.finished_at = None
        sync_log.duration_seconds = None
        sync_log.save(
            update_fields=(
                "sync_type",
                "status",
                "triggered_by",
                "finished_at",
                "duration_seconds",
            )
        )
    else:
        sync_log = SyncLog.objects.create(
            sync_type=sync_type,
            status=SyncLog.Status.RUNNING,
            triggered_by=triggered_by,
        )
    sync_log_id = str(sync_log.id)

    logger.info(
        "odoo_product_sync_started",
        sync_log_id=sync_log_id,
        sync_type=sync_type,
        triggered_by=triggered_by,
        delta_since=delta_since.isoformat() if delta_since else None,
    )

    try:
        try:
            config, _created = SyncConfig.objects.get_or_create(pk=1)
            batch_size = max(config.batch_size, 1)
            fields = config.odoo_fields_to_sync or DEFAULT_ODOO_PRODUCT_FIELDS
            domain = list(config.odoo_product_domain or [])

            if delta_since is not None:
                domain.append(["write_date", ">=", _format_odoo_datetime(delta_since)])

            connector = get_connector()
            total_records = connector.get_product_count(domain)
            offset = 0
            processed_records = 0

            notify_sync_started(sync_log_id)

            while True:
                records = connector.search_read(
                    model="product.template",
                    domain=domain,
                    fields=fields,
                    limit=batch_size,
                    offset=offset,
                )

                if not records:
                    break

                SyncLog.objects.filter(pk=sync_log.pk).update(
                    records_fetched=F("records_fetched") + len(records)
                )
                _process_product_batch(records, sync_log, config)
                processed_records += len(records)
                notify_sync_progress(sync_log_id, processed_records, total_records)

                if len(records) < batch_size:
                    break

                offset += batch_size

            sync_log.refresh_from_db()
            final_status = (
                SyncLog.Status.PARTIAL
                if sync_log.records_errored > 0
                else SyncLog.Status.SUCCESS
            )
            sync_log.mark_finished(final_status)
            notify_sync_completed(sync_log_id)

            logger.info(
                "odoo_product_sync_finished",
                sync_log_id=sync_log_id,
                sync_type=sync_type,
                status=final_status,
                records_fetched=sync_log.records_fetched,
                records_created=sync_log.records_created,
                records_updated=sync_log.records_updated,
                records_skipped=sync_log.records_skipped,
                records_errored=sync_log.records_errored,
                duration_seconds=sync_log.duration_seconds,
            )
            return sync_log_id

        except Exception as exc:
            logger.exception(
                "odoo_product_sync_failed",
                sync_log_id=sync_log_id,
                sync_type=sync_type,
                error_type=type(exc).__name__,
            )
            sync_log.error_detail = {
                "unhandled": {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "timestamp": timezone.now().isoformat(),
                }
            }
            sync_log.save(update_fields=("error_detail",))
            sync_log.mark_finished(SyncLog.Status.FAILED)
            notify_sync_error(sync_log_id, str(exc))

            if task.request.retries < task.max_retries:
                raise task.retry(exc=exc)

            raise
    finally:
        sync_log.refresh_from_db()
        if sync_log.status == SyncLog.Status.RUNNING:
            sync_log.mark_finished(SyncLog.Status.FAILED)
            notify_sync_error(sync_log_id, "Task aborted unexpectedly.")


def _process_product_batch(
    records: list[dict[str, Any]],
    sync_log: SyncLog,
    config: SyncConfig,
) -> None:
    """Process one batch of Odoo product records."""
    now = timezone.now()
    record_ids = [record.get("id") for record in records if record.get("id") is not None]
    existing_products = {
        product.odoo_id: product
        for product in OdooProduct.objects.select_related("local_product").filter(
            odoo_id__in=record_ids
        )
    }

    products_to_create: list[OdooProduct] = []
    products_to_update: list[OdooProduct] = []
    local_products_to_update: list[Any] = []

    for record in records:
        odoo_id = record.get("id")

        try:
            if odoo_id is None:
                raise ValueError("Odoo product record is missing required field 'id'.")

            mapped_data = _map_odoo_to_model(record)
            existing = existing_products.get(int(odoo_id))

            if existing is None:
                local_product = None
                if config.auto_create_local_products:
                    local_product = _build_local_product(mapped_data, record)

                products_to_create.append(
                    OdooProduct(
                        **mapped_data,
                        local_product=local_product,
                        last_synced_at=now,
                        sync_status=OdooProduct.SyncStatus.SYNCED,
                    )
                )
                _increment_sync_counter(sync_log, "records_created")
                continue

            conflict = _has_local_odoo_conflict(existing, mapped_data)
            local_product_updated = False

            if conflict and config.conflict_resolution == SyncConfig.ConflictResolution.MANUAL:
                sync_status = OdooProduct.SyncStatus.CONFLICT
                sync_error_message = "Local product and Odoo product changed since last sync."
                _increment_sync_counter(sync_log, "records_skipped")
            else:
                sync_status = OdooProduct.SyncStatus.SYNCED
                sync_error_message = ""
                _increment_sync_counter(sync_log, "records_updated")

                if (
                    conflict
                    and config.conflict_resolution
                    == SyncConfig.ConflictResolution.ODOO_WINS
                    and existing.local_product is not None
                ):
                    local_product_updated = _apply_odoo_values_to_local_product(
                        existing.local_product,
                        mapped_data,
                    )

            for field_name, value in mapped_data.items():
                setattr(existing, field_name, value)

            existing.last_synced_at = now
            existing.sync_status = sync_status
            existing.sync_error_message = sync_error_message
            existing.updated_at = now
            products_to_update.append(existing)

            if local_product_updated:
                local_products_to_update.append(existing.local_product)

        except Exception as exc:
            logger.exception(
                "odoo_product_record_sync_failed",
                sync_log_id=str(sync_log.id),
                odoo_id=odoo_id,
                error_type=type(exc).__name__,
            )
            _record_sync_error(sync_log, odoo_id, exc)

    if products_to_create:
        _bulk_create_odoo_products(products_to_create, sync_log, config.batch_size)

    if products_to_update:
        OdooProduct.objects.bulk_update(
            products_to_update,
            fields=[
                "odoo_name",
                "odoo_sku",
                "odoo_price",
                "odoo_qty_available",
                "odoo_active",
                "odoo_categ_id",
                "odoo_categ_name",
                "raw_data",
                "last_synced_at",
                "sync_status",
                "sync_error_message",
                "updated_at",
            ],
            batch_size=config.batch_size,
        )

    _bulk_update_local_products(local_products_to_update, config.batch_size)


def _map_odoo_to_model(odoo_record: dict[str, Any]) -> dict[str, Any]:
    """Map an Odoo product record into OdooProduct model fields."""
    categ_id, categ_name = _parse_many2one(odoo_record.get("categ_id"))

    return {
        "odoo_id": int(odoo_record["id"]),
        "odoo_name": str(odoo_record.get("name") or ""),
        "odoo_sku": str(odoo_record.get("default_code") or ""),
        "odoo_price": _to_decimal(odoo_record.get("list_price")),
        "odoo_qty_available": float(odoo_record.get("qty_available") or 0),
        "odoo_active": bool(odoo_record.get("active", True)),
        "odoo_categ_id": categ_id,
        "odoo_categ_name": categ_name,
        "raw_data": odoo_record,
    }


def _format_odoo_datetime(value: datetime) -> str:
    if timezone.is_aware(value):
        value = value.astimezone(datetime_timezone.utc).replace(tzinfo=None)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse_many2one(value: Any) -> tuple[int | None, str]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return int(value[0]), str(value[1] or "")

    if isinstance(value, int) and not isinstance(value, bool):
        return value, ""

    return None, ""


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _increment_sync_counter(sync_log: SyncLog, field_name: str, amount: int = 1) -> None:
    SyncLog.objects.filter(pk=sync_log.pk).update(**{field_name: F(field_name) + amount})


def _decrement_sync_counter(sync_log: SyncLog, field_name: str, amount: int = 1) -> None:
    SyncLog.objects.filter(pk=sync_log.pk).update(**{field_name: F(field_name) - amount})


def _bulk_create_odoo_products(
    products: list[OdooProduct],
    sync_log: SyncLog,
    batch_size: int,
) -> None:
    try:
        OdooProduct.objects.bulk_create(products, batch_size=batch_size)
        return
    except Exception as exc:
        logger.exception(
            "odoo_product_bulk_create_failed",
            sync_log_id=str(sync_log.id),
            product_count=len(products),
            error_type=type(exc).__name__,
        )

    for product in products:
        try:
            product.save()
        except Exception as exc:
            logger.exception(
                "odoo_product_create_failed",
                sync_log_id=str(sync_log.id),
                odoo_id=product.odoo_id,
                error_type=type(exc).__name__,
            )
            _decrement_sync_counter(sync_log, "records_created")
            _record_sync_error(sync_log, product.odoo_id, exc)


def _record_sync_error(sync_log: SyncLog, odoo_id: Any, exc: Exception) -> None:
    _increment_sync_counter(sync_log, "records_errored")

    key = str(odoo_id or "unknown")
    with transaction.atomic():
        locked_log = SyncLog.objects.select_for_update().get(pk=sync_log.pk)
        error_detail = dict(locked_log.error_detail or {})
        error_detail[key] = {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "timestamp": timezone.now().isoformat(),
        }
        locked_log.error_detail = error_detail
        locked_log.save(update_fields=("error_detail",))


def _has_local_odoo_conflict(
    existing: OdooProduct,
    mapped_data: dict[str, Any],
) -> bool:
    local_product = existing.local_product
    if local_product is None:
        return False

    odoo_price_changed = Decimal(mapped_data["odoo_price"]) != existing.odoo_price
    odoo_qty_changed = mapped_data["odoo_qty_available"] != existing.odoo_qty_available

    local_price_changed = (
        hasattr(local_product, "price")
        and Decimal(local_product.price) != existing.odoo_price
    )
    local_qty_changed = (
        hasattr(local_product, "quantity")
        and float(local_product.quantity) != existing.odoo_qty_available
    )

    return (odoo_price_changed and local_price_changed) or (
        odoo_qty_changed and local_qty_changed
    )


def _apply_odoo_values_to_local_product(
    local_product: Any,
    mapped_data: dict[str, Any],
) -> bool:
    updated = False

    if hasattr(local_product, "name"):
        local_product.name = mapped_data["odoo_name"][:255]
        updated = True
    if hasattr(local_product, "sku"):
        local_product.sku = mapped_data["odoo_sku"]
        updated = True
    if hasattr(local_product, "price"):
        local_product.price = mapped_data["odoo_price"]
        updated = True
    if hasattr(local_product, "quantity"):
        local_product.quantity = max(int(mapped_data["odoo_qty_available"]), 0)
        updated = True
    if hasattr(local_product, "status"):
        local_product.status = "active" if mapped_data["odoo_active"] else "inactive"
        updated = True

    return updated


def _build_local_product(
    mapped_data: dict[str, Any],
    raw_record: dict[str, Any],
) -> Any | None:
    product_model = OdooProduct._meta.get_field("local_product").remote_field.model
    field_values = _candidate_local_product_values(mapped_data, raw_record)
    create_kwargs: dict[str, Any] = {}

    for field in product_model._meta.concrete_fields:
        if field.primary_key or getattr(field, "auto_created", False):
            continue
        if field.name in field_values:
            create_kwargs[field.name] = field_values[field.name]
        elif not _field_can_be_omitted(field):
            logger.warning(
                "odoo_local_product_create_skipped",
                missing_required_field=field.name,
                product_model=product_model._meta.label,
                odoo_id=mapped_data["odoo_id"],
            )
            return None

    if "category" in create_kwargs:
        create_kwargs["category"] = _coerce_category_value(
            product_model,
            create_kwargs["category"],
        )
        if create_kwargs["category"] is None:
            logger.warning(
                "odoo_local_product_create_skipped",
                missing_required_field="category",
                product_model=product_model._meta.label,
                odoo_id=mapped_data["odoo_id"],
            )
            return None

    if not create_kwargs:
        return None

    local_product = product_model.objects.create(**create_kwargs)
    logger.info(
        "odoo_local_product_created",
        product_model=product_model._meta.label,
        local_product_id=str(local_product.pk),
        odoo_id=mapped_data["odoo_id"],
    )
    return local_product


def _candidate_local_product_values(
    mapped_data: dict[str, Any],
    raw_record: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": mapped_data["odoo_name"][:255],
        "description": raw_record.get("description_sale")
        or raw_record.get("description")
        or mapped_data["odoo_name"],
        "sku": mapped_data["odoo_sku"],
        "price": mapped_data["odoo_price"],
        "quantity": max(int(mapped_data["odoo_qty_available"]), 0),
        "status": "active" if mapped_data["odoo_active"] else "inactive",
        "category": mapped_data["odoo_categ_name"] or "other",
    }


def _field_can_be_omitted(field: Any) -> bool:
    return (
        field.blank
        or field.null
        or field.has_default()
        or getattr(field, "auto_now", False)
        or getattr(field, "auto_now_add", False)
    )


def _coerce_category_value(product_model: Any, value: str) -> Any:
    field = product_model._meta.get_field("category")

    if getattr(field, "remote_field", None) and field.remote_field:
        category_model = field.remote_field.model
        name_field = "name" if _model_has_field(category_model, "name") else None
        if name_field is None:
            return None
        category, _created = category_model.objects.get_or_create(
            **{name_field: value or "Odoo"}
        )
        return category

    choices = getattr(field, "choices", None)
    if choices:
        valid_values = {choice_value for choice_value, _label in choices}
        if value in valid_values:
            return value
        if "other" in valid_values:
            return "other"
        return next(iter(valid_values))

    return value


def _model_has_field(model: Any, field_name: str) -> bool:
    return any(field.name == field_name for field in model._meta.fields)


def _bulk_update_local_products(
    local_products: list[Any],
    batch_size: int,
) -> None:
    if not local_products:
        return

    product_model = apps.get_model(
        local_products[0]._meta.app_label,
        local_products[0]._meta.model_name,
    )
    fields = [
        field_name
        for field_name in ("name", "sku", "price", "quantity", "status")
        if _model_has_field(product_model, field_name)
    ]

    if fields:
        product_model.objects.bulk_update(local_products, fields=fields, batch_size=batch_size)
