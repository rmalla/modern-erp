#!/usr/bin/env python3
"""
Real Product Migration Script from iDempiere

This script migrates actual product data from the iDempiere database,
including real manufacturers, product names, part numbers, and descriptions.

Usage:
    python migrate_real_products.py [--clear-existing]
"""

import os
import sys
import django
import psycopg2
from decimal import Decimal
from datetime import datetime
import argparse

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from django.db import transaction, connection
from inventory.models import Product, Manufacturer, ProductCategory, UnitOfMeasure, Warehouse, StorageDetail
from sales.models import SalesOrderLine
from purchasing.models import PurchaseOrderLine
from core.models import User, Organization, BusinessPartner


class RealProductMigrator:
    """Migrates real product data from iDempiere database"""
    
    def __init__(self, clear_existing=False):
        self.clear_existing = clear_existing
        
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
        self.default_uom = UnitOfMeasure.objects.first()
        
        # Track mappings
        self.manufacturer_map = {}  # iDempiere ID -> Django Manufacturer
        self.product_map = {}       # iDempiere ID -> Django Product
        self.category_map = {}      # iDempiere ID -> Django ProductCategory
        
        self.stats = {
            'manufacturers': 0,
            'products': 0,
            'categories': 0,
            'updates': 0,
            'errors': []
        }
    
    def clear_existing_data(self):
        """Clear all existing product-related data"""
        if self.clear_existing:
            print("Preparing for real data migration...")
            
            # First, remove manufacturer references from products to allow deletion
            Product.objects.all().update(manufacturer=None)
            
            # Now we can safely delete manufacturers and categories
            Manufacturer.objects.all().delete()
            ProductCategory.objects.all().delete()
            
            print("  - Cleared manufacturers and categories")
            print("  - Products will be updated with real data")
    
    def migrate_manufacturers(self):
        """Migrate manufacturers from c_bpartner table"""
        print("\nMigrating manufacturers from iDempiere...")
        
        cursor = self.idempiere_conn.cursor()
        
        # Get manufacturers from custom_manufacturer references in products
        cursor.execute("""
            SELECT DISTINCT 
                bp.c_bpartner_id,
                bp.value as code,
                bp.name,
                bp.description,
                bp.isactive
            FROM adempiere.m_product p
            JOIN adempiere.c_bpartner bp ON p.custom_manufacturer = bp.c_bpartner_id
            WHERE p.isactive = 'Y'
            ORDER BY bp.name
        """)
        
        manufacturers = cursor.fetchall()
        
        for row in manufacturers:
            try:
                # Create manufacturer
                manufacturer, created = Manufacturer.objects.update_or_create(
                    legacy_id=str(row[0]),
                    defaults={
                        'code': row[1][:50] if row[1] else f'MFG{row[0]}',
                        'name': row[2] or f'Manufacturer {row[0]}',
                        'brand_name': row[2] or f'Manufacturer {row[0]}',
                        'description': row[3] or '',
                        'is_active': (row[4] == 'Y'),
                        'created_by': self.default_user,
                        'updated_by': self.default_user
                    }
                )
                
                self.manufacturer_map[row[0]] = manufacturer
                self.stats['manufacturers'] += 1
                
                if created:
                    print(f"  Created manufacturer: {manufacturer.name}")
                else:
                    print(f"  Updated manufacturer: {manufacturer.name}")
                    
            except Exception as e:
                self.stats['errors'].append(f"Manufacturer {row[0]}: {str(e)}")
                print(f"  Error with manufacturer {row[0]}: {str(e)}")
        
        cursor.close()
        print(f"Migrated {self.stats['manufacturers']} manufacturers")
    
    def migrate_product_categories(self):
        """Migrate product categories from m_product_category"""
        print("\nMigrating product categories...")
        
        cursor = self.idempiere_conn.cursor()
        
        cursor.execute("""
            SELECT 
                m_product_category_id,
                value,
                name,
                description,
                isactive
            FROM adempiere.m_product_category
            WHERE isactive = 'Y'
            ORDER BY name
        """)
        
        categories = cursor.fetchall()
        
        for row in categories:
            try:
                category, created = ProductCategory.objects.update_or_create(
                    legacy_id=str(row[0]),
                    defaults={
                        'code': row[1][:50] if row[1] else f'CAT{row[0]}',
                        'name': row[2] or f'Category {row[0]}',
                        'description': row[3] or '',
                        'is_active': (row[4] == 'Y'),
                        'created_by': self.default_user,
                        'updated_by': self.default_user
                    }
                )
                
                self.category_map[row[0]] = category
                self.stats['categories'] += 1
                
                if created:
                    print(f"  Created category: {category.name}")
                    
            except Exception as e:
                self.stats['errors'].append(f"Category {row[0]}: {str(e)}")
                print(f"  Error with category {row[0]}: {str(e)}")
        
        cursor.close()
        print(f"Migrated {self.stats['categories']} categories")
    
    def migrate_products(self):
        """Migrate real products from m_product table"""
        print("\nMigrating products from iDempiere...")
        
        cursor = self.idempiere_conn.cursor()
        
        # Get all active products with manufacturer info
        cursor.execute("""
            SELECT 
                p.m_product_id,
                p.value,
                p.name,
                p.description,
                p.custom_longdescription,
                p.sku,
                p.upc,
                p.producttype,
                p.custom_manufacturer,
                p.m_product_category_id,
                p.volume,
                p.weight,
                p.isactive,
                p.isstocked,
                p.ispurchased,
                p.issold,
                p.isdropship,
                p.custom_pimcore_id,
                p.guaranteedays,
                p.guaranteedaysmin
            FROM adempiere.m_product p
            WHERE p.isactive = 'Y'
            ORDER BY p.value
        """)
        
        products = cursor.fetchall()
        
        for row in products:
            try:
                # Get manufacturer
                manufacturer = self.manufacturer_map.get(row[8]) if row[8] else None
                
                # Get category
                category = self.category_map.get(row[9]) if row[9] else None
                
                # Determine product type
                product_type_map = {
                    'I': 'item',      # Item
                    'S': 'service',   # Service
                    'R': 'resource',  # Resource
                    'E': 'expense',   # Expense
                    'O': 'online'     # Online
                }
                product_type = product_type_map.get(row[7], 'item')
                
                # Create or update product
                product, created = Product.objects.update_or_create(
                    legacy_id=str(row[0]),
                    defaults={
                        'name': row[2] or f'Product {row[0]}',
                        'short_description': (row[3] or '')[:500],
                        'description': row[4] or row[3] or '',
                        'manufacturer': manufacturer,
                        'manufacturer_part_number': row[5] or row[1] or '',  # Use SKU (row[5]), fallback to VALUE (row[1])
                        'product_type': product_type,
                        'uom': self.default_uom,
                        'weight': Decimal(str(row[11])) if row[11] else Decimal('0'),
                        'volume': Decimal(str(row[10])) if row[10] else Decimal('0'),
                        'is_active': (row[12] == 'Y'),
                        'created_by': self.default_user,
                        'updated_by': self.default_user,
                        # Set default pricing to 0 for now
                        'list_price': Decimal('0.00'),
                        'standard_cost': Decimal('0.00')
                    }
                )
                
                self.product_map[row[0]] = product
                self.stats['products'] += 1
                
                if created:
                    print(f"  Created product: {row[5] or row[1]} - {row[2]}")
                else:
                    print(f"  Updated product: {row[5] or row[1]} - {row[2]}")
                    
            except Exception as e:
                self.stats['errors'].append(f"Product {row[0]}: {str(e)}")
                print(f"  Error with product {row[0]} ({row[1]}): {str(e)}")
        
        cursor.close()
        print(f"Migrated {self.stats['products']} products")
    
    def update_pricing_from_orders(self):
        """Update product pricing based on existing order history"""
        print("\nUpdating product pricing from order history...")
        
        updated_count = 0
        
        # Analyze sales order lines for pricing
        for product in Product.objects.all():
            pricing_updated = False
            
            # Get sales prices
            sales_lines = SalesOrderLine.objects.filter(
                product__legacy_id=product.legacy_id
            ).values_list('price_entered', flat=True)
            
            if sales_lines:
                # Calculate average sales price
                # Handle Money objects properly
                prices = []
                for price in sales_lines:
                    if hasattr(price, 'amount'):
                        prices.append(float(price.amount))
                    else:
                        prices.append(float(price))
                
                if prices:
                    avg_sales_price = sum(prices) / len(prices)
                    product.list_price = Decimal(str(avg_sales_price))
                    pricing_updated = True
            
            # Get purchase prices
            purchase_lines = PurchaseOrderLine.objects.filter(
                product__legacy_id=product.legacy_id
            ).values_list('price_entered', flat=True)
            
            if purchase_lines:
                # Calculate average purchase price
                costs = []
                for cost in purchase_lines:
                    if hasattr(cost, 'amount'):
                        costs.append(float(cost.amount))
                    else:
                        costs.append(float(cost))
                
                if costs:
                    avg_purchase_cost = sum(costs) / len(costs)
                    product.standard_cost = Decimal(str(avg_purchase_cost))
                    pricing_updated = True
            
            if pricing_updated:
                product.save()
                updated_count += 1
                if updated_count <= 10:  # Show first 10 updates
                    print(f"  Updated pricing for {product.manufacturer_part_number}: "
                          f"Price=${product.list_price}, Cost=${product.standard_cost}")
        
        print(f"  Total products with updated pricing: {updated_count}")
    
    def update_order_references(self):
        """Update all order line references to use the new products"""
        print("\nUpdating order line references...")
        
        # Update sales order lines
        updated_count = 0
        for line in SalesOrderLine.objects.all():
            if line.product and line.product.legacy_id:
                new_product = self.product_map.get(int(line.product.legacy_id))
                if new_product and new_product != line.product:
                    line.product = new_product
                    line.save()
                    updated_count += 1
        
        print(f"  Updated {updated_count} sales order lines")
        
        # Update purchase order lines
        updated_count = 0
        for line in PurchaseOrderLine.objects.all():
            if line.product and line.product.legacy_id:
                new_product = self.product_map.get(int(line.product.legacy_id))
                if new_product and new_product != line.product:
                    line.product = new_product
                    line.save()
                    updated_count += 1
        
        print(f"  Updated {updated_count} purchase order lines")
        
        self.stats['updates'] = updated_count
    
    def print_summary(self):
        """Print migration summary"""
        print("\n" + "="*60)
        print("REAL PRODUCT MIGRATION SUMMARY")
        print("="*60)
        
        print(f"Manufacturers migrated: {self.stats['manufacturers']}")
        print(f"Categories migrated: {self.stats['categories']}")
        print(f"Products migrated: {self.stats['products']}")
        print(f"Order lines updated: {self.stats['updates']}")
        
        if self.stats['errors']:
            print(f"\nErrors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:10]:
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more")
        
        # Show sample products
        print("\nSample migrated products:")
        for product in Product.objects.filter(manufacturer__isnull=False)[:10]:
            print(f"  {product.manufacturer_part_number}: {product.name}")
            if product.manufacturer:
                print(f"    Manufacturer: {product.manufacturer.name}")
            print(f"    Price: ${product.list_price} | Cost: ${product.standard_cost}")
    
    def run(self):
        """Run the complete migration process"""
        try:
            with transaction.atomic():
                if self.clear_existing:
                    self.clear_existing_data()
                
                self.migrate_manufacturers()
                self.migrate_product_categories()
                self.migrate_products()
                self.update_pricing_from_orders()
                self.update_order_references()
                
                self.print_summary()
                
        except Exception as e:
            print(f"\nMigration failed: {str(e)}")
            raise
        finally:
            self.idempiere_conn.close()


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Migrate real products from iDempiere')
    parser.add_argument('--clear-existing', action='store_true', 
                        help='Clear all existing product data before migration')
    args = parser.parse_args()
    
    migrator = RealProductMigrator(clear_existing=args.clear_existing)
    migrator.run()


if __name__ == "__main__":
    main()