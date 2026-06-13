"""Tests for odoo_sync models."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from odoo_sync.models import SyncConfig, SyncLog


@pytest.mark.django_db
class TestSyncLogDuration:
    def test_hours_minutes_seconds(self):
        log = SyncLog(sync_type=SyncLog.SyncType.FULL, duration_seconds=3665)
        assert log.get_duration() == "1h 1m 5s"

    def test_minutes_seconds(self):
        log = SyncLog(sync_type=SyncLog.SyncType.FULL, duration_seconds=65)
        assert log.get_duration() == "1m 5s"

    def test_seconds_only(self):
        log = SyncLog(sync_type=SyncLog.SyncType.FULL, duration_seconds=5)
        assert log.get_duration() == "5s"

    def test_zero(self):
        log = SyncLog(sync_type=SyncLog.SyncType.FULL, duration_seconds=0)
        # started_at is auto_now_add so won't be set outside of save
        log.started_at = None
        assert log.get_duration() == "0s"


@pytest.mark.django_db
class TestSyncLogMarkFinished:
    def test_mark_finished_sets_status_and_finished_at(self):
        log = SyncLog.objects.create(
            sync_type=SyncLog.SyncType.FULL,
            status=SyncLog.Status.RUNNING,
        )
        log.mark_finished(SyncLog.Status.SUCCESS)
        log.refresh_from_db()

        assert log.status == SyncLog.Status.SUCCESS
        assert log.finished_at is not None
        assert log.duration_seconds is not None
        assert log.duration_seconds >= 0


@pytest.mark.django_db
class TestSyncConfigSingleton:
    def test_save_forces_pk_to_1(self):
        config = SyncConfig()
        config.pk = 99
        config.save()

        assert config.pk == 1
        assert SyncConfig.objects.count() == 1

    def test_two_saves_overwrite_same_row(self):
        SyncConfig.objects.create(pk=1, batch_size=50)
        c2 = SyncConfig(batch_size=200)
        c2.save()

        assert SyncConfig.objects.count() == 1
        assert SyncConfig.objects.get(pk=1).batch_size == 200
