# Generated manually for purchasing performance indexes
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('purchasing', '0009_purchaseorder_estimated_delivery_weeks'),
    ]

    operations = [
        # Purchase Order performance indexes - core fields only
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_purchase_order_date_status ON purchasing_purchaseorder (date_ordered, doc_status);",
            reverse_sql="DROP INDEX IF EXISTS idx_purchase_order_date_status;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_purchase_order_vendor ON purchasing_purchaseorder (business_partner_id, date_ordered);",
            reverse_sql="DROP INDEX IF EXISTS idx_purchase_order_vendor;"
        ),
        
        # Purchase Order Line performance indexes - core fields only
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_purchase_line_order_product ON purchasing_purchaseorderline (order_id, product_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_purchase_line_order_product;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_purchase_line_quantities ON purchasing_purchaseorderline (order_id, quantity_ordered, quantity_received);",
            reverse_sql="DROP INDEX IF EXISTS idx_purchase_line_quantities;"
        ),
        
        # Vendor Bill performance indexes - core fields only
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_vendor_bill_date_status ON purchasing_vendorbill (date_invoiced, doc_status);",
            reverse_sql="DROP INDEX IF EXISTS idx_vendor_bill_date_status;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_vendor_bill_partner ON purchasing_vendorbill (business_partner_id, date_invoiced);",
            reverse_sql="DROP INDEX IF EXISTS idx_vendor_bill_partner;"
        ),
        
        # Receipt performance indexes - core fields only  
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_receipt_date_status ON purchasing_receipt (movement_date, doc_status);",
            reverse_sql="DROP INDEX IF EXISTS idx_receipt_date_status;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_receipt_vendor ON purchasing_receipt (business_partner_id, movement_date);",
            reverse_sql="DROP INDEX IF EXISTS idx_receipt_vendor;"
        ),
    ]