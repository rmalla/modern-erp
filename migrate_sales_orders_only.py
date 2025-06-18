#!/usr/bin/env python3
"""
Sales Orders Only Migration Script

This script migrates only the sales orders from iDempiere.
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
from core.models import BusinessPartner, BusinessPartnerLocation, Contact, PaymentTerms
from sales.models import SalesOrder, SalesOrderLine
from inventory.models import Product, Warehouse, PriceList
from core.models import Organization, Currency, User

def migrate_sales_orders():
    """Migrate sales orders from iDempiere"""
    
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
    
    # Build business partner mapping
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
    
    print(f"Loaded mappings: {len(bp_map)} BPs, {len(contact_map)} contacts, {len(location_map)} locations")
    
    # Clear existing sales orders first
    print("Clearing existing sales orders...")
    SalesOrderLine.objects.all().delete()
    SalesOrder.objects.all().delete()
    
    cursor = idempiere_conn.cursor()
    
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
            o.isactive
        FROM adempiere.c_order o
        WHERE o.issotrx = 'Y'  -- Sales orders only
        ORDER BY o.c_order_id
    """)
    
    orders_created = 0
    errors = []
    
    for row in cursor.fetchall():
        try:
            bp = bp_map.get(row[6])
            if not bp:
                errors.append(f"No business partner found for SO {row[0]}")
                continue
            
            contact = contact_map.get(row[7]) if row[7] else None
            location = location_map.get(row[8]) if row[8] else None
            bill_to_location = location_map.get(row[9]) if row[9] else None
            
            # Map document status
            doc_status_map = {
                'DR': 'drafted',
                'IP': 'in_progress', 
                'WP': 'waiting_payment',
                'CO': 'complete',
                'CL': 'closed',
                'RE': 'reversed',
                'VO': 'voided'
            }
            
            sales_order = SalesOrder.objects.create(
                organization=default_org,
                document_no=row[1],
                description=row[2] or '',
                doc_status=doc_status_map.get(row[3], 'drafted'),
                date_ordered=row[4],
                date_promised=row[5],
                business_partner=bp,
                contact=contact,
                business_partner_location=location,
                bill_to_location=bill_to_location,
                currency=default_currency,
                price_list=default_price_list,
                warehouse=default_warehouse,
                payment_terms=default_payment_terms,
                grand_total=Decimal(str(row[10])) if row[10] else Decimal('0.00'),
                created=row[12],
                created_by=default_user,
                updated=row[14],
                updated_by=default_user,
                is_active=(row[16] == 'Y'),
                legacy_id=str(row[0])
            )
            
            orders_created += 1
            
            if orders_created <= 10:
                print(f"  Created SO: {sales_order.document_no} - {bp.name}")
                if contact:
                    print(f"    Contact: {contact.name}")
                    
        except Exception as e:
            errors.append(f"Sales Order {row[0]}: {str(e)}")
            print(f"  Error with SO {row[0]}: {str(e)}")
    
    cursor.close()
    idempiere_conn.close()
    
    print(f"\nMigrated {orders_created} sales orders")
    if errors:
        print(f"Errors: {len(errors)}")
        for error in errors[:10]:
            print(f"  - {error}")

if __name__ == "__main__":
    migrate_sales_orders()