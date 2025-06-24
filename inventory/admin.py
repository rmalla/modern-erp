"""
Django admin configuration for inventory models.
"""

from django.contrib import admin
from django.utils.html import format_html
from . import models


@admin.register(models.Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'brand_name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'brand_name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'brand_name', 'description')
        }),
    )


@admin.register(models.ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'parent', 'is_active')
    list_filter = ('parent', 'is_active')
    search_fields = ('code', 'name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'parent')
        }),
        ('Accounting Defaults', {
            'fields': ('asset_account', 'expense_account', 'revenue_account')
        }),
    )


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('manufacturer_part_number', 'name', 'manufacturer', 'product_type', 'list_price', 'is_active')
    list_filter = ('manufacturer', 'product_type', 'is_active')
    search_fields = ('manufacturer_part_number', 'name', 'short_description', 'description')
    autocomplete_fields = ['manufacturer']  # Enable autocomplete for manufacturer selection
    fieldsets = (
        ('Product ID', {
            'fields': (
                ('id',),
            )
        }),
        ('Manufacturer', {
            'fields': (
                ('manufacturer',),
                ('manufacturer_part_number',),
            )
        }),
        ('Basic Information', {
            'fields': (
                ('name',),
                ('short_description',),
                ('description',),
                ('product_type', 'uom'),
            )
        }),
        ('Physical Properties', {
            'fields': (
                ('weight', 'volume'),
            )
        }),
        ('Pricing', {
            'fields': (
                ('list_price', 'standard_cost'),
            )
        }),
        ('Accounting', {
            'fields': (
                ('tax_category',),
                ('asset_account', 'expense_account'),
                ('revenue_account',),
            )
        }),
    )
    readonly_fields = ('id', 'current_stock')
    
    def current_stock(self, obj):
        return obj.current_stock
    current_stock.short_description = 'Current Stock'


@admin.register(models.Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'organization', 'city', 'state', 'is_in_transit', 'is_quarantine', 'is_active')
    list_filter = ('organization', 'is_in_transit', 'is_quarantine', 'is_active')
    search_fields = ('code', 'name', 'address_line1', 'city')
    fieldsets = (
        ('Basic Information', {
            'fields': ('organization', 'code', 'name', 'description')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Flags', {
            'fields': ('is_in_transit', 'is_quarantine')
        }),
    )


@admin.register(models.StorageDetail)
class StorageDetailAdmin(admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'quantity_on_hand', 'quantity_reserved', 'quantity_ordered', 'quantity_available_display', 'date_last_inventory')
    list_filter = ('warehouse', 'product__manufacturer')
    search_fields = ('product__manufacturer_part_number', 'product__name', 'warehouse__name')
    readonly_fields = ('quantity_available',)
    
    def quantity_available_display(self, obj):
        available = obj.quantity_available
        if available < 0:
            return format_html('<span style="color: red;">{}</span>', available)
        elif available == 0:
            return format_html('<span style="color: orange;">{}</span>', available)
        else:
            return format_html('<span style="color: green;">{}</span>', available)
    quantity_available_display.short_description = 'Available'


@admin.register(models.PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'currency', 'is_sales_price_list', 'is_purchase_price_list', 'is_default', 'valid_from', 'valid_to', 'is_active')
    list_filter = ('organization', 'currency', 'is_sales_price_list', 'is_purchase_price_list', 'is_default', 'is_active')
    search_fields = ('name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('organization', 'name', 'description', 'currency')
        }),
        ('Flags', {
            'fields': ('is_sales_price_list', 'is_purchase_price_list', 'is_default')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_to')
        }),
    )


@admin.register(models.PriceListVersion)
class PriceListVersionAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_list', 'valid_from', 'valid_to', 'is_active')
    list_filter = ('price_list', 'is_active')
    search_fields = ('name', 'description', 'price_list__name')
    date_hierarchy = 'valid_from'


class ProductPriceInline(admin.TabularInline):
    model = models.ProductPrice
    extra = 0
    fields = ('product', 'list_price', 'standard_price', 'limit_price')


@admin.register(models.ProductPrice)
class ProductPriceAdmin(admin.ModelAdmin):
    list_display = ('product', 'price_list_version', 'list_price', 'standard_price', 'limit_price')
    list_filter = ('price_list_version__price_list', 'product__manufacturer')
    search_fields = ('product__manufacturer_part_number', 'product__name', 'price_list_version__name')
