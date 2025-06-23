# Generated manually for inventory performance indexes
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_update_product_field_types_and_labels'),
    ]

    operations = [
        # Product performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_active_type ON inventory_product (is_active, product_type);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_active_type;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_manufacturer ON inventory_product (manufacturer_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_manufacturer;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_part_number ON inventory_product (manufacturer_part_number);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_part_number;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_name_search ON inventory_product USING gin(to_tsvector('english', name || ' ' || manufacturer_part_number));",
            reverse_sql="DROP INDEX IF EXISTS idx_product_name_search;"
        ),
        
        # Storage Detail performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_storage_product_warehouse ON inventory_storagedetail (product_id, warehouse_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_storage_product_warehouse;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_storage_quantities ON inventory_storagedetail (product_id, quantity_on_hand, quantity_reserved);",
            reverse_sql="DROP INDEX IF EXISTS idx_storage_quantities;"
        ),
        
        # Price List performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_price_list ON inventory_productprice (product_id, price_list_version_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_price_list;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_price_list_version_date ON inventory_pricelistversion (price_list_id, valid_from, valid_to);",
            reverse_sql="DROP INDEX IF EXISTS idx_price_list_version_date;"
        ),
        
        # Manufacturer performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_manufacturer_name ON inventory_manufacturer (name);",
            reverse_sql="DROP INDEX IF EXISTS idx_manufacturer_name;"
        ),
        
        # Warehouse performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_warehouse_active ON inventory_warehouse (is_active, name);",
            reverse_sql="DROP INDEX IF EXISTS idx_warehouse_active;"
        ),
    ]