#!/usr/bin/env python3
"""
iDempiere to Modern ERP Data Migration Script

This script migrates data from the old iDempiere system to the new Modern ERP Django system.
It handles the following entities:
- Business Partners (customers and vendors)
- Sales Orders
- Purchase Orders  
- Sales Invoices
- Shipments (M_InOut)

Usage:
    python migrate_idempiere_data.py

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
from datetime import datetime
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from core.models import BusinessPartner, Organization, Currency, User, UnitOfMeasure
from sales.models import SalesOrder, SalesOrderLine, Invoice, InvoiceLine, Shipment, ShipmentLine
from purchasing.models import PurchaseOrder, PurchaseOrderLine, VendorBill, VendorBillLine, Receipt, ReceiptLine
from inventory.models import Product, ProductCategory, Warehouse, PriceList


class iDempiereDataMigrator:
    """Migrates data from iDempiere to Modern ERP"""
    
    def __init__(self):
        # Database connections
        self.old_db = psycopg2.connect(
            host='localhost',
            database='temp_idempiere',
            user='django_user',
            password='django_pass'
        )
        
        self.new_db = psycopg2.connect(
            host='localhost',
            database='modern_erp',
            user='django_user',
            password='django_pass'
        )
        
        # Get default organization and user for migration
        self.default_org = Organization.objects.first()
        self.default_user = User.objects.first()
        self.default_currency = Currency.objects.filter(iso_code='USD').first()
        
        if not all([self.default_org, self.default_user, self.default_currency]):
            raise Exception("Please ensure you have at least one Organization, User, and USD Currency in the system")
        
        # Migration statistics
        self.stats = {
            'business_partners': 0,
            'sales_orders': 0,
            'purchase_orders': 0,
            'invoices': 0,
            'shipments': 0,
            'errors': []
        }
    
    def migrate_business_partners(self):
        """Migrate business partners from c_bpartner"""
        print("Migrating Business Partners...")
        
        old_cursor = self.old_db.cursor()
        
        # Get business partners from old system
        old_cursor.execute("""
            SELECT 
                c_bpartner_id,
                value as search_key,
                name,
                name2,
                description,
                iscustomer,
                isvendor,
                isactive,
                created,
                createdby,
                updated,
                updatedby
            FROM adempiere.c_bpartner 
            WHERE issummary = 'N'
            ORDER BY c_bpartner_id
        """)
        
        for row in old_cursor.fetchall():
            try:
                # Determine partner type based on flags
                is_customer = (row[5] == 'Y')
                is_vendor = (row[6] == 'Y')
                
                if is_customer and is_vendor:
                    partner_type = 'customer'  # Default to customer if both
                elif is_vendor:
                    partner_type = 'vendor'
                elif is_customer:
                    partner_type = 'customer'
                else:
                    partner_type = 'other'  # Neither customer nor vendor
                
                bp = BusinessPartner.objects.create(
                    # Map fields from old to new
                    code=row[1] or f"BP{row[0]}",
                    search_key=row[1] or f"BP{row[0]}",
                    name=row[2],
                    name2=row[3] or '',
                    partner_type=partner_type,
                    is_active=(row[7] == 'Y'),
                    created=row[8],
                    created_by=self.default_user,
                    updated=row[9],
                    updated_by=self.default_user,
                    # Set migration reference
                    legacy_id=str(row[0])
                )
                self.stats['business_partners'] += 1
                
            except Exception as e:
                error_msg = f"Error migrating Business Partner ID {row[0]}: {str(e)}"
                print(error_msg)
                self.stats['errors'].append(error_msg)
        
        old_cursor.close()
        print(f"Migrated {self.stats['business_partners']} Business Partners")
    
    def migrate_sales_orders(self):
        """Migrate sales orders from c_order where issotrx='Y'"""
        print("Migrating Sales Orders...")
        
        old_cursor = self.old_db.cursor()
        
        # Get sales orders from old system
        old_cursor.execute("""
            SELECT 
                o.c_order_id,
                o.documentno,
                o.description,
                o.docstatus,
                o.dateordered,
                o.datepromised,
                o.c_bpartner_id,
                o.grandtotal,
                o.created,
                o.createdby,
                o.updated,
                o.updatedby,
                o.isactive
            FROM adempiere.c_order o
            WHERE o.issotrx = 'Y'
            ORDER BY o.c_order_id
        """)
        
        for row in old_cursor.fetchall():
            try:
                # Find corresponding business partner
                bp = BusinessPartner.objects.filter(legacy_id=str(row[6])).first()
                if not bp:
                    print(f"Warning: Business Partner ID {row[6]} not found for Sales Order {row[0]}")
                    continue
                
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
                
                so = SalesOrder.objects.create(
                    organization=self.default_org,
                    document_no=row[1],
                    description=row[2] or '',
                    doc_status=doc_status_map.get(row[3], 'drafted'),
                    date_ordered=row[4],
                    date_promised=row[5],
                    business_partner=bp,
                    currency=self.default_currency,
                    price_list=PriceList.objects.filter(is_sales_price_list=True).first(),
                    warehouse=Warehouse.objects.first(),
                    grand_total=Decimal(str(row[7])) if row[7] else Decimal('0.00'),
                    created=row[8],
                    created_by=self.default_user,
                    updated=row[9],
                    updated_by=self.default_user,
                    is_active=(row[10] == 'Y'),
                    legacy_id=str(row[0])
                )
                
                # Migrate order lines
                self.migrate_sales_order_lines(row[0], so)
                
                self.stats['sales_orders'] += 1
                
            except Exception as e:
                error_msg = f"Error migrating Sales Order ID {row[0]}: {str(e)}"
                print(error_msg)
                self.stats['errors'].append(error_msg)
        
        old_cursor.close()
        print(f"Migrated {self.stats['sales_orders']} Sales Orders")
    
    def migrate_sales_order_lines(self, old_order_id, new_order):
        """Migrate sales order lines"""
        old_cursor = self.old_db.cursor()
        
        old_cursor.execute("""
            SELECT 
                c_orderline_id,
                line,
                m_product_id,
                qtyordered,
                priceentered,
                linenetamt,
                description
            FROM adempiere.c_orderline 
            WHERE c_order_id = %s
            ORDER BY line
        """, (old_order_id,))
        
        for row in old_cursor.fetchall():
            try:
                # Find or create product
                product = Product.objects.filter(legacy_id=str(row[2])).first()
                if not product:
                    # Create placeholder product
                    product = Product.objects.create(
                        code=f"PROD{row[2]}",
                        name=f"Migrated Product {row[2]}",
                        product_category=ProductCategory.objects.first(),
                        uom=UnitOfMeasure.objects.first(),
                        created_by=self.default_user,
                        updated_by=self.default_user,
                        legacy_id=str(row[2])
                    )
                
                SalesOrderLine.objects.create(
                    order=new_order,
                    line_no=row[1],
                    product=product,
                    quantity_ordered=Decimal(str(row[3])),
                    price_entered=Decimal(str(row[4])),
                    line_net_amount=Decimal(str(row[5])),
                    price_actual=Decimal(str(row[4])),
                    description=row[6] or '',
                    created_by=self.default_user,
                    updated_by=self.default_user,
                    legacy_id=str(row[0])
                )
                
            except Exception as e:
                print(f"Error migrating Sales Order Line ID {row[0]}: {str(e)}")
        
        old_cursor.close()
    
    def migrate_purchase_orders(self):
        """Migrate purchase orders from c_order where issotrx='N'"""
        print("Migrating Purchase Orders...")
        
        old_cursor = self.old_db.cursor()
        
        # Similar to sales orders but for purchase orders
        old_cursor.execute("""
            SELECT 
                o.c_order_id,
                o.documentno,
                o.description,
                o.docstatus,
                o.dateordered,
                o.datepromised,
                o.c_bpartner_id,
                o.grandtotal,
                o.created,
                o.createdby,
                o.updated,
                o.updatedby,
                o.isactive
            FROM adempiere.c_order o
            WHERE o.issotrx = 'N'
            ORDER BY o.c_order_id
        """)
        
        for row in old_cursor.fetchall():
            try:
                # Find corresponding business partner
                bp = BusinessPartner.objects.filter(legacy_id=str(row[6])).first()
                if not bp:
                    print(f"Warning: Business Partner ID {row[6]} not found for Purchase Order {row[0]}")
                    continue
                
                # Map document status
                doc_status_map = {
                    'DR': 'drafted',
                    'IP': 'in_progress', 
                    'CO': 'complete',
                    'CL': 'closed',
                    'RE': 'reversed',
                    'VO': 'voided'
                }
                
                po = PurchaseOrder.objects.create(
                    organization=self.default_org,
                    document_no=row[1],
                    description=row[2] or '',
                    doc_status=doc_status_map.get(row[3], 'drafted'),
                    date_ordered=row[4],
                    date_promised=row[5],
                    business_partner=bp,
                    currency=self.default_currency,
                    price_list=PriceList.objects.filter(is_purchase_price_list=True).first(),
                    warehouse=Warehouse.objects.first(),
                    grand_total=Decimal(str(row[7])) if row[7] else Decimal('0.00'),
                    created=row[8],
                    created_by=self.default_user,
                    updated=row[9],
                    updated_by=self.default_user,
                    is_active=(row[10] == 'Y'),
                    legacy_id=str(row[0])
                )
                
                # Migrate order lines
                self.migrate_purchase_order_lines(row[0], po)
                
                self.stats['purchase_orders'] += 1
                
            except Exception as e:
                error_msg = f"Error migrating Purchase Order ID {row[0]}: {str(e)}"
                print(error_msg)
                self.stats['errors'].append(error_msg)
        
        old_cursor.close()
        print(f"Migrated {self.stats['purchase_orders']} Purchase Orders")
    
    def migrate_purchase_order_lines(self, old_order_id, new_order):
        """Migrate purchase order lines"""
        old_cursor = self.old_db.cursor()
        
        old_cursor.execute("""
            SELECT 
                c_orderline_id,
                line,
                m_product_id,
                qtyordered,
                priceentered,
                linenetamt,
                description
            FROM adempiere.c_orderline 
            WHERE c_order_id = %s
            ORDER BY line
        """, (old_order_id,))
        
        for row in old_cursor.fetchall():
            try:
                # Find or create product
                product = Product.objects.filter(legacy_id=str(row[2])).first()
                if not product:
                    # Create placeholder product
                    product = Product.objects.create(
                        code=f"PROD{row[2]}",
                        name=f"Migrated Product {row[2]}",
                        product_category=ProductCategory.objects.first(),
                        uom=UnitOfMeasure.objects.first(),
                        created_by=self.default_user,
                        updated_by=self.default_user,
                        legacy_id=str(row[2])
                    )
                
                PurchaseOrderLine.objects.create(
                    order=new_order,
                    line_no=row[1],
                    product=product,
                    quantity_ordered=Decimal(str(row[3])),
                    price_entered=Decimal(str(row[4])),
                    line_net_amount=Decimal(str(row[5])),
                    price_actual=Decimal(str(row[4])),
                    description=row[6] or '',
                    created_by=self.default_user,
                    updated_by=self.default_user,
                    legacy_id=str(row[0])
                )
                
            except Exception as e:
                print(f"Error migrating Purchase Order Line ID {row[0]}: {str(e)}")
        
        old_cursor.close()
    
    def migrate_invoices(self):
        """Migrate invoices from c_invoice"""
        print("Migrating Invoices...")
        
        old_cursor = self.old_db.cursor()
        
        old_cursor.execute("""
            SELECT 
                c_invoice_id,
                documentno,
                description,
                docstatus,
                dateinvoiced,
                c_bpartner_id,
                grandtotal,
                issotrx,
                created,
                createdby,
                updated,
                updatedby,
                isactive
            FROM adempiere.c_invoice
            ORDER BY c_invoice_id
        """)
        
        for row in old_cursor.fetchall():
            try:
                # Find corresponding business partner
                bp = BusinessPartner.objects.filter(legacy_id=str(row[5])).first()
                if not bp:
                    print(f"Warning: Business Partner ID {row[5]} not found for Invoice {row[0]}")
                    continue
                
                # Map document status
                doc_status_map = {
                    'DR': 'drafted',
                    'IP': 'in_progress', 
                    'CO': 'complete',
                    'CL': 'closed',
                    'RE': 'reversed',
                    'VO': 'voided'
                }
                
                if row[7] == 'Y':  # Sales invoice
                    invoice = Invoice.objects.create(
                        organization=self.default_org,
                        document_no=row[1],
                        description=row[2] or '',
                        doc_status=doc_status_map.get(row[3], 'drafted'),
                        date_invoiced=row[4],
                        date_accounting=row[4],  # Use invoice date as accounting date
                        due_date=row[4],  # Set due date to invoice date for now
                        business_partner=bp,
                        currency=self.default_currency,
                        price_list=PriceList.objects.filter(is_sales_price_list=True).first(),
                        grand_total=Decimal(str(row[6])) if row[6] else Decimal('0.00'),
                        created=row[8],
                        created_by=self.default_user,
                        updated=row[9],
                        updated_by=self.default_user,
                        is_active=(row[10] == 'Y'),
                        legacy_id=str(row[0])
                    )
                    
                    # Migrate invoice lines
                    self.migrate_invoice_lines(row[0], invoice)
                    
                else:  # Purchase invoice (Vendor Bill)
                    bill = VendorBill.objects.create(
                        organization=self.default_org,
                        document_no=row[1],
                        description=row[2] or '',
                        doc_status=doc_status_map.get(row[3], 'drafted'),
                        date_invoiced=row[4],
                        date_accounting=row[4],  # Use invoice date as accounting date
                        due_date=row[4],  # Set due date to invoice date for now
                        business_partner=bp,
                        currency=self.default_currency,
                        price_list=PriceList.objects.filter(is_purchase_price_list=True).first(),
                        grand_total=Decimal(str(row[6])) if row[6] else Decimal('0.00'),
                        created=row[8],
                        created_by=self.default_user,
                        updated=row[9],
                        updated_by=self.default_user,
                        is_active=(row[10] == 'Y'),
                        legacy_id=str(row[0])
                    )
                    
                    # Migrate bill lines
                    self.migrate_vendor_bill_lines(row[0], bill)
                
                self.stats['invoices'] += 1
                
            except Exception as e:
                error_msg = f"Error migrating Invoice ID {row[0]}: {str(e)}"
                print(error_msg)
                self.stats['errors'].append(error_msg)
        
        old_cursor.close()
        print(f"Migrated {self.stats['invoices']} Invoices")
    
    def migrate_invoice_lines(self, old_invoice_id, new_invoice):
        """Migrate invoice lines"""
        old_cursor = self.old_db.cursor()
        
        old_cursor.execute("""
            SELECT 
                c_invoiceline_id,
                line,
                m_product_id,
                qtyinvoiced,
                priceentered,
                linenetamt,
                description
            FROM adempiere.c_invoiceline 
            WHERE c_invoice_id = %s
            ORDER BY line
        """, (old_invoice_id,))
        
        for row in old_cursor.fetchall():
            try:
                # Find or create product
                product = Product.objects.filter(legacy_id=str(row[2])).first()
                if not product:
                    # Create placeholder product
                    product = Product.objects.create(
                        code=f"PROD{row[2]}",
                        name=f"Migrated Product {row[2]}",
                        product_category=ProductCategory.objects.first(),
                        uom=UnitOfMeasure.objects.first(),
                        created_by=self.default_user,
                        updated_by=self.default_user,
                        legacy_id=str(row[2])
                    )
                
                InvoiceLine.objects.create(
                    invoice=new_invoice,
                    line_no=row[1],
                    product=product,
                    quantity_invoiced=Decimal(str(row[3])),
                    price_entered=Decimal(str(row[4])),
                    line_net_amount=Decimal(str(row[5])),
                    price_actual=Decimal(str(row[4])),
                    description=row[6] or '',
                    created_by=self.default_user,
                    updated_by=self.default_user,
                    legacy_id=str(row[0])
                )
                
            except Exception as e:
                print(f"Error migrating Invoice Line ID {row[0]}: {str(e)}")
        
        old_cursor.close()
    
    def migrate_vendor_bill_lines(self, old_invoice_id, new_bill):
        """Migrate vendor bill lines"""
        old_cursor = self.old_db.cursor()
        
        old_cursor.execute("""
            SELECT 
                c_invoiceline_id,
                line,
                m_product_id,
                qtyinvoiced,
                priceentered,
                linenetamt,
                description
            FROM adempiere.c_invoiceline 
            WHERE c_invoice_id = %s
            ORDER BY line
        """, (old_invoice_id,))
        
        for row in old_cursor.fetchall():
            try:
                # Find or create product
                product = Product.objects.filter(legacy_id=str(row[2])).first()
                if not product:
                    # Create placeholder product
                    product = Product.objects.create(
                        code=f"PROD{row[2]}",
                        name=f"Migrated Product {row[2]}",
                        product_category=ProductCategory.objects.first(),
                        uom=UnitOfMeasure.objects.first(),
                        created_by=self.default_user,
                        updated_by=self.default_user,
                        legacy_id=str(row[2])
                    )
                
                VendorBillLine.objects.create(
                    invoice=new_bill,
                    line_no=row[1],
                    product=product,
                    quantity_invoiced=Decimal(str(row[3])),
                    price_entered=Decimal(str(row[4])),
                    line_net_amount=Decimal(str(row[5])),
                    price_actual=Decimal(str(row[4])),
                    description=row[6] or '',
                    created_by=self.default_user,
                    updated_by=self.default_user,
                    legacy_id=str(row[0])
                )
                
            except Exception as e:
                print(f"Error migrating Vendor Bill Line ID {row[0]}: {str(e)}")
        
        old_cursor.close()
    
    def migrate_shipments(self):
        """Migrate shipments from m_inout"""
        print("Migrating Shipments...")
        
        old_cursor = self.old_db.cursor()
        
        old_cursor.execute("""
            SELECT 
                m_inout_id,
                documentno,
                description,
                docstatus,
                movementdate,
                c_bpartner_id,
                issotrx,
                created,
                createdby,
                updated,
                updatedby,
                isactive
            FROM adempiere.m_inout
            ORDER BY m_inout_id
        """)
        
        for row in old_cursor.fetchall():
            try:
                # Find corresponding business partner
                bp = BusinessPartner.objects.filter(legacy_id=str(row[5])).first()
                if not bp:
                    print(f"Warning: Business Partner ID {row[5]} not found for Shipment {row[0]}")
                    continue
                
                # Map document status
                doc_status_map = {
                    'DR': 'drafted',
                    'IP': 'in_progress', 
                    'CO': 'complete',
                    'CL': 'closed',
                    'RE': 'reversed',
                    'VO': 'voided'
                }
                
                if row[6] == 'Y':  # Customer shipment
                    shipment = Shipment.objects.create(
                        organization=self.default_org,
                        document_no=row[1],
                        description=row[2] or '',
                        doc_status=doc_status_map.get(row[3], 'drafted'),
                        movement_date=row[4],
                        business_partner=bp,
                        warehouse=Warehouse.objects.first(),
                        created=row[7],
                        created_by=self.default_user,
                        updated=row[8],
                        updated_by=self.default_user,
                        is_active=(row[9] == 'Y'),
                        legacy_id=str(row[0])
                    )
                    
                    # Migrate shipment lines
                    self.migrate_shipment_lines(row[0], shipment)
                    
                else:  # Vendor receipt
                    receipt = Receipt.objects.create(
                        organization=self.default_org,
                        document_no=row[1],
                        description=row[2] or '',
                        doc_status=doc_status_map.get(row[3], 'drafted'),
                        movement_date=row[4],
                        business_partner=bp,
                        warehouse=Warehouse.objects.first(),
                        created=row[7],
                        created_by=self.default_user,
                        updated=row[8],
                        updated_by=self.default_user,
                        is_active=(row[9] == 'Y'),
                        legacy_id=str(row[0])
                    )
                    
                    # Migrate receipt lines
                    self.migrate_receipt_lines(row[0], receipt)
                
                self.stats['shipments'] += 1
                
            except Exception as e:
                error_msg = f"Error migrating Shipment ID {row[0]}: {str(e)}"
                print(error_msg)
                self.stats['errors'].append(error_msg)
        
        old_cursor.close()
        print(f"Migrated {self.stats['shipments']} Shipments")
    
    def migrate_shipment_lines(self, old_inout_id, new_shipment):
        """Migrate shipment lines"""
        old_cursor = self.old_db.cursor()
        
        old_cursor.execute("""
            SELECT 
                m_inoutline_id,
                line,
                m_product_id,
                movementqty,
                description
            FROM adempiere.m_inoutline 
            WHERE m_inout_id = %s
            ORDER BY line
        """, (old_inout_id,))
        
        for row in old_cursor.fetchall():
            try:
                # Find or create product
                product = Product.objects.filter(legacy_id=str(row[2])).first()
                if not product:
                    # Create placeholder product
                    product = Product.objects.create(
                        code=f"PROD{row[2]}",
                        name=f"Migrated Product {row[2]}",
                        product_category=ProductCategory.objects.first(),
                        uom=UnitOfMeasure.objects.first(),
                        created_by=self.default_user,
                        updated_by=self.default_user,
                        legacy_id=str(row[2])
                    )
                
                ShipmentLine.objects.create(
                    shipment=new_shipment,
                    line_no=row[1],
                    product=product,
                    movement_quantity=Decimal(str(row[3])),
                    quantity_entered=Decimal(str(row[3])),
                    description=row[4] or '',
                    created_by=self.default_user,
                    updated_by=self.default_user,
                    legacy_id=str(row[0])
                )
                
            except Exception as e:
                print(f"Error migrating Shipment Line ID {row[0]}: {str(e)}")
        
        old_cursor.close()
    
    def migrate_receipt_lines(self, old_inout_id, new_receipt):
        """Migrate receipt lines"""
        old_cursor = self.old_db.cursor()
        
        old_cursor.execute("""
            SELECT 
                m_inoutline_id,
                line,
                m_product_id,
                movementqty,
                description
            FROM adempiere.m_inoutline 
            WHERE m_inout_id = %s
            ORDER BY line
        """, (old_inout_id,))
        
        for row in old_cursor.fetchall():
            try:
                # Find or create product
                product = Product.objects.filter(legacy_id=str(row[2])).first()
                if not product:
                    # Create placeholder product
                    product = Product.objects.create(
                        code=f"PROD{row[2]}",
                        name=f"Migrated Product {row[2]}",
                        product_category=ProductCategory.objects.first(),
                        uom=UnitOfMeasure.objects.first(),
                        created_by=self.default_user,
                        updated_by=self.default_user,
                        legacy_id=str(row[2])
                    )
                
                ReceiptLine.objects.create(
                    receipt=new_receipt,
                    line_no=row[1],
                    product=product,
                    movement_quantity=Decimal(str(row[3])),
                    quantity_entered=Decimal(str(row[3])),
                    description=row[4] or '',
                    created_by=self.default_user,
                    updated_by=self.default_user,
                    legacy_id=str(row[0])
                )
                
            except Exception as e:
                print(f"Error migrating Receipt Line ID {row[0]}: {str(e)}")
        
        old_cursor.close()
    
    def run_migration(self):
        """Run the complete migration process"""
        print("Starting iDempiere to Modern ERP Migration...")
        print("=" * 60)
        
        try:
            # Run migrations in dependency order
            self.migrate_business_partners()
            self.migrate_sales_orders()
            self.migrate_purchase_orders()
            self.migrate_invoices()
            self.migrate_shipments()
            
            # Print summary
            print("\n" + "=" * 60)
            print("MIGRATION SUMMARY")
            print("=" * 60)
            print(f"Business Partners: {self.stats['business_partners']}")
            print(f"Sales Orders: {self.stats['sales_orders']}")  
            print(f"Purchase Orders: {self.stats['purchase_orders']}")
            print(f"Invoices: {self.stats['invoices']}")
            print(f"Shipments: {self.stats['shipments']}")
            print(f"Errors: {len(self.stats['errors'])}")
            
            if self.stats['errors']:
                print("\nERRORS:")
                for error in self.stats['errors']:
                    print(f"  - {error}")
                    
        except Exception as e:
            print(f"Migration failed: {str(e)}")
            raise
        
        finally:
            # Close database connections
            self.old_db.close()
            self.new_db.close()
            
        print("\nMigration completed!")


if __name__ == "__main__":
    migrator = iDempiereDataMigrator()
    migrator.run_migration()