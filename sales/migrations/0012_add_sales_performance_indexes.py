# Generated manually for sales performance indexes
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0011_salesorder_transaction_id'),
    ]

    operations = [
        # Sales Order performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_sales_order_date_status ON sales_salesorder (date_ordered, doc_status);",
            reverse_sql="DROP INDEX IF EXISTS idx_sales_order_date_status;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_sales_order_status_partner ON sales_salesorder (doc_status, business_partner_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_sales_order_status_partner;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_sales_order_opportunity ON sales_salesorder (opportunity_id, date_ordered);",
            reverse_sql="DROP INDEX IF EXISTS idx_sales_order_opportunity;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_sales_order_transaction ON sales_salesorder (transaction_id) WHERE transaction_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_sales_order_transaction;"
        ),
        
        # Sales Order Line performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_sales_line_order_product ON sales_salesorderline (order_id, product_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_sales_line_order_product;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_sales_line_quantities ON sales_salesorderline (order_id, quantity_ordered, quantity_delivered);",
            reverse_sql="DROP INDEX IF EXISTS idx_sales_line_quantities;"
        ),
        
        # Invoice performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_invoice_date_status ON sales_invoice (date_invoiced, doc_status);",
            reverse_sql="DROP INDEX IF EXISTS idx_invoice_date_status;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_invoice_partner_date ON sales_invoice (business_partner_id, date_invoiced);",
            reverse_sql="DROP INDEX IF EXISTS idx_invoice_partner_date;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_invoice_sales_order ON sales_invoice (sales_order_id) WHERE sales_order_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_invoice_sales_order;"
        ),
        
        # Shipment performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_shipment_date_status ON sales_shipment (movement_date, doc_status);",
            reverse_sql="DROP INDEX IF EXISTS idx_shipment_date_status;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_shipment_partner ON sales_shipment (business_partner_id, movement_date);",
            reverse_sql="DROP INDEX IF EXISTS idx_shipment_partner;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_shipment_tracking ON sales_shipment (tracking_no) WHERE tracking_no != '';",
            reverse_sql="DROP INDEX IF EXISTS idx_shipment_tracking;"
        ),
    ]