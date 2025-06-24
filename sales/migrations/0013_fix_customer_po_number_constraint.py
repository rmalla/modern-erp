# Generated manually to fix customer_po_number constraint issue
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0012_add_sales_performance_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            # Drop the NOT NULL constraint from customer_po_number (the old column)
            sql="ALTER TABLE sales_salesorder ALTER COLUMN customer_po_number DROP NOT NULL;",
            reverse_sql="ALTER TABLE sales_salesorder ALTER COLUMN customer_po_number SET NOT NULL;",
        ),
        migrations.RunSQL(
            # Set a default empty string for existing NULL values
            sql="UPDATE sales_salesorder SET customer_po_number = '' WHERE customer_po_number IS NULL;",
            reverse_sql="UPDATE sales_salesorder SET customer_po_number = NULL WHERE customer_po_number = '';",
        ),
        migrations.RunSQL(
            # Also make customer_po_reference nullable since it should be optional based on the model
            sql="ALTER TABLE sales_salesorder ALTER COLUMN customer_po_reference DROP NOT NULL;",
            reverse_sql="ALTER TABLE sales_salesorder ALTER COLUMN customer_po_reference SET NOT NULL;",
        ),
    ]