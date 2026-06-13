"""Production Odoo XML-RPC connector service."""

from __future__ import annotations

import socket
import threading
import xmlrpc.client
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

import structlog
from django.conf import settings
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from odoo_sync.exceptions import OdooAuthError, OdooConnectionError

logger = structlog.get_logger(__name__)

_T = TypeVar("_T")
_connector: "OdooConnector | None" = None
_connector_lock = threading.Lock()


def _is_retryable_exception(exception: BaseException) -> bool:
    if isinstance(exception, (ConnectionError, TimeoutError, socket.timeout)):
        return True

    if isinstance(exception, xmlrpc.client.Fault):
        return exception.faultCode == 1

    return False


def _is_access_denied_fault(exception: BaseException) -> bool:
    if not isinstance(exception, xmlrpc.client.Fault):
        return False

    fault_text = exception.faultString.lower()
    return "accessdenied" in fault_text or "access denied" in fault_text


def _retry_log_context(retry_state: RetryCallState) -> dict[str, Any]:
    kwargs = retry_state.kwargs
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    return {
        "attempt_number": retry_state.attempt_number,
        "error_type": type(exception).__name__ if exception else None,
        "model": kwargs.get("log_model"),
        "method": kwargs.get("log_method"),
    }


def _log_retry_attempt(retry_state: RetryCallState) -> None:
    logger.warning("odoo_xmlrpc_retry", **_retry_log_context(retry_state))


def _wrap_connection_errors(
    operation: Callable[..., _T],
    *,
    log_model: str | None,
    log_method: str,
    **kwargs: Any,
) -> _T:
    try:
        return operation(log_model=log_model, log_method=log_method, **kwargs)
    except (ConnectionError, TimeoutError, socket.timeout, xmlrpc.client.Fault) as exc:
        raise OdooConnectionError(
            f"Odoo XML-RPC call failed after retries: "
            f"model={log_model or 'n/a'}, method={log_method}"
        ) from exc


class OdooConnector:
    """XML-RPC connector for Odoo 16/17."""

    def __init__(self) -> None:
        """Initialize XML-RPC endpoints and read Odoo credentials from settings."""
        self.url: str = settings.ODOO_URL.rstrip("/")
        self.db: str = settings.ODOO_DB
        self.username: str = settings.ODOO_USERNAME
        self.password: str = settings.ODOO_PASSWORD
        self.uid: int | None = None
        self._auth_lock = threading.Lock()

        self._common = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common",
            allow_none=True,
        )
        self._object = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/object",
            allow_none=True,
        )
        
        # Apply a global socket timeout for XML-RPC calls
        socket.setdefaulttimeout(10.0)

    @retry(
        retry=retry_if_exception(_is_retryable_exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1),
        before_sleep=_log_retry_attempt,
        reraise=True,
    )
    def _authenticate_once(
        self,
        *,
        log_model: str | None,
        log_method: str,
    ) -> int | bool:
        return self._common.authenticate(
            self.db,
            self.username,
            self.password,
            {},
        )

    @retry(
        retry=retry_if_exception(_is_retryable_exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1),
        before_sleep=_log_retry_attempt,
        reraise=True,
    )
    def _execute_kw_once(
        self,
        *,
        log_model: str | None,
        log_method: str,
        model: str,
        method: str,
        args: Sequence[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        return self._object.execute_kw(
            self.db,
            self._get_uid(),
            self.password,
            model,
            method,
            list(args),
            kwargs or {},
        )

    def _get_uid(self) -> int:
        if self.uid is None:
            return self.authenticate()

        return self.uid

    def _clear_uid(self) -> None:
        with self._auth_lock:
            self.uid = None

    def authenticate(self) -> int:
        """Authenticate with Odoo and cache the returned user ID.

        Returns:
            The authenticated Odoo user ID.

        Raises:
            OdooAuthError: If Odoo rejects the configured credentials.
            OdooConnectionError: If authentication cannot reach Odoo after retries.
        """
        if self.uid is not None:
            return self.uid

        with self._auth_lock:
            if self.uid is not None:
                return self.uid

            uid = _wrap_connection_errors(
                self._authenticate_once,
                log_model="auth",
                log_method="authenticate",
            )

            if not uid:
                raise OdooAuthError(
                    "Odoo authentication failed. Check ODOO_DB, "
                    "ODOO_USERNAME, and ODOO_PASSWORD."
                )

            self.uid = int(uid)
            return self.uid

    def execute(
        self,
        model: str,
        method: str,
        domain: Sequence[Any] | None = None,
        fields: Sequence[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> Any:
        """Execute an Odoo model method through XML-RPC.

        Args:
            model: Odoo model name, such as ``product.template``.
            method: Odoo model method, such as ``search_read``.
            domain: Odoo domain filters.
            fields: Field names to return for methods that accept fields.
            limit: Maximum number of records to return.
            offset: Number of matching records to skip.

        Returns:
            The decoded XML-RPC response from Odoo.

        Raises:
            OdooAuthError: If re-authentication fails after access is denied.
            OdooConnectionError: If the XML-RPC call fails after retries.
        """
        execute_kwargs: dict[str, Any] = {}
        if fields is not None:
            execute_kwargs["fields"] = list(fields)
        if limit is not None:
            execute_kwargs["limit"] = limit
        if offset:
            execute_kwargs["offset"] = offset

        args: list[Any] = [list(domain or [])]

        try:
            return _wrap_connection_errors(
                self._execute_kw_once,
                log_model=model,
                log_method=method,
                model=model,
                method=method,
                args=args,
                kwargs=execute_kwargs,
            )
        except OdooConnectionError as exc:
            if not _is_access_denied_fault(exc.__cause__):
                raise

            self._clear_uid()
            self.authenticate()
            return _wrap_connection_errors(
                self._execute_kw_once,
                log_model=model,
                log_method=method,
                model=model,
                method=method,
                args=args,
                kwargs=execute_kwargs,
            )

    def search_read(
        self,
        model: str,
        domain: Sequence[Any] | None = None,
        fields: Sequence[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Search and read Odoo records in one XML-RPC call.

        Args:
            model: Odoo model name to query.
            domain: Odoo domain filters.
            fields: Field names to include in the result.
            limit: Maximum number of records to return.
            offset: Number of matching records to skip.

        Returns:
            A list of Odoo records represented as dictionaries.
        """
        result = self.execute(
            model=model,
            method="search_read",
            domain=domain,
            fields=fields,
            limit=limit,
            offset=offset,
        )
        return list(result)

    def get_product_count(self, domain: Sequence[Any] | None = None) -> int:
        """Return the number of Odoo product templates matching a domain.

        Args:
            domain: Odoo domain filters.

        Returns:
            Count of matching ``product.template`` records.
        """
        result = self.execute(
            model="product.template",
            method="search_count",
            domain=domain,
            fields=None,
            limit=None,
            offset=0,
        )
        return int(result)


def get_connector() -> OdooConnector:
    """Return a process-local singleton Odoo connector instance.

    Returns:
        A thread-safe singleton ``OdooConnector`` instance.
    """
    global _connector

    if _connector is None:
        with _connector_lock:
            if _connector is None:
                _connector = OdooConnector()

    return _connector
