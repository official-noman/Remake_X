"""Custom exceptions for Odoo synchronization."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


class OdooSyncError(Exception):
    """Base exception for all Odoo sync-related errors."""


class OdooAuthError(OdooSyncError):
    """Raised when Odoo authentication fails."""


class OdooConnectionError(OdooSyncError):
    """Raised when an Odoo XML-RPC call fails after retries are exhausted."""


def problem_detail_exception_handler(
    exc: Exception,
    context: dict[str, Any],
) -> Response | None:
    """Format DRF exceptions as RFC 7807 Problem Details."""
    response = exception_handler(exc, context)
    if response is None:
        return None

    request = context.get("request")
    status_code = response.status_code
    title = _status_title(status_code)
    detail = _stringify_detail(response.data)

    response.data = {
        "type": f"https://httpstatuses.com/{status_code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.path if request else "",
    }
    response.content_type = "application/problem+json"
    return response


def _status_title(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def _stringify_detail(data: Any) -> str:
    if isinstance(data, dict):
        if "detail" in data:
            return _stringify_detail(data["detail"])
        return "; ".join(
            f"{key}: {_stringify_detail(value)}" for key, value in data.items()
        )

    if isinstance(data, list):
        return "; ".join(_stringify_detail(item) for item in data)

    return str(data)
