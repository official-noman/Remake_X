# Generated by Django 5.1.3 on 2025-03-10 08:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0010_product_is_upcycled'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='is_available',
            field=models.BooleanField(default=False),
        ),
    ]
