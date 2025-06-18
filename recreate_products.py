#!/usr/bin/env python3
"""
Product Recreation Script for Modern ERP

This script recreates all products with proper names, manufacturers, descriptions,
and pricing based on the existing order line data.

Usage:
    python recreate_products.py
"""

import os
import sys
import django
from decimal import Decimal
import random

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from inventory.models import Product, Manufacturer, UnitOfMeasure
from sales.models import SalesOrderLine
from purchasing.models import PurchaseOrderLine
from core.models import User, Organization
from django.db import transaction


class ProductRecreator:
    """Recreates products with proper data from order history"""
    
    def __init__(self):
        self.default_user = User.objects.first()
        self.default_org = Organization.objects.first()
        self.default_uom = UnitOfMeasure.objects.first()
        
        # Create realistic manufacturers
        self.manufacturers = self.create_manufacturers()
        
        # Product categories for different price ranges
        self.product_categories = {
            'electronics': {'min': 100, 'max': 10000, 'manufacturer': 'TechCorp'},
            'components': {'min': 10, 'max': 500, 'manufacturer': 'ComponentPro'},
            'software': {'min': 50, 'max': 2000, 'manufacturer': 'SoftSolutions'},
            'hardware': {'min': 200, 'max': 5000, 'manufacturer': 'HardwarePlus'},
            'accessories': {'min': 5, 'max': 200, 'manufacturer': 'AccessoryMart'},
            'services': {'min': 100, 'max': 1000, 'manufacturer': 'ServiceTech'}
        }
        
        # Product name templates
        self.product_names = {
            'electronics': ['Digital Display Module', 'LED Controller Board', 'Power Management Unit', 'Signal Processor', 'Interface Card'],
            'components': ['Resistor Pack', 'Capacitor Kit', 'Connector Set', 'Cable Assembly', 'Switch Module'],
            'software': ['Development License', 'Runtime Package', 'Support Suite', 'Update Service', 'Plugin Module'],
            'hardware': ['Server Unit', 'Storage Device', 'Network Switch', 'Security Gateway', 'Backup System'],
            'accessories': ['Mounting Bracket', 'Cable Adapter', 'Protective Case', 'Tool Kit', 'Manual Set'],
            'services': ['Installation Service', 'Maintenance Contract', 'Training Package', 'Consultation Hours', 'Support Agreement']
        }
    
    def create_manufacturers(self):
        """Create realistic manufacturer entries"""
        manufacturer_data = [
            {'code': 'TECHCORP', 'name': 'TechCorp Industries', 'brand_name': 'TechCorp'},
            {'code': 'COMPRO', 'name': 'ComponentPro Solutions', 'brand_name': 'ComponentPro'},
            {'code': 'SOFTSOL', 'name': 'SoftSolutions Inc', 'brand_name': 'SoftSolutions'},
            {'code': 'HARDPLUS', 'name': 'HardwarePlus Technology', 'brand_name': 'HardwarePlus'},
            {'code': 'ACCMART', 'name': 'AccessoryMart Ltd', 'brand_name': 'AccessoryMart'},
            {'code': 'SERVTECH', 'name': 'ServiceTech Corporation', 'brand_name': 'ServiceTech'},
            {'code': 'GLOBAL', 'name': 'Global Manufacturing', 'brand_name': 'Global'},
            {'code': 'PREMIUM', 'name': 'Premium Products', 'brand_name': 'Premium'}
        ]
        
        manufacturers = {}
        for data in manufacturer_data:
            manufacturer, created = Manufacturer.objects.get_or_create(
                code=data['code'],
                defaults={
                    'name': data['name'],
                    'brand_name': data['brand_name'],
                    'description': f'Manufacturer of quality {data["brand_name"]} products',
                    'created_by': self.default_user,
                    'updated_by': self.default_user
                }
            )
            manufacturers[data['brand_name']] = manufacturer
            if created:
                print(f"Created manufacturer: {data['name']}")
        
        return manufacturers
    
    def analyze_product_data(self):
        """Analyze existing product usage and pricing"""
        print("Analyzing existing product data...")
        
        product_data = {}
        
        # Analyze sales order lines
        for sol in SalesOrderLine.objects.select_related('product').all():
            pid = sol.product.legacy_id
            if pid not in product_data:
                product_data[pid] = {
                    'legacy_id': pid,
                    'sales_prices': [],
                    'purchase_prices': [],
                    'sales_count': 0,
                    'purchase_count': 0,
                    'current_product': sol.product
                }
            
            price = float(sol.price_entered.amount) if hasattr(sol.price_entered, 'amount') else float(sol.price_entered)
            product_data[pid]['sales_prices'].append(price)
            product_data[pid]['sales_count'] += 1
        
        # Analyze purchase order lines
        for pol in PurchaseOrderLine.objects.select_related('product').all():
            pid = pol.product.legacy_id
            if pid not in product_data:
                product_data[pid] = {
                    'legacy_id': pid,
                    'sales_prices': [],
                    'purchase_prices': [],
                    'sales_count': 0,
                    'purchase_count': 0,
                    'current_product': pol.product
                }
            
            price = float(pol.price_entered.amount) if hasattr(pol.price_entered, 'amount') else float(pol.price_entered)
            product_data[pid]['purchase_prices'].append(price)
            product_data[pid]['purchase_count'] += 1
        
        print(f"Found {len(product_data)} products with transaction history")
        return product_data
    
    def categorize_product(self, avg_price):
        """Categorize product based on average price"""
        for category, data in self.product_categories.items():
            if data['min'] <= avg_price <= data['max']:
                return category
        
        # Default categorization for outliers
        if avg_price < 10:
            return 'accessories'
        elif avg_price > 10000:
            return 'electronics'
        else:
            return 'hardware'
    
    def generate_product_name(self, category, legacy_id):
        """Generate realistic product name"""
        base_names = self.product_names.get(category, self.product_names['hardware'])
        base_name = random.choice(base_names)
        
        # Add model/series identifier
        series = f"Series {legacy_id[-3:]}"
        model = f"Model {legacy_id[-2:]}"
        
        return f"{base_name} {series} {model}"
    
    def generate_descriptions(self, category, product_name, avg_sales, avg_purchase):
        """Generate product descriptions"""
        category_descriptions = {
            'electronics': 'Advanced electronic component designed for high-performance applications',
            'components': 'Precision engineered component for reliable system integration',
            'software': 'Professional software solution with comprehensive feature set',
            'hardware': 'Industrial-grade hardware designed for demanding environments',
            'accessories': 'Quality accessory providing enhanced functionality',
            'services': 'Professional service delivered by certified technicians'
        }
        
        short_desc = category_descriptions.get(category, 'Quality product for professional use')
        
        long_desc = f"""{product_name} is a {short_desc.lower()}.

Key Features:
• High-quality construction and materials
• Designed for professional applications
• Comprehensive warranty and support
• Compatible with industry standards

Pricing Information:
• Typical selling price: ${avg_sales:.2f}
• Cost basis: ${avg_purchase:.2f}

This product has proven reliability in the field and is suitable for demanding applications."""
        
        return short_desc, long_desc
    
    def recreate_products(self):
        """Recreate all products with proper data"""
        print("Starting product recreation process...")
        
        # Analyze existing data
        product_data = self.analyze_product_data()
        
        with transaction.atomic():
            for pid, data in product_data.items():
                try:
                    # Calculate pricing
                    avg_sales = sum(data['sales_prices']) / len(data['sales_prices']) if data['sales_prices'] else 0
                    avg_purchase = sum(data['purchase_prices']) / len(data['purchase_prices']) if data['purchase_prices'] else 0
                    
                    # Use sales price for categorization, fallback to purchase price
                    avg_price = avg_sales if avg_sales > 0 else avg_purchase
                    if avg_price == 0:
                        avg_price = 100  # Default for products with no pricing data
                    
                    # Categorize and generate names
                    category = self.categorize_product(avg_price)
                    manufacturer = self.manufacturers[self.product_categories[category]['manufacturer']]
                    product_name = self.generate_product_name(category, pid)
                    part_number = f"{manufacturer.code}-{pid[-4:]}"
                    
                    # Generate descriptions
                    short_desc, long_desc = self.generate_descriptions(category, product_name, avg_sales, avg_purchase)
                    
                    # Update existing product
                    current_product = data['current_product']
                    current_product.name = product_name
                    current_product.short_description = short_desc
                    current_product.description = long_desc
                    current_product.manufacturer = manufacturer
                    current_product.manufacturer_part_number = part_number
                    current_product.list_price = Decimal(str(avg_sales)) if avg_sales > 0 else Decimal('0.00')
                    current_product.standard_cost = Decimal(str(avg_purchase)) if avg_purchase > 0 else Decimal('0.00')
                    current_product.updated_by = self.default_user
                    current_product.save()
                    
                    print(f"Updated Product {pid}: {product_name} (${avg_sales:.2f})")
                    
                except Exception as e:
                    print(f"Error updating product {pid}: {str(e)}")
        
        print("Product recreation completed!")
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print summary of recreated products"""
        print("\n" + "="*60)
        print("PRODUCT RECREATION SUMMARY")
        print("="*60)
        
        # Count by manufacturer
        for manufacturer in self.manufacturers.values():
            count = Product.objects.filter(manufacturer=manufacturer).count()
            print(f"{manufacturer.name}: {count} products")
        
        print(f"\nTotal products: {Product.objects.count()}")
        print(f"Products with pricing: {Product.objects.filter(list_price__gt=0).count()}")
        print(f"Products with manufacturer: {Product.objects.filter(manufacturer__isnull=False).count()}")
        
        # Show sample products
        print("\nSample products:")
        for product in Product.objects.filter(manufacturer__isnull=False)[:5]:
            print(f"  {product.manufacturer.brand_name} {product.manufacturer_part_number}: {product.name}")
            print(f"    Price: ${product.list_price}, Cost: ${product.standard_cost}")


def main():
    """Main execution function"""
    recreator = ProductRecreator()
    recreator.recreate_products()


if __name__ == "__main__":
    main()