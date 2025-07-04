# Generated by Django 4.2.11 on 2025-06-16 20:48

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_opportunity'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentTerms',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('legacy_id', models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True)),
                ('code', models.CharField(max_length=20, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('net_days', models.IntegerField(default=30, help_text='Number of days for payment')),
                ('discount_days', models.IntegerField(default=0, help_text='Days for early payment discount')),
                ('discount_percent', models.DecimalField(decimal_places=2, default=0, help_text='Early payment discount percentage', max_digits=5)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='updated_%(class)s', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Payment Terms',
                'ordering': ['code'],
            },
        ),
        migrations.CreateModel(
            name='Incoterms',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('legacy_id', models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True)),
                ('code', models.CharField(help_text='Incoterm code (e.g., EXW, FOB, CIF)', max_length=10, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, help_text='Full description of the incoterm')),
                ('seller_responsibility', models.TextField(blank=True, help_text='What seller is responsible for')),
                ('buyer_responsibility', models.TextField(blank=True, help_text='What buyer is responsible for')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='updated_%(class)s', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Incoterms',
                'ordering': ['code'],
            },
        ),
    ]
