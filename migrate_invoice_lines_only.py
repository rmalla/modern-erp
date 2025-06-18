#!/usr/bin/env python3
"""
Invoice Lines Migration Script

This script migrates only the missing invoice lines from iDempiere to existing invoices.
"""

import os
import sys
import django
import psycopg2
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from core.models import User, UnitOfMeasure
from sales.models import Invoice, InvoiceLine
from inventory.models import Product, ProductCategory


def migrate_invoice_lines():
    """Migrate all invoice lines for existing invoices"""
    
    # Database connection
    old_db = psycopg2.connect(
        host='localhost',
        database='temp_idempiere',
        user='django_user',
        password='django_pass'
    )
    
    # Get defaults
    default_user = User.objects.filter(is_superuser=True).first()
    default_uom = UnitOfMeasure.objects.first()
    default_category = ProductCategory.objects.first()
    
    # Build product lookup map
    product_map = {}
    for product in Product.objects.all():
        if product.legacy_id:
            product_map[product.legacy_id] = product
    
    stats = {
        'lines_migrated': 0,
        'products_created': 0,
        'errors': []
    }
    
    print("Migrating Invoice Lines...")
    
    # Get all existing invoices with legacy_id
    for invoice in Invoice.objects.filter(legacy_id__isnull=False):
        old_invoice_id = int(invoice.legacy_id)
        
        # Skip if invoice already has lines
        if invoice.lines.exists():
            continue
        
        print(f"Processing invoice {invoice.document_no} (legacy ID: {old_invoice_id})")
        
        old_cursor = old_db.cursor()
        
        old_cursor.execute("""
            SELECT 
                c_invoiceline_id,
                line,
                m_product_id,
                qtyinvoiced,
                priceentered,
                priceactual,
                linenetamt,
                description,
                c_orderline_id
            FROM adempiere.c_invoiceline 
            WHERE c_invoice_id = %s
            ORDER BY line
        """, (old_invoice_id,))
        
        for row in old_cursor.fetchall():
            try:
                line_id = row[0]
                line_no = row[1]
                product_id = row[2]
                qty_invoiced = row[3]
                price_entered = row[4]
                price_actual = row[5]
                line_net_amount = row[6]
                line_description = row[7] or ''
                order_line_id = row[8]
                
                # Find or create product
                product = None
                if product_id:
                    product = product_map.get(str(product_id))
                    if not product:
                        # Create placeholder product
                        product = Product.objects.create(
                            code=f"MIGRATED-{product_id}",
                            name=f"Migrated Product {product_id}",
                            description=f"Product migrated from iDempiere ID: {product_id}",
                            product_category=default_category,
                            uom=default_uom,
                            is_sold=True,
                            is_purchased=False,
                            created_by=default_user,
                            updated_by=default_user,
                            legacy_id=str(product_id)
                        )
                        product_map[str(product_id)] = product
                        stats['products_created'] += 1
                        print(f"  → Created placeholder product: {product.code}")
                
                # Find related order line (optional)
                order_line = None
                if order_line_id and invoice.sales_order:
                    order_line = invoice.sales_order.lines.filter(legacy_id=str(order_line_id)).first()
                
                # Create invoice line
                InvoiceLine.objects.create(
                    invoice=invoice,
                    line_no=line_no,
                    description=line_description,
                    
                    # Product
                    product=product,
                    
                    # Reference to order line
                    order_line=order_line,
                    
                    # Quantities
                    quantity_invoiced=Decimal(str(qty_invoiced)) if qty_invoiced else Decimal('0'),
                    
                    # Pricing
                    price_entered=Decimal(str(price_entered)) if price_entered else Decimal('0'),
                    price_actual=Decimal(str(price_actual)) if price_actual else Decimal('0'),
                    discount=Decimal('0'),
                    line_net_amount=Decimal(str(line_net_amount)) if line_net_amount else Decimal('0'),
                    
                    # Audit
                    created_by=default_user,
                    updated_by=default_user,
                    legacy_id=str(line_id)
                )
                
                stats['lines_migrated'] += 1
                print(f"  ✓ Migrated line {line_no}: {line_description}")
                
            except Exception as e:
                error_msg = f"Error migrating Invoice Line ID {line_id}: {str(e)}"
                print(f"    ✗ {error_msg}")
                stats['errors'].append(error_msg)
        
        old_cursor.close()
    
    old_db.close()
    
    print(f"\nMigration Summary:")
    print(f"Lines migrated: {stats['lines_migrated']}")
    print(f"Products created: {stats['products_created']}")
    print(f"Errors: {len(stats['errors'])}")
    
    if stats['errors']:
        print("\nErrors:")
        for error in stats['errors'][:10]:
            print(f"  - {error}")


if __name__ == '__main__':
    migrate_invoice_lines()