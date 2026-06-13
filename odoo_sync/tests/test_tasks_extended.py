"""Extended tests for Celery sync tasks covering mapping, conflict logic and error handling."""

import pytest
from unittest.mock import patch, MagicMock, call
from decimal import Decimal
from model_bakery import baker
from django.test import override_settings
from odoo_sync.tasks import (
    sync_odoo_products_full, 
    sync_odoo_products_by_ids,
    _map_odoo_to_model, 
    trigger_manual_sync, 
    _process_product_batch,
    _bulk_create_odoo_products
)
from odoo_sync.models import SyncLog, OdooProduct, SyncConfig
from odoo_sync.exceptions import OdooConnectionError

@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_sync_full_error_marks_log_failed():
    """Test that sync_log is marked as FAILED if Odoo connection dies mid-sync."""
    log = baker.make(SyncLog, status=SyncLog.Status.RUNNING)
    
    with patch("odoo_sync.tasks.get_connector") as mock_conn:
        mock_conn.return_value.get_product_count.side_effect = OdooConnectionError("Timeout")
        
        with pytest.raises(OdooConnectionError):
            sync_odoo_products_full(triggered_by="test", sync_log_id=str(log.id))
            
    log.refresh_from_db()
    assert log.status == SyncLog.Status.FAILED

def test_map_odoo_to_model_handling_complex_fields_correctly():
    """Test mapping logic for False values, categ_id pairs, and numeric types."""
    record = {
        "id": 123,
        "name": "Test Product",
        "default_code": False,  # Should become ""
        "list_price": 99.50,
        "qty_available": 10.0,
        "active": True,
        "categ_id": [5, "Electronics / Phones"]
    }
    
    mapped = _map_odoo_to_model(record)
    assert mapped["odoo_id"] == 123
    assert mapped["odoo_sku"] == ""
    assert mapped["odoo_price"] == Decimal("99.50")
    assert mapped["odoo_categ_id"] == 5
    assert mapped["odoo_categ_name"] == "Electronics / Phones"

@pytest.mark.django_db
def test_process_batch_odoo_wins_updates_local_product():
    """Test conflict resolution ODOO_WINS updates linked local product fields when a conflict occurs."""
    config = baker.make(SyncConfig, conflict_resolution=SyncConfig.ConflictResolution.ODOO_WINS)
    # last sync state: price 10.00
    local_p = baker.make("myapp.Product", price=Decimal("15.00"), quantity=5) # local changed to 15.00
    odoo_p = baker.make(OdooProduct, odoo_id=1, local_product=local_p, odoo_price=Decimal("10.00"), odoo_qty_available=5.0)
    
    # Odoo changed to 20.00
    record = [{"id": 1, "name": "New Name", "list_price": 20.0, "qty_available": 15.0, "active": True}]
    log = baker.make(SyncLog)
    
    _process_product_batch(record, log, config)
    
    local_p.refresh_from_db()
    # Odoo wins, so local product should now have Odoo's price (20.00)
    assert local_p.price == Decimal("20.00")
    assert local_p.quantity == 15

@pytest.mark.django_db
def test_process_batch_manual_resolution_sets_conflict_status():
    """Test MANUAL conflict resolution sets product status to CONFLICT."""
    config = baker.make(SyncConfig, conflict_resolution=SyncConfig.ConflictResolution.MANUAL)
    local_p = baker.make("myapp.Product", price=Decimal("10.00"))
    odoo_p = baker.make(OdooProduct, odoo_id=1, local_product=local_p, odoo_price=Decimal("10.00"))
    
    # Conflict: Odoo price is 20, but local was manually changed (simulated by record update)
    record = [{"id": 1, "name": "Test", "list_price": 20.0, "qty_available": 5.0, "active": True}]
    log = baker.make(SyncLog)
    
    # We need to simulate that local_p was also modified. 
    local_p.price = Decimal("15.00") # Local changed
    local_p.save()
    
    _process_product_batch(record, log, config)
    
    odoo_p.refresh_from_db()
    assert odoo_p.sync_status == OdooProduct.SyncStatus.CONFLICT

@pytest.mark.django_db
def test_trigger_manual_sync_calls_correct_subtask():
    """Test trigger_manual_sync dispatches delta task when requested."""
    with patch("odoo_sync.tasks.sync_odoo_products_delta.apply") as mock_delta:
        mock_delta.return_value.get.return_value = "task-uuid"
        trigger_manual_sync(sync_type="delta")
        mock_delta.assert_called_once()

@pytest.mark.django_db
def test_sync_log_counters_increment_correctly():
    """Test records_created and records_updated counts in SyncLog."""
    log = baker.make(SyncLog, records_created=0, records_updated=0)
    config = baker.make(SyncConfig, auto_create_local_products=False)
    
    # 1 New, 1 Existing
    baker.make(OdooProduct, odoo_id=100)
    records = [
        {"id": 100, "name": "Update", "list_price": 10, "qty_available": 1, "active": True},
        {"id": 200, "name": "Create", "list_price": 20, "qty_available": 2, "active": True},
    ]
    
    _process_product_batch(records, log, config)
    
    log.refresh_from_db()
    assert log.records_created == 1
    assert log.records_updated == 1


# ── New Coverage Tests ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_process_batch_local_wins_ignores_odoo_change():
    """Test LOCAL_WINS resolution leaves local product price unchanged."""
    config = baker.make(SyncConfig, conflict_resolution=SyncConfig.ConflictResolution.LOCAL_WINS)
    local_p = baker.make("myapp.Product", price=Decimal("15.00")) # local changed
    baker.make(OdooProduct, odoo_id=55, local_product=local_p, odoo_price=Decimal("10.00"))
    
    record = [{"id": 55, "name": "Test", "list_price": 20.0, "qty_available": 5.0, "active": True}]
    _process_product_batch(record, baker.make(SyncLog), config)
    
    local_p.refresh_from_db()
    assert local_p.price == Decimal("15.00") # Remains 15.00

@pytest.mark.django_db
def test_process_batch_skips_creation_if_auto_create_false():
    """Test that new Odoo products don't create local Products if auto_create is off."""
    config = baker.make(SyncConfig, auto_create_local_products=False)
    record = [{"id": 999, "name": "Ghost", "list_price": 10.0, "qty_available": 1, "active": True}]
    
    _process_product_batch(record, baker.make(SyncLog), config)
    
    op = OdooProduct.objects.get(odoo_id=999)
    assert op.local_product is None

@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_sync_by_ids_success_path():
    """Test sync_odoo_products_by_ids fetches specific records successfully."""
    log = baker.make(SyncLog)
    with patch("odoo_sync.tasks.get_connector") as mock_conn:
        mock_conn.return_value.search_read.return_value = [
            {"id": 10, "name": "P1", "list_price": 5.0, "qty_available": 2, "active": True}
        ]
        sync_odoo_products_by_ids(odoo_ids=[10])
        
    assert OdooProduct.objects.filter(odoo_id=10).exists()

@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_sync_full_calls_notifications():
    """Test that sync_full triggers all WebSocket notification helpers."""
    with patch("odoo_sync.tasks.get_connector") as mock_conn, \
         patch("odoo_sync.tasks.notify_sync_started") as n_start, \
         patch("odoo_sync.tasks.notify_sync_completed") as n_done:
        
        mock_conn.return_value.get_product_count.return_value = 1
        mock_conn.return_value.search_read.return_value = [
            {"id": 1, "name": "N", "list_price": 1, "qty_available": 1, "active": True}
        ]
        
        sync_odoo_products_full()
        
        n_start.assert_called_once()
        n_done.assert_called_once()

@pytest.mark.django_db
def test_bulk_create_fallback_logic_on_error():
    """Test that if bulk_create fails, it falls back to individual saves (covers lines 483-502)."""
    products = [baker.prepare(OdooProduct, odoo_id=i) for i in range(5)]
    log = baker.make(SyncLog, records_created=5)
    
    # Mock bulk_create to raise error, but individual save to work
    with patch("odoo_sync.models.OdooProduct.objects.bulk_create", side_effect=Exception("Bulk Fail")):
        _bulk_create_odoo_products(products, log, batch_size=10)
        
    assert OdooProduct.objects.count() == 5

@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@patch("odoo_sync.tasks.sync_odoo_products_full.retry")
def test_sync_full_retries_on_transient_error(mock_retry):
    """Test that sync task attempts retry on generic exceptions."""
    with patch("odoo_sync.tasks.get_connector", side_effect=Exception("Transient")):
        with pytest.raises(Exception):
            sync_odoo_products_full()
    
    mock_retry.assert_called()

@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_sync_full_marks_failed_in_finally_on_abort():
    """Test that SyncLog status is set to FAILED even if task is aborted/exception is unhandled."""
    log = baker.make(SyncLog, status=SyncLog.Status.RUNNING)
    
    # Simulate a crash inside the while loop after starting
    with patch("odoo_sync.tasks.get_connector") as mock_conn:
        mock_conn.return_value.get_product_count.return_value = 10
        mock_conn.return_value.search_read.side_effect = KeyboardInterrupt() # Abrupt abort
        
        with pytest.raises(KeyboardInterrupt):
            sync_odoo_products_full(sync_log_id=str(log.id))
            
    log.refresh_from_db()
    assert log.status == SyncLog.Status.FAILED
