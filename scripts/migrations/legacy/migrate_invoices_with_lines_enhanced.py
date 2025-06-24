#!/usr/bin/env python3
"""
Enhanced Invoice Migration Script with Invoice Lines

This script migrates invoices AND their invoice lines from iDempiere,
following the same successful pattern as the sales order migration.

IMPORTANT: This will preserve new invoices created in the modern system:
- Only invoices with legacy_id will be affected
- New invoices (without legacy_id) will NOT be touched
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
from sales.models import Invoice, InvoiceLine, SalesOrder
from inventory.models import Product, Warehouse, PriceList
from djmoney.money import Money

def migrate_invoices_with_lines():
    """Migrate invoices AND invoice lines from iDempiere"""
    
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
    
    # Create mappings for performance
    bp_map = {}
    contact_map = {}
    location_map = {}
    product_map = {}
    sales_order_map = {}
    
    # Build business partner mapping
    for bp in BusinessPartner.objects.exclude(legacy_id__isnull=True):
        if bp.legacy_id:
            try:
                legacy_key = int(bp.legacy_id)
            except ValueError:
                legacy_key = bp.legacy_id
            bp_map[legacy_key] = bp
    
    # Build contact mapping
    for contact in Contact.objects.exclude(legacy_id__isnull=True):
        if contact.legacy_id:
            try:
                legacy_key = int(contact.legacy_id)
            except ValueError:
                legacy_key = contact.legacy_id
            contact_map[legacy_key] = contact
    
    # Build location mapping
    for location in BusinessPartnerLocation.objects.exclude(legacy_id__isnull=True):
        if location.legacy_id:
            try:
                legacy_key = int(location.legacy_id)
            except ValueError:
                legacy_key = location.legacy_id
            location_map[legacy_key] = location
    
    # Build product mapping
    for product in Product.objects.exclude(legacy_id__isnull=True):
        if product.legacy_id:
            try:
                legacy_key = int(product.legacy_id)
            except ValueError:
                legacy_key = product.legacy_id
            product_map[legacy_key] = product
    
    # Build sales order mapping
    for order in SalesOrder.objects.exclude(legacy_id__isnull=True):
        if order.legacy_id:
            try:
                legacy_key = int(order.legacy_id)
            except ValueError:
                legacy_key = order.legacy_id
            sales_order_map[legacy_key] = order
    
    print(f"Loaded mappings: {len(bp_map)} BPs, {len(contact_map)} contacts, {len(location_map)} locations")
    print(f"Products: {len(product_map)}, Sales Orders: {len(sales_order_map)}")
    
    # Preserve new invoices (those without legacy_id)
    print("Preserving new invoices...")
    new_invoices = []
    for invoice in Invoice.objects.filter(legacy_id__isnull=True):
        new_invoices.append({
            'id': invoice.id,
            'document_no': invoice.document_no,
            'partner': invoice.business_partner.name,
            'total': invoice.grand_total
        })
        print(f"  Will preserve: {invoice.document_no} - {invoice.business_partner.name} - {invoice.grand_total}")
    
    # Clear existing LEGACY invoices only
    print("Clearing existing LEGACY invoices...")
    legacy_invoices = Invoice.objects.exclude(legacy_id__isnull=True)
    print(f"Found {legacy_invoices.count()} legacy invoices to remove")
    
    # Remove lines first, then invoices
    for invoice in legacy_invoices:
        invoice.lines.all().delete()
    legacy_invoices.delete()
    
    cursor = idempiere_conn.cursor()
    
    # Get invoices from iDempiere (issotrx = 'Y' for sales invoices)
    cursor.execute("""
        SELECT 
            i.c_invoice_id,
            i.documentno,
            i.description,
            i.docstatus,
            i.dateinvoiced,
            i.dateacct,
            i.c_bpartner_id,
            i.ad_user_id,
            i.c_bpartner_location_id,
            i.bill_location_id,
            i.grandtotal,
            i.totallines,
            i.c_order_id,
            i.issotrx,
            i.created,
            i.createdby,
            i.updated,
            i.updatedby,
            i.isactive,
            i.ispaid
        FROM adempiere.c_invoice i
        WHERE i.issotrx = 'Y'  -- Sales invoices only
        ORDER BY i.c_invoice_id
    """)
    
    invoices_created = 0
    lines_created = 0
    errors = []
    
    for row in cursor.fetchall():
        try:
            bp = bp_map.get(row[6])
            if not bp:
                errors.append(f"No business partner found for Invoice {row[0]}")
                continue
            
            # Ensure this BP is marked as a customer for sales invoices
            if not bp.is_customer:
                bp.is_customer = True
                bp.save()
                print(f"  Updated BP {bp.name} to be a customer")
            
            contact = contact_map.get(row[7]) if row[7] else None
            location = location_map.get(row[8]) if row[8] else None
            bill_to_location = location_map.get(row[9]) if row[9] else None
            sales_order = sales_order_map.get(row[12]) if row[12] else None
            
            # Map document status for invoices
            doc_status_map = {
                'DR': 'drafted',
                'IP': 'in_progress',
                'CO': 'complete',
                'CL': 'closed',
                'RE': 'reversed',
                'VO': 'voided'
            }
            
            invoice = Invoice.objects.create(
                organization=default_org,
                document_no=row[1],
                description=row[2] or 'Migrated from iDempiere',
                doc_status=doc_status_map.get(row[3], 'drafted'),
                date_invoiced=row[4] or '2022-01-01',
                date_acct=row[5] or row[4] or '2022-01-01',
                business_partner=bp,
                contact=contact,
                business_partner_location=location,
                bill_to_location=bill_to_location,
                sales_order=sales_order,
                currency=default_currency,
                price_list=default_price_list,
                warehouse=default_warehouse,
                payment_terms=default_payment_terms,
                total_lines=Money(Decimal(str(row[11])), 'USD') if row[11] else Money(0, 'USD'),
                grand_total=Money(Decimal(str(row[10])), 'USD') if row[10] else Money(0, 'USD'),
                is_paid=(row[19] == 'Y'),
                created=row[14],
                created_by=default_user,
                updated=row[16],
                updated_by=default_user,
                is_active=(row[18] == 'Y'),
                legacy_id=str(row[0])
            )
            
            # Migrate invoice lines
            invoice_lines_created = migrate_invoice_lines(cursor, row[0], invoice, product_map, default_user)
            lines_created += invoice_lines_created
            
            invoices_created += 1
            
            if invoices_created <= 10:
                print(f"  Created Invoice: {invoice.document_no} - {bp.name}")
                if contact:
                    print(f"    Contact: {contact.name}")
                if sales_order:
                    print(f"    Sales Order: {sales_order.document_no}")
                if invoice_lines_created > 0:
                    print(f"    Lines: {invoice_lines_created}")
                    
        except Exception as e:
            errors.append(f"Invoice {row[0]}: {str(e)}")
            print(f"  Error with Invoice {row[0]}: {str(e)}")
    
    cursor.close()
    idempiere_conn.close()
    
    print(f"\nMigration completed:")
    print(f"  Invoices: {invoices_created}")
    print(f"  Invoice Lines: {lines_created}")
    
    if errors:
        print(f"Errors: {len(errors)}")
        for error in errors[:10]:
            print(f"  - {error}")
    
    # Verify preservation of new invoices
    print(f"\nVerification - Preserved {len(new_invoices)} new invoices:")
    for preserved in new_invoices:
        try:
            invoice = Invoice.objects.get(id=preserved['id'])
            print(f"  ✓ {invoice.document_no} - {invoice.business_partner.name} - {invoice.grand_total}")
        except Invoice.DoesNotExist:
            print(f"  ✗ Invoice ID {preserved['id']} was accidentally deleted!")

def migrate_invoice_lines(cursor, old_invoice_id, new_invoice, product_map, default_user):
    """Migrate invoice lines for a specific invoice"""
    
    cursor.execute("""
        SELECT 
            il.c_invoiceline_id,
            il.line,
            il.m_product_id,
            il.qtyinvoiced,
            il.priceentered,
            il.priceactual,
            il.linenetamt,
            il.description,
            il.c_charge_id
        FROM adempiere.c_invoiceline il
        WHERE il.c_invoice_id = %s
        ORDER BY il.line
    """, (old_invoice_id,))
    
    lines_created = 0
    
    for row in cursor.fetchall():
        try:
            product = None
            charge = None
            
            if row[2]:  # Product
                product = product_map.get(row[2])
                if not product:
                    print(f"    Warning: Product {row[2]} not found for Invoice line {row[0]}, skipping line")
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
            
            InvoiceLine.objects.create(
                invoice=new_invoice,
                line_no=row[1],
                product=product,
                charge=charge,
                quantity_invoiced=Decimal(str(row[3])) if row[3] else Decimal('0.00'),
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
            print(f"  Error with Invoice Line {row[0]}: {str(e)}")
    
    if lines_created > 0:
        print(f"    Created {lines_created} lines")
        # Recalculate invoice totals after adding lines
        new_invoice.calculate_totals()
    
    return lines_created

if __name__ == "__main__":
    print("Enhanced Invoice Migration with Invoice Lines")
    print("=" * 50)
    print("This will migrate invoices AND their invoice lines from iDempiere")
    print("New invoices (without legacy_id) will be preserved")
    print()
    
    confirm = input("Continue? (y/N): ")
    if confirm.lower() == 'y':
        migrate_invoices_with_lines()
    else:
        print("Migration cancelled")