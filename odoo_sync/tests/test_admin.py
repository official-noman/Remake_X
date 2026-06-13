"""Tests for Django admin customizations, actions and dashboard view."""

import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.contrib.admin.sites import AdminSite
from django.http import HttpResponse
from model_bakery import baker
from odoo_sync.admin import OdooProductAdmin, SyncLogAdmin, SyncConfigAdmin
from odoo_sync.models import OdooProduct, SyncLog, SyncConfig

@pytest.mark.django_db
def test_admin_action_mark_as_synced_updates_status(admin_user):
    """Test admin action sets sync_status to SYNCED for multiple records."""
    products = baker.make(OdooProduct, sync_status=OdooProduct.SyncStatus.ERROR, _quantity=3)
    site = AdminSite()
    admin_obj = OdooProductAdmin(OdooProduct, site)
    
    # Mock request and avoid message_user complexity by mocking it
    request = MagicMock()
    request.user = admin_user
    
    with patch.object(OdooProductAdmin, "message_user") as mock_msg:
        queryset = OdooProduct.objects.filter(id__in=[p.id for p in products])
        admin_obj.mark_as_synced(request, queryset)
        
    for p in queryset:
        p.refresh_from_db()
        assert p.sync_status == OdooProduct.SyncStatus.SYNCED

@pytest.mark.django_db
def test_admin_action_create_local_products_mapping(admin_user):
    """Test admin action creates local Product instances for Odoo products."""
    odoo_p = baker.make(OdooProduct, local_product=None, odoo_name="Orphan", odoo_price=10.0)
    site = AdminSite()
    admin_obj = OdooProductAdmin(OdooProduct, site)
    
    request = MagicMock()
    request.user = admin_user
    
    # We must mock _candidate_local_product_values because the local Product model
    # requires 'seller' and 'image' fields which aren't provided by default.
    # We also mock the image field to avoid file system issues.
    with patch("odoo_sync.tasks._candidate_local_product_values") as mock_candidates:
        mock_candidates.return_value = {
            "name": "Orphan",
            "description": "Desc",
            "price": 10.0,
            "quantity": 1,
            "seller": admin_user,
            "image": "fake.jpg",
            "category": "other"
        }
        with patch.object(OdooProductAdmin, "message_user") as mock_msg:
            admin_obj.create_local_products(request, OdooProduct.objects.filter(id=odoo_p.id))
    
    odoo_p.refresh_from_db()
    assert odoo_p.local_product is not None

@pytest.mark.django_db
def test_odoo_product_admin_display_methods():
    """Test display logic for local product presence and status colors."""
    odoo_p = baker.make(OdooProduct, local_product=None, sync_status=OdooProduct.SyncStatus.PENDING)
    admin_obj = OdooProductAdmin(OdooProduct, AdminSite())
    
    # returns HTML icon
    res = admin_obj.has_local_product(odoo_p)
    assert "✘ No" in res
    
    status_html = admin_obj.sync_status_badge(odoo_p)
    assert "PENDING" in status_html

@pytest.mark.django_db
def test_readonly_admin_permissions():
    """Test SyncLog and SyncConfig admins restrict add/delete permissions."""
    site = AdminSite()
    log_admin = SyncLogAdmin(SyncLog, site)
    cfg_admin = SyncConfigAdmin(SyncConfig, site)
    
    assert log_admin.has_add_permission(None) is False
    assert log_admin.has_change_permission(None) is False
    assert cfg_admin.has_add_permission(None) is False
    assert cfg_admin.has_delete_permission(None) is False

@pytest.mark.django_db
def test_admin_dashboard_access_control(client, admin_user):
    """Test dashboard view access for authenticated vs anonymous users."""
    url = reverse("admin:odoo_sync_dashboard")
    
    # Anon
    response = client.get(url)
    assert response.status_code == 302
    
    # Admin
    client.force_login(admin_user)
    # Return a real HttpResponse to avoid issues with Django middleware expecting headers
    with patch("odoo_sync.admin.render", return_value=HttpResponse("OK")):
        response = client.get(url)
        assert response.status_code == 200
