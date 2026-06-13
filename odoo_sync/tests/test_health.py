"""Tests for Odoo connection health checking logic and endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status
from odoo_sync.health import check_odoo_connection
from odoo_sync.exceptions import OdooConnectionError

@pytest.mark.django_db
def test_check_odoo_connection_reachable_returns_ok():
    """Test check_odoo_connection returns success when Odoo version call succeeds."""
    mock_connector = MagicMock()
    mock_connector._common.version.return_value = {"server_version": "16.0"}
    
    with patch("odoo_sync.health.get_connector", return_value=mock_connector), \
         patch("odoo_sync.health.time.time", side_effect=[100.0, 100.1]):
        result = check_odoo_connection()
        
    assert result["status"] == "ok"
    assert "latency_ms" in result
    assert result["odoo_version"] == "16.0"

@pytest.mark.django_db
def test_check_odoo_connection_exception_returns_down():
    """Test check_odoo_connection returns down status when connector raises error."""
    with patch("odoo_sync.health.get_connector", side_effect=OdooConnectionError("Down")):
        result = check_odoo_connection()
        
    assert result["status"] == "down"
    assert result["odoo_version"] == "unknown"

@pytest.mark.django_db
def test_check_odoo_connection_slow_returns_ok():
    """Test check_odoo_connection still returns ok when latency is high (degraded logic not implemented)."""
    mock_connector = MagicMock()
    mock_connector._common.version.return_value = {"server_version": "17.0"}
    
    # Simulating 2.5 seconds latency
    with patch("odoo_sync.health.get_connector", return_value=mock_connector), \
         patch("odoo_sync.health.time.time", side_effect=[100.0, 102.5]):
        result = check_odoo_connection()
        
    assert result["status"] == "ok"
    assert result["latency_ms"] >= 2000

@pytest.mark.django_db
def test_health_api_endpoint_success_returns_200(api_client):
    """Test public health endpoint returns 200 when Odoo is ok."""
    with patch("odoo_sync.views.check_odoo_connection") as mock_health:
        mock_health.return_value = {"status": "ok", "latency_ms": 10, "odoo_version": "16.0"}
        response = api_client.get("/api/v1/odoo-sync/health/")
        
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ok"

@pytest.mark.django_db
def test_health_api_endpoint_down_returns_503(api_client):
    """Test health endpoint returns 503 Service Unavailable when Odoo is down."""
    with patch("odoo_sync.views.check_odoo_connection") as mock_health:
        mock_health.return_value = {"status": "down", "latency_ms": 0, "odoo_version": "unknown"}
        response = api_client.get("/api/v1/odoo-sync/health/")
        
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
