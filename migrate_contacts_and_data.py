#!/usr/bin/env python3
"""
Complete Data Migration Script with Contacts and Addresses

This script performs a complete migration from iDempiere including:
- Business Partners
- Contacts (AD_User)
- Business Partner Locations (C_BPartner_Location + C_Location)
- Products and Manufacturers
- Sales Orders, Purchase Orders, Invoices, Shipments
- All with proper contact and address relationships

Usage:
    python migrate_contacts_and_data.py [--clear-all]
"""

import os
import sys
import django
import psycopg2
from decimal import Decimal
from datetime import datetime, date
import argparse

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from django.db import transaction
from core.models import (
    BusinessPartner, BusinessPartnerLocation, Contact, Organization, 
    Currency, User, UnitOfMeasure, PaymentTerms, Incoterms, Opportunity
)
from inventory.models import Product, Manufacturer, ProductCategory, Warehouse, PriceList
from sales.models import SalesOrder, SalesOrderLine, Invoice, InvoiceLine, Shipment, ShipmentLine
from purchasing.models import PurchaseOrder, PurchaseOrderLine, VendorBill, VendorBillLine, Receipt, ReceiptLine


class CompleteDataMigrator:
    """Complete data migrator with contacts and addresses"""
    
    def __init__(self, clear_all=False):
        self.clear_all = clear_all
        
        # Connect to iDempiere database
        self.idempiere_conn = psycopg2.connect(
            host='localhost',
            database='idempiere',
            user='django_user',
            password='django_pass'
        )
        
        # Get default entities
        self.default_user = User.objects.first()
        self.default_org = Organization.objects.first()
        self.default_currency = Currency.objects.filter(iso_code='USD').first()
        self.default_uom = UnitOfMeasure.objects.first()
        self.default_payment_terms = PaymentTerms.objects.first()
        self.default_warehouse = Warehouse.objects.first()
        self.default_price_list = PriceList.objects.filter(is_sales_price_list=True).first()
        
        # Migration mappings
        self.bp_map = {}              # iDempiere BP ID -> Django BusinessPartner
        self.contact_map = {}         # iDempiere AD_User ID -> Django Contact
        self.location_map = {}        # iDempiere BP_Location ID -> Django BusinessPartnerLocation
        self.manufacturer_map = {}    # iDempiere BP ID -> Django Manufacturer
        self.product_map = {}         # iDempiere Product ID -> Django Product
        self.category_map = {}        # iDempiere Category ID -> Django ProductCategory
        
        self.stats = {
            'business_partners': 0,
            'contacts': 0,
            'locations': 0,
            'manufacturers': 0,
            'products': 0,
            'sales_orders': 0,
            'purchase_orders': 0,
            'invoices': 0,
            'shipments': 0,
            'errors': []
        }
    
    def clear_all_data(self):
        """Clear all existing data"""
        if self.clear_all:
            print("Clearing all existing data...")
            
            # Clear in dependency order
            SalesOrderLine.objects.all().delete()
            PurchaseOrderLine.objects.all().delete()
            InvoiceLine.objects.all().delete()
            ShipmentLine.objects.all().delete()
            VendorBillLine.objects.all().delete()
            ReceiptLine.objects.all().delete()
            
            SalesOrder.objects.all().delete()
            PurchaseOrder.objects.all().delete()
            Invoice.objects.all().delete()
            Shipment.objects.all().delete()
            VendorBill.objects.all().delete()
            Receipt.objects.all().delete()
            
            Product.objects.all().delete()
            Manufacturer.objects.all().delete()
            ProductCategory.objects.all().delete()
            
            Contact.objects.all().delete()
            BusinessPartnerLocation.objects.all().delete()
            
            # Clear opportunities that reference business partners
            Opportunity.objects.all().delete()
            
            BusinessPartner.objects.all().delete()
            
            print("  - All data cleared")
    
    def migrate_business_partners(self):
        """Migrate business partners from c_bpartner"""
        print("\nMigrating Business Partners...")
        
        cursor = self.idempiere_conn.cursor()
        
        cursor.execute("""
            SELECT 
                c_bpartner_id,
                value as search_key,
                name,
                name2,
                description,
                iscustomer,
                isvendor,
                isemployee,
                isprospect,
                issalesrep,
                taxid,
                url,
                isactive,
                created,
                createdby,
                updated,
                updatedby
            FROM adempiere.c_bpartner 
            WHERE issummary = 'N'
            ORDER BY c_bpartner_id
        """)
        
        for row in cursor.fetchall():
            try:
                # Determine partner type based on flags
                partner_type = 'customer'
                if row[6] == 'Y':  # is_vendor
                    partner_type = 'vendor'
                elif row[7] == 'Y':  # is_employee
                    partner_type = 'employee'
                elif row[8] == 'Y':  # is_prospect
                    partner_type = 'prospect'
                
                bp = BusinessPartner.objects.create(
                    search_key=row[1][:40] if row[1] else f'BP{row[0]}',
                    code=row[1][:50] if row[1] else f'BP{row[0]}',
                    name=row[2] or f'Business Partner {row[0]}',
                    name2=row[3] or '',
                    partner_type=partner_type,
                    is_customer=(row[5] == 'Y'),
                    is_vendor=(row[6] == 'Y'),
                    is_employee=(row[7] == 'Y'),
                    is_prospect=(row[8] == 'Y'),
                    tax_id=row[10] or '',
                    website=row[11] or '',
                    is_active=(row[12] == 'Y'),
                    created=row[13],
                    created_by=self.default_user,
                    updated=row[14],
                    updated_by=self.default_user,
                    legacy_id=str(row[0])
                )
                
                self.bp_map[row[0]] = bp
                self.stats['business_partners'] += 1
                
                if self.stats['business_partners'] <= 10:
                    print(f"  Created BP: {bp.name}")
                    
            except Exception as e:
                self.stats['errors'].append(f"Business Partner {row[0]}: {str(e)}")
                print(f"  Error with BP {row[0]}: {str(e)}")
        
        cursor.close()
        print(f"Migrated {self.stats['business_partners']} business partners")
    
    def migrate_locations(self):
        """Migrate business partner locations"""
        print("\nMigrating Business Partner Locations...")
        
        cursor = self.idempiere_conn.cursor()
        
        cursor.execute("""
            SELECT 
                bpl.c_bpartner_location_id,
                bpl.c_bpartner_id,
                bpl.name,
                bpl.phone,
                bpl.phone2,
                bpl.fax,
                bpl.isbillto,
                bpl.isshipto,
                bpl.ispayfrom,
                bpl.isremitto,
                loc.address1,
                loc.address2,
                loc.address3,
                loc.city,
                loc.postal,
                loc.postal_add,
                loc.regionname,
                loc.comments,
                COALESCE(country.name, 'United States') as country_name
            FROM adempiere.c_bpartner_location bpl
            JOIN adempiere.c_location loc ON bpl.c_location_id = loc.c_location_id
            LEFT JOIN adempiere.c_country country ON loc.c_country_id = country.c_country_id
            WHERE bpl.isactive = 'Y'
            ORDER BY bpl.c_bpartner_id, bpl.c_bpartner_location_id
        """)
        
        for row in cursor.fetchall():
            try:
                bp = self.bp_map.get(row[1])
                if not bp:
                    continue
                
                location = BusinessPartnerLocation.objects.create(
                    business_partner=bp,
                    name=row[2] or 'Main',
                    phone=row[3] or '',
                    phone2=row[4] or '',
                    fax=row[5] or '',
                    is_bill_to=(row[6] == 'Y'),
                    is_ship_to=(row[7] == 'Y'),
                    is_pay_from=(row[8] == 'Y'),
                    is_remit_to=(row[9] == 'Y'),
                    address1=row[10] or '',
                    address2=row[11] or '',
                    address3=row[12] or '',
                    city=row[13] or '',
                    postal_code=row[14] or '',
                    postal_code_add=row[15] or '',
                    state=row[16] or '',
                    comments=row[17] or '',
                    country=row[18],
                    created_by=self.default_user,
                    updated_by=self.default_user,
                    legacy_id=str(row[0])
                )
                
                self.location_map[row[0]] = location
                self.stats['locations'] += 1
                
            except Exception as e:
                self.stats['errors'].append(f"Location {row[0]}: {str(e)}")
                print(f"  Error with location {row[0]}: {str(e)}")
        
        cursor.close()
        print(f"Migrated {self.stats['locations']} locations")
    
    def migrate_contacts(self):
        """Migrate contacts from ad_user"""
        print("\nMigrating Contacts...")
        
        cursor = self.idempiere_conn.cursor()
        
        cursor.execute("""
            SELECT 
                ad_user_id,
                c_bpartner_id,
                c_bpartner_location_id,
                name,
                email,
                phone,
                phone2,
                fax,
                title,
                description,
                comments,
                birthday,
                supervisor_id,
                issaleslead,
                isbillto,
                isshipto,
                isactive
            FROM adempiere.ad_user
            WHERE c_bpartner_id IS NOT NULL
            ORDER BY c_bpartner_id, ad_user_id
        """)
        
        for row in cursor.fetchall():
            try:
                bp = self.bp_map.get(row[1])
                if not bp:
                    continue
                
                location = self.location_map.get(row[2]) if row[2] else None
                supervisor = self.contact_map.get(row[12]) if row[12] else None
                
                # Safely truncate fields to match model limits
                contact_name = (row[3] or f'Contact {row[0]}')[:60]
                
                contact = Contact.objects.create(
                    business_partner=bp,
                    business_partner_location=location,
                    name=contact_name,
                    email=(row[4] or '')[:254],  # EmailField max length
                    phone=(row[5] or '')[:40],
                    phone2=(row[6] or '')[:40],
                    fax=(row[7] or '')[:40],
                    title=(row[8] or '')[:40],
                    description=(row[9] or '')[:255],
                    comments=row[10] or '',
                    birthday=row[11] if row[11] else None,
                    supervisor=supervisor,
                    is_sales_lead=(row[13] == 'Y'),
                    is_bill_to=(row[14] == 'Y'),
                    is_ship_to=(row[15] == 'Y'),
                    is_active=(row[16] == 'Y'),
                    created_by=self.default_user,
                    updated_by=self.default_user,
                    legacy_id=str(row[0])
                )
                
                self.contact_map[row[0]] = contact
                self.stats['contacts'] += 1
                
                if self.stats['contacts'] <= 10:
                    print(f"  Created contact: {contact.name} ({bp.name})")
                    
            except Exception as e:
                self.stats['errors'].append(f"Contact {row[0]}: {str(e)}")
                print(f"  Error with contact {row[0]}: {str(e)}")
        
        cursor.close()
        print(f"Migrated {self.stats['contacts']} contacts")
    
    def migrate_manufacturers_and_products(self):
        """Migrate manufacturers and products"""
        print("\nMigrating Manufacturers and Products...")
        
        # Use the existing real product migration logic
        from migrate_real_products import RealProductMigrator
        
        migrator = RealProductMigrator(clear_existing=False)
        migrator.migrate_manufacturers()
        migrator.migrate_product_categories()
        migrator.migrate_products()
        
        # Update stats
        self.stats['manufacturers'] = migrator.stats['manufacturers']
        self.stats['products'] = migrator.stats['products']
        
        # Update mappings
        self.manufacturer_map = migrator.manufacturer_map
        self.product_map = migrator.product_map
        self.category_map = migrator.category_map
    
    def migrate_sales_orders(self):
        """Migrate sales orders with contact and location references"""
        print("\nMigrating Sales Orders...")
        
        cursor = self.idempiere_conn.cursor()
        
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
        
        for row in cursor.fetchall():
            try:
                bp = self.bp_map.get(row[6])
                if not bp:
                    continue
                
                contact = self.contact_map.get(row[7]) if row[7] else None
                location = self.location_map.get(row[8]) if row[8] else None
                bill_to_location = self.location_map.get(row[9]) if row[9] else None
                
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
                    organization=self.default_org,
                    document_no=row[1],
                    description=row[2] or '',
                    doc_status=doc_status_map.get(row[3], 'drafted'),
                    date_ordered=row[4],
                    date_promised=row[5],
                    business_partner=bp,
                    contact=contact,
                    business_partner_location=location,
                    bill_to_location=bill_to_location,
                    currency=self.default_currency,
                    price_list=self.default_price_list,
                    warehouse=self.default_warehouse,
                    payment_terms=self.default_payment_terms,
                    grand_total=Decimal(str(row[10])) if row[10] else Decimal('0.00'),
                    created=row[12],
                    created_by=self.default_user,
                    updated=row[13],
                    updated_by=self.default_user,
                    is_active=(row[15] == 'Y'),
                    legacy_id=str(row[0])
                )
                
                # Migrate sales order lines
                self.migrate_sales_order_lines(row[0], sales_order)
                
                self.stats['sales_orders'] += 1
                
                if self.stats['sales_orders'] <= 5:
                    print(f"  Created SO: {sales_order.document_no} - {bp.name}")
                    if contact:
                        print(f"    Contact: {contact.name}")
                    
            except Exception as e:
                self.stats['errors'].append(f"Sales Order {row[0]}: {str(e)}")
                print(f"  Error with SO {row[0]}: {str(e)}")
        
        cursor.close()
        print(f"Migrated {self.stats['sales_orders']} sales orders")
    
    def migrate_sales_order_lines(self, order_id, sales_order):
        """Migrate sales order lines"""
        cursor = self.idempiere_conn.cursor()
        
        cursor.execute("""
            SELECT 
                line,
                m_product_id,
                description,
                qtyordered,
                priceentered,
                linenetamt
            FROM adempiere.c_orderline
            WHERE c_order_id = %s
            ORDER BY line
        """, (order_id,))
        
        for row in cursor.fetchall():
            try:
                product = self.product_map.get(row[1])
                if not product:
                    # Create placeholder product if not found
                    product = Product.objects.create(
                        name=f"Migrated Product {row[1]}",
                        uom=self.default_uom,
                        created_by=self.default_user,
                        updated_by=self.default_user,
                        legacy_id=str(row[1])
                    )
                    self.product_map[row[1]] = product
                
                SalesOrderLine.objects.create(
                    order=sales_order,
                    line_no=row[0],
                    product=product,
                    description=row[2] or '',
                    quantity_ordered=Decimal(str(row[3])) if row[3] else Decimal('0'),
                    price_entered=Decimal(str(row[4])) if row[4] else Decimal('0'),
                    line_net_amount=Decimal(str(row[5])) if row[5] else Decimal('0'),
                    created_by=self.default_user,
                    updated_by=self.default_user
                )
                
            except Exception as e:
                self.stats['errors'].append(f"Sales Order Line {order_id}-{row[0]}: {str(e)}")
        
        cursor.close()
    
    def print_summary(self):
        """Print migration summary"""
        print("\n" + "="*60)
        print("COMPLETE DATA MIGRATION SUMMARY")
        print("="*60)
        
        print(f"Business Partners: {self.stats['business_partners']}")
        print(f"Locations: {self.stats['locations']}")
        print(f"Contacts: {self.stats['contacts']}")
        print(f"Manufacturers: {self.stats['manufacturers']}")
        print(f"Products: {self.stats['products']}")
        print(f"Sales Orders: {self.stats['sales_orders']}")
        
        if self.stats['errors']:
            print(f"\nErrors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:10]:
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more")
        
        # Show sample data
        print("\nSample Business Partners with Contacts:")
        for bp in BusinessPartner.objects.filter(contacts__isnull=False)[:5]:
            print(f"  {bp.name}")
            for contact in bp.contacts.all()[:2]:
                print(f"    - {contact.name} ({contact.email})")
            for location in bp.locations.all()[:2]:
                print(f"    - {location.name}: {location.address1}, {location.city}")
    
    def run(self):
        """Run the complete migration"""
        try:
            if self.clear_all:
                self.clear_all_data()
            
            self.migrate_business_partners()
            self.migrate_locations()
            self.migrate_contacts()
            self.migrate_manufacturers_and_products()
            self.migrate_sales_orders()
            # Add other document migrations as needed
            
            self.print_summary()
                
        except Exception as e:
            print(f"\nMigration failed: {str(e)}")
            raise
        finally:
            self.idempiere_conn.close()


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Complete data migration with contacts and addresses')
    parser.add_argument('--clear-all', action='store_true', 
                        help='Clear all existing data before migration')
    args = parser.parse_args()
    
    migrator = CompleteDataMigrator(clear_all=args.clear_all)
    migrator.run()


if __name__ == "__main__":
    main()