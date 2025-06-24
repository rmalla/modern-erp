#!/usr/bin/env python3
"""
Enhanced Sales Orders Migration Script with Order Lines

This script migrates sales orders AND their order lines from iDempiere,
following the same pattern as the successful purchase order migration.

IMPORTANT: This will preserve new orders created in the modern system:
- SO-14104 and SO-14105 will NOT be touched
- Only legacy orders (with legacy_id) will be affected
"""

import os
import sys
import django
import psycopg2
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from django.db import transaction
from core.models import BusinessPartner, BusinessPartnerLocation, Contact, PaymentTerms, Organization, Currency, User
from sales.models import SalesOrder, SalesOrderLine
from inventory.models import Product, Warehouse, PriceList
from djmoney.money import Money

def migrate_sales_orders_with_lines():
    """Migrate sales orders AND order lines from iDempiere"""
    
    # Connect to iDempiere database
    idempiere_conn = psycopg2.connect(
        host='localhost',
        database='idempiere',
        user='django_user',
        password='django_pass'
    )
    
    # Get default entities
    default_user = User.objects.first()
    default_org = Organization.objects.first()
    default_currency = Currency.objects.filter(iso_code='USD').first()
    default_payment_terms = PaymentTerms.objects.first()
    default_warehouse = Warehouse.objects.first()
    default_price_list = PriceList.objects.filter(is_sales_price_list=True).first()
    
    print(f"Defaults - User: {default_user}, Org: {default_org}")
    print(f"Currency: {default_currency}, Payment Terms: {default_payment_terms}")
    print(f"Warehouse: {default_warehouse}, Price List: {default_price_list}")
    
    # Create mappings
    bp_map = {}
    contact_map = {}
    location_map = {}
    product_map = {}
    
    # Build business partner mapping (ensure customers for sales orders)
    for bp in BusinessPartner.objects.exclude(legacy_id__isnull=True):
        if bp.legacy_id:
            bp_map[int(bp.legacy_id)] = bp
    
    # Build contact mapping
    for contact in Contact.objects.exclude(legacy_id__isnull=True):
        if contact.legacy_id:
            contact_map[int(contact.legacy_id)] = contact
    
    # Build location mapping
    for location in BusinessPartnerLocation.objects.exclude(legacy_id__isnull=True):
        if location.legacy_id:
            location_map[int(location.legacy_id)] = location
    
    # Build product mapping
    for product in Product.objects.exclude(legacy_id__isnull=True):
        if product.legacy_id:
            product_map[int(product.legacy_id)] = product
    
    print(f"Loaded mappings: {len(bp_map)} BPs, {len(contact_map)} contacts, {len(location_map)} locations, {len(product_map)} products")
    
    # Clear existing LEGACY sales orders only (preserve new orders)
    print("Clearing existing LEGACY sales orders...")
    legacy_orders = SalesOrder.objects.exclude(legacy_id__isnull=True)
    print(f"Found {legacy_orders.count()} legacy orders to remove")
    
    # Remove lines first, then orders
    for order in legacy_orders:
        order.lines.all().delete()
    legacy_orders.delete()
    
    print("Preserving new orders (SO-14104, SO-14105, etc.)")
    remaining_orders = SalesOrder.objects.filter(legacy_id__isnull=True)
    for order in remaining_orders:
        print(f"  Preserved: {order.document_no} - {order.business_partner.name}")
    
    cursor = idempiere_conn.cursor()
    
    # Get sales orders (issotrx = 'Y' for sales orders)
    cursor.execute("""
        SELECT 
            o.c_order_id,
            o.documentno,
            o.description,
            o.docstatus,
            o.dateordered,
            o.datepromised,
            o.c_bpartner_id,
            o.ad_user_id,
            o.c_bpartner_location_id,
            o.bill_location_id,
            o.grandtotal,
            o.issotrx,
            o.created,
            o.createdby,
            o.updated,
            o.updatedby,
            o.isactive,
            o.totallines
        FROM adempiere.c_order o
        WHERE o.issotrx = 'Y'  -- Sales orders only
        ORDER BY o.c_order_id
    """)
    
    orders_created = 0
    lines_created = 0
    errors = []
    
    for row in cursor.fetchall():
        try:
            bp = bp_map.get(row[6])
            if not bp:
                errors.append(f"No business partner found for SO {row[0]}")
                continue
            
            # Ensure this BP is marked as a customer for sales orders
            if not bp.is_customer:
                bp.is_customer = True
                bp.save()
                print(f"  Updated BP {bp.name} to be a customer")
            
            contact = contact_map.get(row[7]) if row[7] else None
            location = location_map.get(row[8]) if row[8] else None
            bill_to_location = location_map.get(row[9]) if row[9] else None
            
            # Map document status for sales orders
            doc_status_map = {
                'DR': 'drafted',
                'IP': 'in_progress', 
                'WP': 'waiting_payment',    # SO specific status
                'CO': 'complete',
                'CL': 'closed',
                'RE': 'reversed',
                'VO': 'voided'
            }
            
            sales_order = SalesOrder.objects.create(
                organization=default_org,
                document_no=row[1],
                description=row[2] or 'Migrated from iDempiere',
                doc_status=doc_status_map.get(row[3], 'drafted'),
                date_ordered=row[4] or '2022-01-01',  # Provide default if null
                date_promised=row[5],
                business_partner=bp,
                contact=contact,
                business_partner_location=location,
                bill_to_location=bill_to_location,
                currency=default_currency,
                price_list=default_price_list,
                warehouse=default_warehouse,
                payment_terms=default_payment_terms,
                total_lines=Money(Decimal(str(row[17])), 'USD') if row[17] else Money(0, 'USD'),
                grand_total=Money(Decimal(str(row[10])), 'USD') if row[10] else Money(0, 'USD'),
                created=row[12],
                created_by=default_user,
                updated=row[14],
                updated_by=default_user,
                is_active=(row[16] == 'Y'),
                legacy_id=str(row[0])
            )
            
            # Migrate sales order lines
            order_lines_created = migrate_sales_order_lines(cursor, row[0], sales_order, product_map, default_user)
            lines_created += order_lines_created
            
            orders_created += 1
            
            if orders_created <= 10:
                print(f"  Created SO: {sales_order.document_no} - {bp.name}")
                if contact:
                    print(f"    Contact: {contact.name}")
                if order_lines_created > 0:
                    print(f"    Lines: {order_lines_created}")
                    
        except Exception as e:
            errors.append(f"Sales Order {row[0]}: {str(e)}")
            print(f"  Error with SO {row[0]}: {str(e)}")
    
    cursor.close()
    idempiere_conn.close()
    
    print(f"\nMigration completed:")
    print(f"  Sales Orders: {orders_created}")
    print(f"  Order Lines: {lines_created}")
    
    if errors:
        print(f"Errors: {len(errors)}")
        for error in errors[:10]:
            print(f"  - {error}")

def migrate_sales_order_lines(cursor, old_order_id, new_order, product_map, default_user):
    """Migrate sales order lines for a specific order"""
    
    cursor.execute("""
        SELECT 
            ol.c_orderline_id,
            ol.line,
            ol.m_product_id,
            ol.qtyordered,
            ol.priceentered,
            ol.priceactual,
            ol.linenetamt,
            ol.description,
            ol.c_charge_id
        FROM adempiere.c_orderline ol
        WHERE ol.c_order_id = %s
        ORDER BY ol.line
    """, (old_order_id,))
    
    lines_created = 0
    
    for row in cursor.fetchall():
        try:
            product = None
            charge = None
            
            if row[2]:  # Product
                product = product_map.get(row[2])
                if not product:
                    print(f"    Warning: Product {row[2]} not found for SO line {row[0]}, skipping line")
                    continue
            
            # Skip lines with charges for now, focus on products
            if row[8] and not product:  # Has charge but no product
                print(f"    Skipping charge line {row[0]} - charges not yet migrated")
                continue
            
            if not product:
                print(f"    Skipping line {row[0]} - no product or charge")
                continue
            
            # Create the line using proper Money objects
            price_entered = Money(Decimal(str(row[4])), 'USD') if row[4] else Money(0, 'USD')
            price_actual = Money(Decimal(str(row[5])), 'USD') if row[5] else price_entered
            line_net_amount = Money(Decimal(str(row[6])), 'USD') if row[6] else Money(0, 'USD')
            
            SalesOrderLine.objects.create(
                order=new_order,
                line_no=row[1],
                product=product,
                charge=charge,
                quantity_ordered=Decimal(str(row[3])) if row[3] else Decimal('0.00'),
                price_entered=price_entered,
                price_actual=price_actual,
                price_list=price_entered,  # Set price_list same as price_entered
                line_net_amount=line_net_amount,
                description=row[7] or '',
                created_by=default_user,
                updated_by=default_user,
                legacy_id=str(row[0])
            )
            
            lines_created += 1
            
        except Exception as e:
            print(f"  Error with SO Line {row[0]}: {str(e)}")
    
    if lines_created > 0:
        print(f"    Created {lines_created} lines")
        # Recalculate order totals after adding lines
        new_order.calculate_totals()
    
    return lines_created

if __name__ == "__main__":
    print("Enhanced Sales Orders Migration with Order Lines")
    print("=" * 50)
    print("This will migrate sales orders AND their order lines from iDempiere")
    print("New orders (SO-14104, SO-14105) will be preserved")
    print()
    
    confirm = input("Continue? (y/N): ")
    if confirm.lower() == 'y':
        migrate_sales_orders_with_lines()
    else:
        print("Migration cancelled")