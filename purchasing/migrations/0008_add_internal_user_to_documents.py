# Generated by Django 4.2.11 on 2025-06-17 00:26

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_businesspartnerlocation_contact'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('purchasing', '0007_purchaseorder_bill_to_location_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseorder',
            name='internal_user',
            field=models.ForeignKey(blank=True, help_text='Our company contact handling this purchase order', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchase_orders_as_internal_contact', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='purchaseorder',
            name='contact',
            field=models.ForeignKey(blank=True, help_text='Vendor contact for this purchase order', null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.contact'),
        ),
    ]
