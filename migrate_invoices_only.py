#!/usr/bin/env python3
"""
Invoice Migration Script for Modern ERP System

This script migrates only sales invoices from the iDempiere database to the new Modern ERP Django system.
It's based on the existing migration pattern but focuses specifically on invoices.

Usage:
    python migrate_invoices_only.py

Requirements:
    - iDempiere backup restored to temp_idempiere database
    - Modern ERP Django application running
    - PostgreSQL access to both databases
"""

import os
import sys
import django
import psycopg2
from decimal import Decimal
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from core.models import BusinessPartner, Organization, Currency, User, UnitOfMeasure, Contact, BusinessPartnerLocation
from sales.models import SalesOrder, Invoice, InvoiceLine
from inventory.models import Product, ProductCategory, PriceList


class InvoiceMigrator:
    """Migrates sales invoices from iDempiere to Modern ERP"""
    
    def __init__(self):
        # Database connections
        self.old_db = psycopg2.connect(
            host='localhost',
            database='temp_idempiere',
            user='django_user',
            password='django_pass'
        )
        
        # Get default values
        self.default_org = Organization.objects.first()
        self.default_currency = Currency.objects.filter(iso_code='USD').first()
        self.default_user = User.objects.filter(is_superuser=True).first()
        self.default_uom = UnitOfMeasure.objects.first()
        self.default_category = ProductCategory.objects.first()
        
        # Statistics
        self.stats = {
            'invoices_migrated': 0,
            'invoice_lines_migrated': 0,
            'products_created': 0,
            'errors': []
        }
        
        # Create lookup maps for performance
        self.business_partner_map = {}
        self.contact_map = {}
        self.location_map = {}
        self.product_map = {}
        self.sales_order_map = {}
        self.opportunity_map = {}
        
        self._build_lookup_maps()
    
    def _build_lookup_maps(self):
        """Build lookup maps for foreign key relationships"""
        print("Building lookup maps...")
        
        # Business Partners
        for bp in BusinessPartner.objects.all():
            if bp.legacy_id:
                self.business_partner_map[bp.legacy_id] = bp
        
        # Contacts
        for contact in Contact.objects.all():
            if contact.legacy_id:
                self.contact_map[contact.legacy_id] = contact
        
        # Business Partner Locations
        for location in BusinessPartnerLocation.objects.all():
            if location.legacy_id:
                self.location_map[location.legacy_id] = location
        
        # Products
        for product in Product.objects.all():
            if product.legacy_id:
                self.product_map[product.legacy_id] = product
        
        # Sales Orders
        for so in SalesOrder.objects.all():
            if so.legacy_id:
                self.sales_order_map[so.legacy_id] = so
        
        # Opportunities
        from core.models import Opportunity
        for opp in Opportunity.objects.all():
            if opp.legacy_id:
                self.opportunity_map[opp.legacy_id] = opp
        
        print(f"Loaded {len(self.business_partner_map)} business partners")
        print(f"Loaded {len(self.contact_map)} contacts")
        print(f"Loaded {len(self.location_map)} locations")
        print(f"Loaded {len(self.product_map)} products")
        print(f"Loaded {len(self.sales_order_map)} sales orders")
        print(f"Loaded {len(self.opportunity_map)} opportunities")
    
    def migrate_invoices(self):
        """Migrate sales invoices from c_invoice"""
        print("Migrating Sales Invoices...")
        
        old_cursor = self.old_db.cursor()
        
        # Query sales invoices from iDempiere
        old_cursor.execute("""
            SELECT 
                c_invoice_id,
                documentno,
                description,
                docstatus,
                dateinvoiced,
                c_bpartner_id,
                ad_user_id,
                c_bpartner_location_id,
                grandtotal,
                totallines,
                c_order_id,
                created,
                createdby,
                updated,
                updatedby,
                isactive,
                c_paymentterm_id,
                custom_opportunity_id
            FROM adempiere.c_invoice
            WHERE issotrx = 'Y'  -- Sales invoices only
            ORDER BY c_invoice_id
        """)
        
        for row in old_cursor.fetchall():
            try:
                # Extract fields
                invoice_id = row[0]
                document_no = row[1]
                description = row[2] or ''
                doc_status = row[3]
                date_invoiced = row[4]
                bp_id = row[5]
                contact_id = row[6]
                bp_location_id = row[7]
                grand_total = row[8]
                total_lines = row[9]
                order_id = row[10]  # Reference to sales order
                created = row[11]
                updated = row[13]
                is_active = row[15]
                payment_term_id = row[16]
                opportunity_id = row[17]
                
                # Skip if invoice already exists
                if Invoice.objects.filter(legacy_id=str(invoice_id)).exists():
                    print(f"Invoice {document_no} already exists, skipping...")
                    continue
                
                # Find business partner
                business_partner = self.business_partner_map.get(str(bp_id))
                if not business_partner:
                    error_msg = f"Business Partner ID {bp_id} not found for Invoice {invoice_id}"
                    print(f"Warning: {error_msg}")
                    self.stats['errors'].append(error_msg)
                    continue
                
                # Find contact (optional)
                contact = None
                if contact_id:
                    contact = self.contact_map.get(str(contact_id))
                
                # Find locations
                bp_location = None
                if bp_location_id:
                    bp_location = self.location_map.get(str(bp_location_id))
                
                # Use bp_location as bill_to_location since we don't have separate billing address
                bill_to_location = bp_location
                
                # Find related sales order (optional)
                sales_order = None
                if order_id:
                    sales_order = self.sales_order_map.get(str(order_id))
                
                # Find related opportunity (optional)
                opportunity = None
                if opportunity_id:
                    opportunity = self.opportunity_map.get(str(opportunity_id))
                elif sales_order and sales_order.opportunity:
                    opportunity = sales_order.opportunity
                
                # Map document status
                doc_status_map = {
                    'DR': 'drafted',
                    'IP': 'in_progress',
                    'CO': 'complete',
                    'CL': 'closed',
                    'RE': 'reversed',
                    'VO': 'voided'
                }
                
                # Calculate due date (default 30 days from invoice date)
                due_date = date_invoiced + timedelta(days=30)
                
                # Get default price list
                price_list = PriceList.objects.filter(is_sales_price_list=True).first()
                
                # Create the invoice
                invoice = Invoice.objects.create(
                    organization=self.default_org,
                    document_no=document_no,
                    description=description,
                    doc_status=doc_status_map.get(doc_status, 'drafted'),
                    invoice_type='standard',
                    
                    # Dates
                    date_invoiced=date_invoiced,
                    date_accounting=date_invoiced,
                    due_date=due_date,
                    
                    # Business partner and contacts
                    business_partner=business_partner,
                    contact=contact,
                    internal_user=self.default_user,  # Our company contact
                    
                    # Addresses
                    business_partner_location=bp_location,
                    bill_to_location=bill_to_location,
                    
                    # References
                    sales_order=sales_order,
                    opportunity=opportunity,
                    
                    # Pricing
                    price_list=price_list,
                    currency=self.default_currency,
                    payment_terms='Net 30',  # Default payment terms
                    
                    # Totals
                    total_lines=Decimal(str(total_lines)) if total_lines else Decimal('0.00'),
                    grand_total=Decimal(str(grand_total)) if grand_total else Decimal('0.00'),
                    open_amount=Decimal(str(grand_total)) if grand_total else Decimal('0.00'),
                    
                    # Sales rep
                    sales_rep=self.default_user,
                    
                    # Audit fields
                    created=created,
                    created_by=self.default_user,
                    updated=updated,
                    updated_by=self.default_user,
                    is_active=is_active == 'Y',
                    legacy_id=str(invoice_id)
                )
                
                # Migrate invoice lines
                self.migrate_invoice_lines(invoice_id, invoice)
                
                self.stats['invoices_migrated'] += 1
                print(f"✓ Migrated Invoice: {document_no}")
                
            except Exception as e:
                error_msg = f"Error migrating Invoice ID {invoice_id}: {str(e)}"
                print(f"✗ {error_msg}")
                self.stats['errors'].append(error_msg)
        
        old_cursor.close()
        print(f"Completed: {self.stats['invoices_migrated']} invoices migrated")
    
    def migrate_invoice_lines(self, old_invoice_id, new_invoice):
        """Migrate invoice lines for a given invoice"""
        old_cursor = self.old_db.cursor()
        
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
                c_orderline_id,
                c_tax_id
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
                tax_id = row[9]
                
                # Find or create product
                product = None
                if product_id:
                    product = self.product_map.get(str(product_id))
                    if not product:
                        # Create placeholder product
                        product = Product.objects.create(
                            code=f"MIGRATED-{product_id}",
                            name=f"Migrated Product {product_id}",
                            description=f"Product migrated from iDempiere ID: {product_id}",
                            product_category=self.default_category,
                            uom=self.default_uom,
                            is_sold=True,
                            is_purchased=False,
                            created_by=self.default_user,
                            updated_by=self.default_user,
                            legacy_id=str(product_id)
                        )
                        self.product_map[str(product_id)] = product
                        self.stats['products_created'] += 1
                        print(f"  → Created placeholder product: {product.code}")
                
                # Find related order line (optional)
                order_line = None
                if order_line_id and new_invoice.sales_order:
                    order_line = new_invoice.sales_order.lines.filter(legacy_id=str(order_line_id)).first()
                
                # Create invoice line
                InvoiceLine.objects.create(
                    invoice=new_invoice,
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
                    discount=Decimal('0'),  # No discount info available in iDempiere
                    line_net_amount=Decimal(str(line_net_amount)) if line_net_amount else Decimal('0'),
                    
                    # Audit
                    created_by=self.default_user,
                    updated_by=self.default_user,
                    legacy_id=str(line_id)
                )
                
                self.stats['invoice_lines_migrated'] += 1
                
            except Exception as e:
                error_msg = f"Error migrating Invoice Line ID {line_id}: {str(e)}"
                print(f"    ✗ {error_msg}")
                self.stats['errors'].append(error_msg)
        
        old_cursor.close()
    
    def run_migration(self):
        """Run the invoice migration process"""
        print("Starting Invoice Migration from iDempiere...")
        print("=" * 60)
        
        start_time = datetime.now()
        
        try:
            self.migrate_invoices()
            
            # Print summary
            print("\n" + "=" * 60)
            print("INVOICE MIGRATION SUMMARY")
            print("=" * 60)
            print(f"Invoices migrated: {self.stats['invoices_migrated']}")
            print(f"Invoice lines migrated: {self.stats['invoice_lines_migrated']}")
            print(f"Products created: {self.stats['products_created']}")
            print(f"Errors: {len(self.stats['errors'])}")
            
            if self.stats['errors']:
                print("\nERRORS:")
                for error in self.stats['errors'][:10]:  # Show first 10 errors
                    print(f"  - {error}")
                if len(self.stats['errors']) > 10:
                    print(f"  ... and {len(self.stats['errors']) - 10} more errors")
            
            elapsed_time = datetime.now() - start_time
            print(f"\nMigration completed in: {elapsed_time}")
            
        except Exception as e:
            print(f"Migration failed: {str(e)}")
            raise
        
        finally:
            if hasattr(self, 'old_db'):
                self.old_db.close()


def main():
    """Main migration function"""
    print("Invoice Migration Script")
    print("=" * 40)
    
    # Confirm before proceeding
    response = input("This will migrate invoices from iDempiere. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return
    
    # Run migration
    migrator = InvoiceMigrator()
    migrator.run_migration()
    
    print("\nInvoice migration completed!")


if __name__ == '__main__':
    main()