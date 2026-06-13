"""Tests for WebSocket notification utilities using Channels group_send."""

import pytest
from unittest.mock import patch, AsyncMock
from model_bakery import baker
from odoo_sync.ws_utils import (
    notify_sync_started, 
    notify_sync_progress, 
    notify_sync_completed, 
    notify_sync_error
)
from odoo_sync.models import SyncLog

@pytest.mark.django_db
def test_notify_sync_started_sends_correct_payload():
    """Test notify_sync_started calls group_send with 'sync.started' type."""
    log = baker.make(SyncLog)
    mock_layer = AsyncMock()
    with patch("odoo_sync.ws_utils.get_channel_layer", return_value=mock_layer):
        notify_sync_started(str(log.id))
        
    mock_layer.group_send.assert_called_once()
    args, kwargs = mock_layer.group_send.call_args
    # The message itself is the second positional argument or 'message' in kwargs if using group_send(group, message)
    # Actually Channels group_send(group, message) - so kwargs['message'] might not exist if passed positionally
    message = args[1]
    assert message["type"] == "sync.started"
    assert message["sync_log"]["id"] == str(log.id)

@pytest.mark.django_db
def test_notify_sync_progress_calculates_percentage():
    """Test progress notification calculates correct percentage for frontend."""
    mock_layer = AsyncMock()
    with patch("odoo_sync.ws_utils.get_channel_layer", return_value=mock_layer):
        notify_sync_progress("fake-id", processed=25, total=100)
        
    args, kwargs = mock_layer.group_send.call_args
    message = args[1]
    assert message["type"] == "sync.progress"
    assert message["percent"] == 25

@pytest.mark.django_db
def test_notify_sync_completed_sends_broadcast():
    """Test completion utility sends broadcast message."""
    log = baker.make(SyncLog)
    mock_layer = AsyncMock()
    with patch("odoo_sync.ws_utils.get_channel_layer", return_value=mock_layer):
        notify_sync_completed(str(log.id))
        
    args, kwargs = mock_layer.group_send.call_args
    message = args[1]
    assert message["type"] == "sync.completed"
    assert message["sync_log"]["id"] == str(log.id)

@pytest.mark.django_db
def test_notify_sync_error_includes_message():
    """Test error notification passes the error message to the group."""
    mock_layer = AsyncMock()
    with patch("odoo_sync.ws_utils.get_channel_layer", return_value=mock_layer):
        notify_sync_error("fake-id", "XML-RPC Fault")
        
    args, kwargs = mock_layer.group_send.call_args
    message = args[1]
    assert message["type"] == "sync.error"
    assert message["message"] == "XML-RPC Fault"
