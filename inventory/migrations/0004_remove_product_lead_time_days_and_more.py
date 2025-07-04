# Generated by Django 4.2.11 on 2025-06-16 21:14

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('inventory', '0003_remove_product_default_vendor_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='lead_time_days',
        ),
        migrations.RemoveField(
            model_name='product',
            name='primary_vendor',
        ),
        migrations.RemoveField(
            model_name='product',
            name='vendor_product_code',
        ),
        migrations.AddField(
            model_name='product',
            name='manufacturer_part_number',
            field=models.CharField(blank=True, help_text="Manufacturer's part number", max_length=100),
        ),
        migrations.CreateModel(
            name='Manufacturer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('legacy_id', models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True)),
                ('code', models.CharField(help_text='Manufacturer code (e.g., APPLE, SAMSUNG)', max_length=50, unique=True)),
                ('name', models.CharField(help_text='Full manufacturer name', max_length=200)),
                ('brand_name', models.CharField(blank=True, help_text='Brand name if different from company name', max_length=200)),
                ('description', models.TextField(blank=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='updated_%(class)s', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='product',
            name='manufacturer',
            field=models.ForeignKey(blank=True, help_text='Product manufacturer/brand', null=True, on_delete=django.db.models.deletion.PROTECT, to='inventory.manufacturer'),
        ),
    ]
