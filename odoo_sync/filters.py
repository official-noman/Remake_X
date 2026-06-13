"""Filter classes for Odoo synchronization APIs."""

import django_filters

from odoo_sync.models import OdooProduct, SyncLog


class OdooProductFilter(django_filters.FilterSet):
    sync_status = django_filters.MultipleChoiceFilter(
        choices=OdooProduct.SyncStatus.choices
    )
    min_price = django_filters.NumberFilter(field_name="odoo_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="odoo_price", lookup_expr="lte")
    last_synced_at = django_filters.DateTimeFromToRangeFilter()

    class Meta:
        model = OdooProduct
        fields = (
            "sync_status",
            "odoo_active",
            "odoo_categ_id",
            "min_price",
            "max_price",
            "last_synced_at",
        )


class SyncLogFilter(django_filters.FilterSet):
    started_at = django_filters.DateFromToRangeFilter(
        field_name="started_at",
        lookup_expr="date",
    )

    class Meta:
        model = SyncLog
        fields = ("status", "sync_type", "started_at")
