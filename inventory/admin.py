"""
Django admin configuration for inventory models.
"""

from django.contrib import admin
from django.utils.html import format_html
from . import models


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
    list_display = ('code', 'name', 'product_type', 'product_category', 'list_price', 'is_sold', 'is_purchased', 'is_stocked', 'is_active')
    list_filter = ('product_type', 'product_category', 'is_sold', 'is_purchased', 'is_stocked', 'is_active')
    search_fields = ('code', 'name', 'description', 'vendor_product_no')
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'product_type', 'product_category')
        }),
        ('Physical Properties', {
            'fields': ('uom', 'weight', 'volume')
        }),
        ('Flags', {
            'fields': ('is_sold', 'is_purchased', 'is_stocked', 'is_bill_of_materials', 'is_verification_required', 'is_drop_ship')
        }),
        ('Pricing', {
            'fields': ('list_price', 'standard_cost')
        }),
        ('Inventory', {
            'fields': ('shelf_life_days', 'min_stock_level', 'max_stock_level')
        }),
        ('Vendor Information', {
            'fields': ('default_vendor', 'vendor_product_no')
        }),
        ('Accounting', {
            'fields': ('tax_category', 'asset_account', 'expense_account', 'revenue_account')
        }),
    )
    readonly_fields = ('current_stock',)
    
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
    list_filter = ('warehouse', 'product__product_category')
    search_fields = ('product__code', 'product__name', 'warehouse__name')
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
    list_filter = ('price_list_version__price_list', 'product__product_category')
    search_fields = ('product__code', 'product__name', 'price_list_version__name')
