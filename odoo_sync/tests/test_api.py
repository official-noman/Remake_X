"""Tests for the DRF API endpoints."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from odoo_sync.models import OdooProduct, SyncLog
from odoo_sync.tests.conftest import make_odoo_product


@pytest.fixture
def anon_client():
    return APIClient()


# ---------------------------------------------------------------------------
# Authentication / authorisation guards
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_products_list_requires_auth(anon_client):
    response = anon_client.get("/api/v1/odoo-sync/products/")
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.django_db
def test_logs_list_requires_auth(anon_client):
    response = anon_client.get("/api/v1/odoo-sync/logs/")
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.django_db
def test_trigger_requires_auth(anon_client):
    response = anon_client.post("/api/v1/odoo-sync/sync/trigger/", {"sync_type": "full"})
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.django_db
def test_trigger_requires_admin(db, django_user_model):
    """Non-staff users get 403 on the trigger endpoint."""
    user = django_user_model.objects.create_user(username="plain", password="pw")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post("/api/v1/odoo-sync/sync/trigger/", {"sync_type": "full"})
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_products_list_returns_paginated_results(api_client, sample_odoo_product_data):
    """GET /products/ returns all products with cursor pagination."""
    for d in sample_odoo_product_data:
        make_odoo_product(
            odoo_id=d["id"],
            odoo_name=d["name"],
            odoo_sku=d["default_code"],
            odoo_price=Decimal(str(d["list_price"])),
            odoo_qty_available=d["qty_available"],
        )

    response = api_client.get("/api/v1/odoo-sync/products/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 3


@pytest.mark.django_db
def test_filter_by_sync_status(api_client):
    """?sync_status=ERROR returns only ERROR products."""
    make_odoo_product(odoo_id=1, odoo_name="Good", sync_status=OdooProduct.SyncStatus.SYNCED)
    make_odoo_product(odoo_id=2, odoo_name="Bad", sync_status=OdooProduct.SyncStatus.ERROR)

    response = api_client.get("/api/v1/odoo-sync/products/?sync_status=ERROR")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["odoo_name"] == "Bad"


# ---------------------------------------------------------------------------
# Sync logs
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_latest_log_returns_most_recent(api_client):
    """GET /logs/latest/ returns the newest SyncLog."""
    SyncLog.objects.create(sync_type=SyncLog.SyncType.FULL, status=SyncLog.Status.SUCCESS)
    newest = SyncLog.objects.create(sync_type=SyncLog.SyncType.DELTA, status=SyncLog.Status.FAILED)

    response = api_client.get("/api/v1/odoo-sync/logs/latest/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == str(newest.id)
    assert response.data["status"] == "FAILED"


# ---------------------------------------------------------------------------
# Trigger endpoint
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch("odoo_sync.views.sync_odoo_products_full.delay")
def test_trigger_full_sync_queues_task_and_returns_202(mock_delay, api_client):
    """POST trigger with sync_type=full returns 202 with task_id."""
    mock_delay.return_value.id = "fake-task-id"

    # conftest already patches check_odoo_connection → "ok" via odoo_connector_mock,
    # but this test doesn't use that fixture; patch manually.
    with patch("odoo_sync.views.check_odoo_connection",
               return_value={"status": "ok", "latency_ms": 5, "odoo_version": "16.0"}):
        response = api_client.post(
            "/api/v1/odoo-sync/sync/trigger/",
            {"sync_type": "full"},
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data["status"] == "queued"
    assert response.data["task_id"] == "fake-task-id"
    assert "sync_log_id" in response.data
    mock_delay.assert_called_once()


@pytest.mark.django_db
def test_trigger_returns_503_when_odoo_down(api_client):
    """If check_odoo_connection reports 'down', trigger returns 503."""
    with patch("odoo_sync.views.check_odoo_connection",
               return_value={"status": "down", "latency_ms": 9999, "odoo_version": "unknown"}):
        response = api_client.post(
            "/api/v1/odoo-sync/sync/trigger/",
            {"sync_type": "full"},
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# ---------------------------------------------------------------------------
# Conflict resolution
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_resolve_conflict_sets_synced_status(api_client):
    """POST /products/{pk}/resolve_conflict/ sets sync_status=SYNCED."""
    product = make_odoo_product(odoo_id=1, sync_status=OdooProduct.SyncStatus.CONFLICT)

    response = api_client.post(
        f"/api/v1/odoo-sync/products/{product.pk}/resolve_conflict/"
    )

    assert response.status_code == status.HTTP_200_OK
    product.refresh_from_db()
    assert product.sync_status == OdooProduct.SyncStatus.SYNCED


# ---------------------------------------------------------------------------
# Error format (RFC 7807 via problem_detail_exception_handler)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_validation_error_wrapped_in_rfc7807(api_client):
    """A 400 validation error is wrapped in RFC 7807 problem+json format."""
    with patch("odoo_sync.views.check_odoo_connection",
               return_value={"status": "ok", "latency_ms": 1, "odoo_version": "16.0"}):
        response = api_client.post("/api/v1/odoo-sync/sync/trigger/", {})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # RFC 7807 wrapper fields
    assert "type" in response.data
    assert "title" in response.data
    assert "detail" in response.data
    # sync_type field error serialised into the detail string
    assert "sync_type" in response.data["detail"]


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_health_endpoint_no_auth_required(anon_client):
    """GET /health/ is publicly accessible."""
    with patch("odoo_sync.views.check_odoo_connection",
               return_value={"status": "ok", "latency_ms": 10, "odoo_version": "16.0"}):
        response = anon_client.get("/api/v1/odoo-sync/health/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ok"


@pytest.mark.django_db
def test_health_endpoint_returns_503_when_down(anon_client):
    """GET /health/ returns 503 when Odoo is unreachable."""
    with patch("odoo_sync.views.check_odoo_connection",
               return_value={"status": "down", "latency_ms": 9999, "odoo_version": "unknown"}):
        response = anon_client.get("/api/v1/odoo-sync/health/")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
