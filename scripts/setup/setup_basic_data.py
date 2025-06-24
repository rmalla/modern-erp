#!/usr/bin/env python3
"""
Setup script to create basic master data for Modern ERP

This script creates the essential master data needed for the system to function:
- Organization
- Currency (USD)
- Unit of Measure (Each, Hour, etc.)
- Product Categories
- Price Lists
- Warehouse
"""

import os
import django
from datetime import date

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from core.models import Organization, Currency, UnitOfMeasure, User
from inventory.models import ProductCategory, PriceList, Warehouse


def create_basic_data():
    """Create essential master data"""
    print("Creating basic master data...")
    
    # Get the admin user
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.first()
    
    # Create Organization
    org, created = Organization.objects.get_or_create(
        code='MAIN',
        defaults={
            'name': 'Main Organization',
            'description': 'Primary organization for Modern ERP',
            'created_by': admin_user,
            'updated_by': admin_user,
        }
    )
    if created:
        print(f"Created Organization: {org.name}")
    
    # Create Currency
    usd, created = Currency.objects.get_or_create(
        iso_code='USD',
        defaults={
            'symbol': '$',
            'name': 'US Dollar',
            'precision': 2,
            'is_base_currency': True,
            'created_by': admin_user,
            'updated_by': admin_user,
        }
    )
    if created:
        print(f"Created Currency: {usd.name}")
    
    # Create Units of Measure
    uoms = [
        {'code': 'EA', 'name': 'Each', 'symbol': 'ea', 'precision': 0},
        {'code': 'HR', 'name': 'Hour', 'symbol': 'hr', 'precision': 2},
        {'code': 'KG', 'name': 'Kilogram', 'symbol': 'kg', 'precision': 3},
        {'code': 'LB', 'name': 'Pound', 'symbol': 'lb', 'precision': 3},
        {'code': 'FT', 'name': 'Foot', 'symbol': 'ft', 'precision': 2},
        {'code': 'M', 'name': 'Meter', 'symbol': 'm', 'precision': 2},
    ]
    
    for uom_data in uoms:
        uom, created = UnitOfMeasure.objects.get_or_create(
            code=uom_data['code'],
            defaults={
                'name': uom_data['name'],
                'symbol': uom_data['symbol'],
                'precision': uom_data['precision'],
                'created_by': admin_user,
                'updated_by': admin_user,
            }
        )
        if created:
            print(f"Created UOM: {uom.name}")
    
    # Create Product Categories
    categories = [
        {'code': 'GENERAL', 'name': 'General Products'},
        {'code': 'SERVICES', 'name': 'Services'},
        {'code': 'MATERIALS', 'name': 'Raw Materials'},
        {'code': 'FINISHED', 'name': 'Finished Goods'},
    ]
    
    for cat_data in categories:
        cat, created = ProductCategory.objects.get_or_create(
            code=cat_data['code'],
            defaults={
                'name': cat_data['name'],
                'created_by': admin_user,
                'updated_by': admin_user,
            }
        )
        if created:
            print(f"Created Product Category: {cat.name}")
    
    # Create Price Lists
    price_lists = [
        {'name': 'Standard Sales Price List', 'is_sales': True, 'is_purchase': False},
        {'name': 'Standard Purchase Price List', 'is_sales': False, 'is_purchase': True},
    ]
    
    for pl_data in price_lists:
        pl, created = PriceList.objects.get_or_create(
            name=pl_data['name'],
            defaults={
                'organization': org,
                'currency': usd,
                'is_sales_price_list': pl_data['is_sales'],
                'is_purchase_price_list': pl_data['is_purchase'],
                'valid_from': date.today(),
                'created_by': admin_user,
                'updated_by': admin_user,
            }
        )
        if created:
            print(f"Created Price List: {pl.name}")
    
    # Create Warehouse
    warehouse, created = Warehouse.objects.get_or_create(
        code='MAIN',
        defaults={
            'name': 'Main Warehouse',
            'organization': org,
            'address_line1': '123 Main St',
            'city': 'Anytown',
            'state': 'CA',
            'postal_code': '12345',
            'created_by': admin_user,
            'updated_by': admin_user,
        }
    )
    if created:
        print(f"Created Warehouse: {warehouse.name}")
    
    print("\nBasic master data setup completed successfully!")
    print(f"Organizations: {Organization.objects.count()}")
    print(f"Currencies: {Currency.objects.count()}")
    print(f"Units of Measure: {UnitOfMeasure.objects.count()}")
    print(f"Product Categories: {ProductCategory.objects.count()}")
    print(f"Price Lists: {PriceList.objects.count()}")
    print(f"Warehouses: {Warehouse.objects.count()}")


if __name__ == "__main__":
    create_basic_data()