#!/usr/bin/env python3
"""
Purchase Orders Only Migration Script

This script migrates only the purchase orders from iDempiere.
Purchase orders are identified by issotrx = 'N' (not sales transactions).
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
from purchasing.models import PurchaseOrder, PurchaseOrderLine
from inventory.models import Product, Warehouse, PriceList

def migrate_purchase_orders():
    """Migrate purchase orders from iDempiere"""
    
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
    default_price_list = PriceList.objects.filter(is_purchase_price_list=True).first()
    
    print(f"Defaults - User: {default_user}, Org: {default_org}")
    print(f"Currency: {default_currency}, Payment Terms: {default_payment_terms}")
    print(f"Warehouse: {default_warehouse}, Price List: {default_price_list}")
    
    # Create mappings
    bp_map = {}
    contact_map = {}
    location_map = {}
    product_map = {}
    
    # Build business partner mapping (ensure vendors for purchase orders)
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
    
    # Clear existing purchase orders first
    print("Clearing existing purchase orders...")
    PurchaseOrderLine.objects.all().delete()
    PurchaseOrder.objects.all().delete()
    
    cursor = idempiere_conn.cursor()
    
    # Get purchase orders (issotrx = 'N' for purchase orders)
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
            o.poreference
        FROM adempiere.c_order o
        WHERE o.issotrx = 'N'  -- Purchase orders only
        ORDER BY o.c_order_id
    """)
    
    orders_created = 0
    errors = []
    
    for row in cursor.fetchall():
        try:
            bp = bp_map.get(row[6])
            if not bp:
                errors.append(f"No business partner found for PO {row[0]}")
                continue
            
            # Ensure this BP is marked as a vendor for purchase orders
            if not bp.is_vendor:
                bp.is_vendor = True
                bp.save()
                print(f"  Updated BP {bp.name} to be a vendor")
            
            contact = contact_map.get(row[7]) if row[7] else None
            location = location_map.get(row[8]) if row[8] else None
            bill_to_location = location_map.get(row[9]) if row[9] else None
            
            # Map document status for purchase orders
            doc_status_map = {
                'DR': 'drafted',
                'IP': 'in_progress', 
                'WD': 'waiting_delivery',    # PO specific status
                'WI': 'waiting_invoice',     # PO specific status
                'CO': 'complete',
                'CL': 'closed',
                'RE': 'reversed',
                'VO': 'voided'
            }
            
            purchase_order = PurchaseOrder.objects.create(
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
                vendor_reference=row[17] or '',  # PO reference field
                currency=default_currency,
                price_list=default_price_list,
                warehouse=default_warehouse,
                # payment_terms=default_payment_terms,  # Skip payment_terms for now
                grand_total=Decimal(str(row[10])) if row[10] else Decimal('0.00'),
                buyer=default_user,
                created=row[12],
                created_by=default_user,
                updated=row[14],
                updated_by=default_user,
                is_active=(row[16] == 'Y'),
                legacy_id=str(row[0])
            )
            
            # Migrate purchase order lines
            migrate_purchase_order_lines(cursor, row[0], purchase_order, product_map, default_user)
            
            orders_created += 1
            
            if orders_created <= 10:
                print(f"  Created PO: {purchase_order.document_no} - {bp.name}")
                if contact:
                    print(f"    Contact: {contact.name}")
                if row[17]:  # vendor reference
                    print(f"    Vendor Ref: {row[17]}")
                    
        except Exception as e:
            errors.append(f"Purchase Order {row[0]}: {str(e)}")
            print(f"  Error with PO {row[0]}: {str(e)}")
    
    cursor.close()
    idempiere_conn.close()
    
    print(f"\nMigrated {orders_created} purchase orders")
    if errors:
        print(f"Errors: {len(errors)}")
        for error in errors[:10]:
            print(f"  - {error}")

def migrate_purchase_order_lines(cursor, old_order_id, new_order, product_map, default_user):
    """Migrate purchase order lines for a specific order"""
    
    cursor.execute("""
        SELECT 
            ol.c_orderline_id,
            ol.line,
            ol.m_product_id,
            ol.qtyordered,
            ol.priceentered,
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
                    print(f"    Warning: Product {row[2]} not found for PO line {row[0]}, skipping line")
                    continue
            
            # Skip lines with charges for now, focus on products
            if row[7] and not product:  # Has charge but no product
                print(f"    Skipping charge line {row[0]} - charges not yet migrated")
                continue
            
            if not product:
                print(f"    Skipping line {row[0]} - no product or charge")
                continue
            
            PurchaseOrderLine.objects.create(
                order=new_order,
                line_no=row[1],
                product=product,
                charge=charge,
                quantity_ordered=Decimal(str(row[3])) if row[3] else Decimal('0.00'),
                price_entered=Decimal(str(row[4])) if row[4] else Decimal('0.00'),
                price_actual=Decimal(str(row[4])) if row[4] else Decimal('0.00'),
                line_net_amount=Decimal(str(row[5])) if row[5] else Decimal('0.00'),
                description=row[6] or '',
                created_by=default_user,
                updated_by=default_user,
                legacy_id=str(row[0])
            )
            
            lines_created += 1
            
        except Exception as e:
            print(f"  Error with PO Line {row[0]}: {str(e)}")
    
    if lines_created > 0:
        print(f"    Created {lines_created} lines")

if __name__ == "__main__":
    migrate_purchase_orders() 