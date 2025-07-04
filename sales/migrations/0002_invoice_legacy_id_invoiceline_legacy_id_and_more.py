# Generated by Django 4.2.11 on 2025-06-16 18:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='invoiceline',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='salesorder',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='salesorderline',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='shipmentline',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
    ]
