"""Tests for Odoo synchronisation Celery tasks."""

from __future__ import annotations

from datetime import datetime, timezone as dt_tz
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from odoo_sync.models import OdooProduct, SyncLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply(task, **kwargs):
    """Run a Celery task synchronously via .apply() and return the result value."""
    return task.apply(kwargs=kwargs).get()


# ---------------------------------------------------------------------------
# Full sync
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_full_sync_creates_synclog_with_success_status(odoo_connector_mock, sync_config):
    """Full sync produces a SyncLog that ends in SUCCESS."""
    with patch("odoo_sync.tasks.notify_sync_started"), \
         patch("odoo_sync.tasks.notify_sync_progress"), \
         patch("odoo_sync.tasks.notify_sync_completed"):
        from odoo_sync.tasks import sync_odoo_products_full
        sync_log_id = _apply(sync_odoo_products_full, triggered_by="test")

    log = SyncLog.objects.get(id=sync_log_id)
    assert log.status == SyncLog.Status.SUCCESS
    assert log.records_fetched == 2
    assert log.records_created == 2


@pytest.mark.django_db
def test_full_sync_creates_odoo_product_records(odoo_connector_mock, sync_config):
    """One OdooProduct row is created for each record returned by Odoo."""
    with patch("odoo_sync.tasks.notify_sync_started"), \
         patch("odoo_sync.tasks.notify_sync_progress"), \
         patch("odoo_sync.tasks.notify_sync_completed"):
        from odoo_sync.tasks import sync_odoo_products_full
        _apply(sync_odoo_products_full, triggered_by="test")

    assert OdooProduct.objects.count() == 2
    p = OdooProduct.objects.get(odoo_id=1)
    assert p.odoo_name == "Test Product 1"
    assert p.odoo_price == Decimal("10.00")


@pytest.mark.django_db
def test_batch_pagination_stops_when_fewer_records_returned(odoo_connector_mock, sync_config):
    """Pagination loop stops when Odoo returns fewer records than batch_size."""
    sync_config.batch_size = 1
    sync_config.save()

    # first call → 1 record, second call → 0 records (stops)
    odoo_connector_mock.search_read.side_effect = [
        [{"id": 1, "name": "P1", "default_code": "", "list_price": 5.0,
          "qty_available": 0, "active": True, "categ_id": False}],
        [],
    ]
    odoo_connector_mock.get_product_count.return_value = 1

    with patch("odoo_sync.tasks.notify_sync_started"), \
         patch("odoo_sync.tasks.notify_sync_progress"), \
         patch("odoo_sync.tasks.notify_sync_completed"):
        from odoo_sync.tasks import sync_odoo_products_full
        _apply(sync_odoo_products_full)

    assert OdooProduct.objects.count() == 1
    # search_read called twice: first page + empty page
    assert odoo_connector_mock.search_read.call_count == 2


@pytest.mark.django_db
def test_per_record_error_does_not_abort_sync(odoo_connector_mock, sync_config):
    """A bad record is logged in error_detail but the rest of the batch continues."""
    odoo_connector_mock.search_read.return_value = [
        {"id": 1, "name": "Good", "default_code": "G1",
         "list_price": 5.0, "qty_available": 0, "active": True, "categ_id": False},
        {"id": None, "name": "Bad"},       # missing id → ValueError
    ]

    with patch("odoo_sync.tasks.notify_sync_started"), \
         patch("odoo_sync.tasks.notify_sync_progress"), \
         patch("odoo_sync.tasks.notify_sync_completed"):
        from odoo_sync.tasks import sync_odoo_products_full
        sync_log_id = _apply(sync_odoo_products_full)

    log = SyncLog.objects.get(id=sync_log_id)
    assert log.status == SyncLog.Status.PARTIAL
    assert log.records_created == 1
    assert log.records_errored == 1
    assert "unknown" in log.error_detail


# ---------------------------------------------------------------------------
# Delta sync
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_delta_sync_adds_write_date_to_domain(odoo_connector_mock, sync_config):
    """Delta sync appends a write_date filter when a previous SUCCESS log exists."""
    SyncLog.objects.create(
        sync_type=SyncLog.SyncType.FULL,
        status=SyncLog.Status.SUCCESS,
        started_at=timezone.now(),
        finished_at=datetime(2023, 1, 1, 10, 0, 0, tzinfo=dt_tz.utc),
    )

    with patch("odoo_sync.tasks.notify_sync_started"), \
         patch("odoo_sync.tasks.notify_sync_progress"), \
         patch("odoo_sync.tasks.notify_sync_completed"):
        from odoo_sync.tasks import sync_odoo_products_delta
        _apply(sync_odoo_products_delta)

    # Verify write_date was included in the domain passed to search_read
    call_kwargs = odoo_connector_mock.search_read.call_args
    domain = call_kwargs.kwargs.get("domain") or call_kwargs.args[1]
    has_write_date = any(
        isinstance(c, list) and c[0] == "write_date" for c in domain
    )
    assert has_write_date


@pytest.mark.django_db
def test_delta_sync_falls_back_to_full_when_no_success_log(odoo_connector_mock, sync_config):
    """Delta sync performs a FULL sync when no previous SUCCESS log exists."""
    assert SyncLog.objects.count() == 0

    with patch("odoo_sync.tasks.notify_sync_started"), \
         patch("odoo_sync.tasks.notify_sync_progress"), \
         patch("odoo_sync.tasks.notify_sync_completed"):
        from odoo_sync.tasks import sync_odoo_products_delta
        sync_log_id = _apply(sync_odoo_products_delta)

    log = SyncLog.objects.get(id=sync_log_id)
    assert log.sync_type == SyncLog.SyncType.FULL
