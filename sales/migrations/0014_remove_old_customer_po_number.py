# Migration to remove the old customer_po_number column
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0013_fix_customer_po_number_constraint'),
    ]

    operations = [
        migrations.RunSQL(
            # Drop the old customer_po_number column that's no longer used
            sql="ALTER TABLE sales_salesorder DROP COLUMN IF EXISTS customer_po_number;",
            reverse_sql="ALTER TABLE sales_salesorder ADD COLUMN customer_po_number VARCHAR(100);",
        ),
    ]