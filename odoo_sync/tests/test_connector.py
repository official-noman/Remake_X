"""Tests for the Odoo XML-RPC connector."""

from __future__ import annotations

import socket
import xmlrpc.client
from unittest.mock import MagicMock, patch

import pytest

from odoo_sync.connector import OdooConnector
from odoo_sync.exceptions import OdooAuthError, OdooConnectionError
from odoo_sync.tasks import _map_odoo_to_model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_connector_with_mocks():
    """Create an OdooConnector with both XML-RPC endpoints replaced by Mocks."""
    with patch("odoo_sync.connector.xmlrpc.client.ServerProxy"):
        conn = OdooConnector()
    conn._common = MagicMock()
    conn._object = MagicMock()
    return conn


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------

def test_authentication_success():
    """Successful authentication stores the uid returned by Odoo."""
    conn = _make_connector_with_mocks()
    conn._common.authenticate.return_value = 7

    uid = conn.authenticate()

    assert uid == 7
    assert conn.uid == 7
    conn._common.authenticate.assert_called_once()


def test_authentication_failure_raises_odoo_auth_error():
    """If Odoo returns falsy uid, OdooAuthError is raised."""
    conn = _make_connector_with_mocks()
    conn._common.authenticate.return_value = False

    with pytest.raises(OdooAuthError, match="Odoo authentication failed"):
        conn.authenticate()


def test_authentication_retries_exactly_3_times_on_timeout():
    """A socket.timeout causes exactly 3 retry attempts before giving up."""
    conn = _make_connector_with_mocks()
    conn._common.authenticate.side_effect = socket.timeout("timed out")

    with pytest.raises(OdooConnectionError):
        conn.authenticate()

    assert conn._common.authenticate.call_count == 3


def test_authentication_raises_connection_error_after_retries():
    """ConnectionError is wrapped in OdooConnectionError after 3 attempts."""
    conn = _make_connector_with_mocks()
    conn._common.authenticate.side_effect = ConnectionError("network down")

    with pytest.raises(OdooConnectionError, match="Odoo XML-RPC call failed after retries"):
        conn.authenticate()


def test_re_authentication_on_access_denied_fault():
    """An AccessDenied XML-RPC fault triggers uid clear + re-authenticate + retry."""
    conn = _make_connector_with_mocks()
    conn.uid = 1  # already "authenticated"
    conn._common.authenticate.return_value = 1

    access_denied = xmlrpc.client.Fault(2, "Access denied")
    good_result = [{"id": 99}]
    conn._object.execute_kw.side_effect = [access_denied, good_result]

    result = conn.execute(model="res.partner", method="search_read")

    assert result == good_result
    conn._common.authenticate.assert_called_once()
    assert conn._object.execute_kw.call_count == 2


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_get_connector_returns_singleton():
    """get_connector() returns the same instance on every call."""
    from odoo_sync.connector import get_connector

    with patch("odoo_sync.connector.xmlrpc.client.ServerProxy"):
        c1 = get_connector()
        c2 = get_connector()

    assert c1 is c2


# ---------------------------------------------------------------------------
# _map_odoo_to_model
# ---------------------------------------------------------------------------

def test_map_many2one_field():
    """Many2One [id, name] list is unpacked into categ_id and categ_name."""
    record = {
        "id": 10,
        "name": "Widget",
        "default_code": "WGT",
        "list_price": 99.99,
        "qty_available": 5.0,
        "active": True,
        "categ_id": [42, "Hardware"],
    }
    mapped = _map_odoo_to_model(record)

    assert mapped["odoo_categ_id"] == 42
    assert mapped["odoo_categ_name"] == "Hardware"


def test_map_false_fields_handled_gracefully():
    """Odoo False (null) values produce empty strings / 0 without raising."""
    record = {
        "id": 10,
        "name": False,
        "default_code": False,
        "list_price": False,
        "qty_available": False,
        "active": False,
        "categ_id": False,
    }
    mapped = _map_odoo_to_model(record)

    # str(False or "") → ""
    assert mapped["odoo_name"] == ""
    assert mapped["odoo_sku"] == ""
    assert mapped["odoo_price"] == 0
    assert mapped["odoo_qty_available"] == 0.0
    assert mapped["odoo_active"] is False
    assert mapped["odoo_categ_id"] is None
    assert mapped["odoo_categ_name"] == ""
