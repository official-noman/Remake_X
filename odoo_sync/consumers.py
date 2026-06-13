"""WebSocket consumers for live Odoo sync status updates."""

from __future__ import annotations

import json
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from odoo_sync.models import SyncLog
from odoo_sync.serializers import SyncLogSerializer

SYNC_STATUS_GROUP = "sync_status"


class SyncStatusConsumer(AsyncWebsocketConsumer):
    """Broadcast live Odoo synchronization status to authenticated staff users."""

    async def connect(self) -> None:
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not user.is_staff:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(SYNC_STATUS_GROUP, self.channel_name)
        await self.accept()
        await self.send_latest_status()

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(SYNC_STATUS_GROUP, self.channel_name)

    async def receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
    ) -> None:
        if not text_data:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json(
                {
                    "type": "sync_error",
                    "message": "Invalid JSON payload.",
                    "sync_log_id": "",
                }
            )
            return

        if payload.get("action") == "get_latest":
            await self.send_latest_status()

    async def sync_started(self, event: dict[str, Any]) -> None:
        await self.send_json(
            {
                "type": "sync_started",
                "sync_log": event.get("sync_log"),
            }
        )

    async def sync_progress(self, event: dict[str, Any]) -> None:
        await self.send_json(
            {
                "type": "sync_progress",
                "records_processed": event.get("records_processed", 0),
                "total": event.get("total", 0),
                "percent": event.get("percent", 0),
            }
        )

    async def sync_completed(self, event: dict[str, Any]) -> None:
        await self.send_json(
            {
                "type": "sync_completed",
                "sync_log": event.get("sync_log"),
                "summary": event.get("summary"),
            }
        )

    async def sync_error(self, event: dict[str, Any]) -> None:
        await self.send_json(
            {
                "type": "sync_error",
                "message": event.get("message", ""),
                "sync_log_id": event.get("sync_log_id", ""),
            }
        )

    async def send_latest_status(self) -> None:
        sync_log = await _get_latest_sync_log()
        await self.send_json(
            {
                "type": "sync_latest",
                "sync_log": sync_log,
            }
        )

    async def send_json(self, payload: dict[str, Any]) -> None:
        await self.send(text_data=json.dumps(payload, default=str))


@database_sync_to_async
def _get_latest_sync_log() -> dict[str, Any] | None:
    sync_log = SyncLog.objects.order_by("-started_at").first()
    if sync_log is None:
        return None

    return json.loads(json.dumps(SyncLogSerializer(sync_log).data, default=str))
