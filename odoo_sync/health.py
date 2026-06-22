"""Health check for Odoo connection."""

import time
from typing import Any

import structlog

from odoo_sync.connector import get_connector

logger = structlog.get_logger(__name__)


def check_odoo_connection() -> dict[str, Any]:
    """Check the connection to Odoo and return health status."""
    start_time = time.time()
    try:
        connector = get_connector()
        # authenticate will test the connection
        connector.authenticate()
        # call version on common endpoint
        version_info = connector._common.version()
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "ok",
            "latency_ms": latency_ms,
            "odoo_version": version_info.get("server_version", "unknown"),
        }
    except Exception as exc:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning("odoo_health_check_failed", error=str(exc))
        return {
            "status": "down",
            "latency_ms": latency_ms,
            "odoo_version": "unknown",
        }
