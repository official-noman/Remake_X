"""Synchronous helpers for sending Odoo sync WebSocket events."""

from __future__ import annotations

import json
from typing import Any

import structlog
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from odoo_sync.consumers import SYNC_STATUS_GROUP
from odoo_sync.models import SyncLog
from odoo_sync.serializers import SyncLogSerializer

logger = structlog.get_logger(__name__)


def notify_sync_started(sync_log_id: str) -> None:
    """Broadcast that an Odoo sync run started."""
    sync_log = _serialize_sync_log(sync_log_id)
    _group_send(
        {
            "type": "sync.started",
            "sync_log": sync_log,
        }
    )


def notify_sync_progress(sync_log_id: str, processed: int, total: int) -> None:
    """Broadcast Odoo sync progress counters."""
    percent = round((processed / total) * 100, 2) if total else 0
    _group_send(
        {
            "type": "sync.progress",
            "sync_log_id": sync_log_id,
            "records_processed": processed,
            "total": total,
            "percent": percent,
        }
    )


def notify_sync_completed(sync_log_id: str) -> None:
    """Broadcast that an Odoo sync run completed."""
    sync_log = _serialize_sync_log(sync_log_id)
    summary = _sync_summary(sync_log_id)
    _group_send(
        {
            "type": "sync.completed",
            "sync_log": sync_log,
            "summary": summary,
        }
    )


def notify_sync_error(sync_log_id: str, message: str) -> None:
    """Broadcast that an Odoo sync run failed."""
    _group_send(
        {
            "type": "sync.error",
            "sync_log_id": sync_log_id,
            "message": message,
        }
    )


def _group_send(event: dict[str, Any]) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("odoo_sync_channel_layer_missing", event_type=event.get("type"))
        return

    async_to_sync(channel_layer.group_send)(SYNC_STATUS_GROUP, event)


def _serialize_sync_log(sync_log_id: str) -> dict[str, Any] | None:
    try:
        sync_log = SyncLog.objects.get(pk=sync_log_id)
    except SyncLog.DoesNotExist:
        logger.warning("odoo_sync_log_missing_for_ws", sync_log_id=sync_log_id)
        return None

    return _json_safe(SyncLogSerializer(sync_log).data)


def _sync_summary(sync_log_id: str) -> dict[str, Any]:
    try:
        sync_log = SyncLog.objects.get(pk=sync_log_id)
    except SyncLog.DoesNotExist:
        return {}

    return {
        "records_fetched": sync_log.records_fetched,
        "records_created": sync_log.records_created,
        "records_updated": sync_log.records_updated,
        "records_skipped": sync_log.records_skipped,
        "records_errored": sync_log.records_errored,
        "duration_seconds": sync_log.duration_seconds,
    }


def _json_safe(data: Any) -> Any:
    return json.loads(json.dumps(data, default=str))
