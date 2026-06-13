"""Shared pytest fixtures for odoo_sync tests."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIClient

from odoo_sync.models import OdooProduct, SyncConfig


# ---------------------------------------------------------------------------
# Connector singleton reset — runs before every test automatically
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_odoo_connector_singleton():
    """Reset the module-level connector singleton before and after each test."""
    import odoo_sync.connector as _mod
    with _mod._connector_lock:
        _mod._connector = None
    yield
    with _mod._connector_lock:
        _mod._connector = None


# ---------------------------------------------------------------------------
# Connector mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_connector():
    """Return a pre-configured MagicMock that mimics OdooConnector."""
    conn = MagicMock()
    conn.uid = 1
    conn.authenticate.return_value = 1

    # Default search_count → 2 records
    conn.get_product_count.return_value = 2

    # Default search_read → 2 products
    conn.search_read.return_value = [
        {
            "id": 1,
            "name": "Test Product 1",
            "default_code": "SKU001",
            "list_price": 10.0,
            "qty_available": 100.0,
            "active": True,
            "categ_id": [1, "Category 1"],
            "write_date": "2023-01-01 12:00:00",
        },
        {
            "id": 2,
            "name": "Test Product 2",
            "default_code": "SKU002",
            "list_price": 20.0,
            "qty_available": 50.0,
            "active": True,
            "categ_id": [1, "Category 1"],
            "write_date": "2023-01-02 12:00:00",
        },
    ]
    return conn


@pytest.fixture
def odoo_connector_mock(mock_connector):
    """Patch get_connector() in both tasks and views to return mock_connector."""
    with patch("odoo_sync.tasks.get_connector", return_value=mock_connector), \
         patch("odoo_sync.views.check_odoo_connection",
               return_value={"status": "ok", "latency_ms": 5, "odoo_version": "16.0"}):
        yield mock_connector


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_odoo_product_data():
    """Three realistic Odoo product dicts matching the OdooProduct field schema."""
    return [
        {
            "id": 101,
            "name": "Premium Widget",
            "default_code": "WGT-PRM",
            "list_price": 49.99,
            "qty_available": 150.0,
            "active": True,
            "categ_id": [12, "Widgets"],
            "write_date": "2023-10-01 10:00:00",
        },
        {
            "id": 102,
            "name": "Basic Widget",
            "default_code": "WGT-BSC",
            "list_price": 19.99,
            "qty_available": 500.0,
            "active": True,
            "categ_id": [12, "Widgets"],
            "write_date": "2023-10-02 11:30:00",
        },
        {
            "id": 103,
            "name": "Discontinued Widget",
            "default_code": "WGT-OLD",
            "list_price": 9.99,
            "qty_available": 0.0,
            "active": False,
            "categ_id": [12, "Widgets"],
            "write_date": "2023-09-15 08:00:00",
        },
    ]


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sync_config(db):
    """Return (or create) the singleton SyncConfig row."""
    config, _ = SyncConfig.objects.get_or_create(
        id=1,
        defaults={
            "sync_interval_minutes": 30,
            "full_sync_interval_hours": 24,
            "batch_size": 100,
            "auto_create_local_products": False,  # avoids Product FK issues in unit tests
            "conflict_resolution": SyncConfig.ConflictResolution.ODOO_WINS,
        },
    )
    return config


@pytest.fixture
def admin_user(db, django_user_model):
    """Return a staff/superuser."""
    return django_user_model.objects.create_user(
        username="admin",
        password="password123",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def api_client(admin_user):
    """Return a DRF APIClient force-authenticated as admin_user."""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


# ---------------------------------------------------------------------------
# Helper: create an OdooProduct with sensible defaults
# ---------------------------------------------------------------------------

def make_odoo_product(**kwargs):
    defaults = dict(
        odoo_id=1,
        odoo_name="Product",
        odoo_sku="SKU-001",
        odoo_price=Decimal("10.00"),
        odoo_qty_available=0.0,
    )
    defaults.update(kwargs)
    return OdooProduct.objects.create(**defaults)
