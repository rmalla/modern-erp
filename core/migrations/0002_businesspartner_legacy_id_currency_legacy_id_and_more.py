# Generated by Django 4.2.11 on 2025-06-16 18:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='businesspartner',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='currency',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='department',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='numbersequence',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='unitofmeasure',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Original ID from migrated system', max_length=50, null=True),
        ),
    ]
