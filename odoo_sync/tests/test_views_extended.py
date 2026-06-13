"""Extended tests for API viewsets covering ordering, filtering and singleton logic."""

import pytest
from rest_framework import status
from model_bakery import baker
from odoo_sync.models import SyncConfig, OdooProduct, SyncLog

@pytest.mark.django_db
def test_sync_config_singleton_get_or_create_behavior(api_client):
    """Test that GET config returns the singleton instance even if not in DB yet."""
    # Ensure DB is empty
    SyncConfig.objects.all().delete()
    
    # Retrieve action requires a PK, but get_object overrides it to ID=1
    response = api_client.get("/api/v1/odoo-sync/config/1/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["batch_size"] == 100 # Default

@pytest.mark.django_db
def test_sync_config_patch_permissions(api_client, django_user_model):
    """Test only staff can update sync configuration."""
    # Non-staff user with unique email
    user = django_user_model.objects.create_user(
        username="peon", 
        password="pw",
        email="peon@example.com"
    )
    api_client.force_authenticate(user=user)
    
    response = api_client.patch("/api/v1/odoo-sync/config/1/", {"batch_size": 500})
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_odoo_product_ordering_logic(api_client):
    """Test product listing respects price and sync date ordering."""
    baker.make(OdooProduct, odoo_price=10.0, odoo_id=1)
    baker.make(OdooProduct, odoo_price=50.0, odoo_id=2)
    
    # Price ascending
    response = api_client.get("/api/v1/odoo-sync/products/?ordering=odoo_price")
    assert response.data["results"][0]["odoo_price"] == "10.00"
    
    # Price descending
    response = api_client.get("/api/v1/odoo-sync/products/?ordering=-odoo_price")
    assert response.data["results"][0]["odoo_price"] == "50.00"

@pytest.mark.django_db
def test_sync_log_filtering_by_type_and_status(api_client):
    """Test sync logs can be filtered by type and status fields."""
    baker.make(SyncLog, sync_type="FULL", status="SUCCESS")
    baker.make(SyncLog, sync_type="DELTA", status="FAILED")
    
    # Filter by FAILED - SyncLogViewSet is NOT paginated by default
    response = api_client.get("/api/v1/odoo-sync/logs/?status=FAILED")
    assert len(response.data) == 1
    assert response.data[0]["sync_type"] == "DELTA"
    
    # Filter by FULL
    response = api_client.get("/api/v1/odoo-sync/logs/?sync_type=FULL")
    assert len(response.data) == 1
    assert response.data[0]["status"] == "SUCCESS"
