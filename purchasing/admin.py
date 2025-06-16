"""
Django admin configuration for purchasing models.
"""

from django.contrib import admin
from django.utils.html import format_html
from . import models


class PurchaseOrderLineInline(admin.TabularInline):
    model = models.PurchaseOrderLine
    extra = 0
    fields = ('line_no', 'product', 'charge', 'description', 'quantity_ordered', 'price_entered', 'discount', 'line_net_amount')


@admin.register(models.PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'business_partner', 'date_ordered', 'doc_status', 'grand_total', 'is_received', 'is_invoiced')
    list_filter = ('doc_status', 'organization', 'warehouse', 'is_received', 'is_invoiced', 'is_drop_ship')
    search_fields = ('document_no', 'business_partner__name', 'vendor_reference', 'description')
    date_hierarchy = 'date_ordered'
    inlines = [PurchaseOrderLineInline]
    
    fieldsets = (
        ('Document Information', {
            'fields': ('organization', 'document_no', 'description', 'doc_status')
        }),
        ('Dates', {
            'fields': ('date_ordered', 'date_promised', 'date_received')
        }),
        ('Vendor', {
            'fields': ('business_partner', 'vendor_reference', 'bill_to_address', 'ship_to_address')
        }),
        ('Pricing', {
            'fields': ('price_list', 'currency', 'payment_terms', 'total_lines', 'grand_total')
        }),
        ('Delivery', {
            'fields': ('warehouse', 'delivery_via', 'delivery_rule', 'freight_cost_rule')
        }),
        ('Buyer', {
            'fields': ('buyer',)
        }),
        ('Flags', {
            'fields': ('is_printed', 'is_received', 'is_invoiced', 'is_drop_ship')
        }),
    )
    readonly_fields = ('total_lines', 'grand_total')


@admin.register(models.PurchaseOrderLine)
class PurchaseOrderLineAdmin(admin.ModelAdmin):
    list_display = ('order', 'line_no', 'product', 'charge', 'quantity_ordered', 'price_actual', 'line_net_amount')
    list_filter = ('order__organization', 'product__product_category')
    search_fields = ('order__document_no', 'product__code', 'product__name', 'vendor_product_no', 'description')


class VendorBillLineInline(admin.TabularInline):
    model = models.VendorBillLine
    extra = 0
    fields = ('line_no', 'product', 'charge', 'description', 'quantity_invoiced', 'price_entered', 'discount', 'line_net_amount')


@admin.register(models.VendorBill)
class VendorBillAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'vendor_invoice_no', 'business_partner', 'date_invoiced', 'doc_status', 'invoice_type', 'grand_total', 'is_paid', 'is_1099')
    list_filter = ('doc_status', 'invoice_type', 'organization', 'is_paid', 'is_posted', 'is_1099')
    search_fields = ('document_no', 'vendor_invoice_no', 'business_partner__name', 'description')
    date_hierarchy = 'date_invoiced'
    inlines = [VendorBillLineInline]
    
    fieldsets = (
        ('Document Information', {
            'fields': ('organization', 'document_no', 'vendor_invoice_no', 'description', 'doc_status', 'invoice_type')
        }),
        ('Dates', {
            'fields': ('date_invoiced', 'date_accounting', 'due_date')
        }),
        ('Vendor', {
            'fields': ('business_partner', 'bill_to_address')
        }),
        ('References', {
            'fields': ('purchase_order',)
        }),
        ('Pricing', {
            'fields': ('price_list', 'currency', 'payment_terms', 'total_lines', 'tax_amount', 'grand_total', 'paid_amount', 'open_amount')
        }),
        ('Buyer', {
            'fields': ('buyer',)
        }),
        ('Flags', {
            'fields': ('is_printed', 'is_paid', 'is_posted', 'is_1099')
        }),
    )
    readonly_fields = ('total_lines', 'tax_amount', 'grand_total', 'paid_amount', 'open_amount')


@admin.register(models.VendorBillLine)
class VendorBillLineAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'line_no', 'product', 'charge', 'quantity_invoiced', 'price_actual', 'line_net_amount')
    list_filter = ('invoice__organization', 'product__product_category')
    search_fields = ('invoice__document_no', 'invoice__vendor_invoice_no', 'product__code', 'product__name', 'description')


class ReceiptLineInline(admin.TabularInline):
    model = models.ReceiptLine
    extra = 0
    fields = ('line_no', 'product', 'description', 'movement_quantity', 'quantity_entered', 'is_quality_checked')


@admin.register(models.Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'business_partner', 'movement_date', 'doc_status', 'movement_type', 'warehouse', 'is_in_transit')
    list_filter = ('doc_status', 'movement_type', 'organization', 'warehouse', 'is_in_transit')
    search_fields = ('document_no', 'business_partner__name', 'description', 'tracking_no')
    date_hierarchy = 'movement_date'
    inlines = [ReceiptLineInline]
    
    fieldsets = (
        ('Document Information', {
            'fields': ('organization', 'document_no', 'description', 'doc_status', 'movement_type')
        }),
        ('Dates', {
            'fields': ('movement_date', 'date_received')
        }),
        ('Business Partner & Warehouse', {
            'fields': ('business_partner', 'warehouse')
        }),
        ('References', {
            'fields': ('purchase_order',)
        }),
        ('Shipping', {
            'fields': ('delivery_via', 'tracking_no', 'freight_amount')
        }),
        ('Flags', {
            'fields': ('is_printed', 'is_in_transit')
        }),
    )


@admin.register(models.ReceiptLine)
class ReceiptLineAdmin(admin.ModelAdmin):
    list_display = ('receipt', 'line_no', 'product', 'movement_quantity', 'quantity_entered', 'is_quality_checked')
    list_filter = ('receipt__organization', 'product__product_category', 'is_quality_checked')
    search_fields = ('receipt__document_no', 'product__code', 'product__name', 'description')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('receipt', 'line_no', 'product', 'description')
        }),
        ('Quantities', {
            'fields': ('movement_quantity', 'quantity_entered')
        }),
        ('Quality Control', {
            'fields': ('is_quality_checked', 'quality_notes')
        }),
        ('References', {
            'fields': ('order_line',)
        }),
    )


@admin.register(models.Charge)
class ChargeAdmin(admin.ModelAdmin):
    list_display = ('name', 'charge_account', 'tax_category', 'is_active')
    list_filter = ('charge_account', 'tax_category', 'is_active')
    search_fields = ('name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Accounting', {
            'fields': ('charge_account', 'tax_category')
        }),
    )
