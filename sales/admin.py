"""
Django admin configuration for sales models.
"""

from django.contrib import admin
from django.utils.html import format_html
from . import models


class SalesOrderLineInline(admin.TabularInline):
    model = models.SalesOrderLine
    extra = 0
    fields = ('line_no', 'product', 'quantity_ordered', 'price_entered')
    readonly_fields = ('line_no',)


@admin.register(models.SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'business_partner', 'date_ordered', 'doc_status', 'grand_total', 'is_delivered', 'is_invoiced')
    list_filter = ('doc_status', 'organization', 'warehouse', 'is_delivered', 'is_invoiced', 'is_drop_ship')
    search_fields = ('document_no', 'business_partner__name', 'description')
    date_hierarchy = 'date_ordered'
    inlines = [SalesOrderLineInline]
    
    fieldsets = (
        ('Document Information', {
            'fields': ('organization', 'document_no', 'description', 'doc_status')
        }),
        ('Dates', {
            'fields': ('date_ordered', 'date_promised')
        }),
        ('Business Partner', {
            'fields': ('business_partner',)
        }),
        ('Pricing', {
            'fields': ('currency', 'total_lines', 'grand_total')
        }),
        ('Delivery', {
            'fields': ('warehouse',)
        }),
    )
    readonly_fields = ('total_lines', 'grand_total')


@admin.register(models.SalesOrderLine)
class SalesOrderLineAdmin(admin.ModelAdmin):
    list_display = ('order', 'line_no', 'product', 'charge', 'quantity_ordered', 'price_actual', 'line_net_amount')
    list_filter = ('order__organization', 'product__product_category')
    search_fields = ('order__document_no', 'product__code', 'product__name', 'description')


class InvoiceLineInline(admin.TabularInline):
    model = models.InvoiceLine
    extra = 0
    fields = ('line_no', 'product', 'charge', 'description', 'quantity_invoiced', 'price_entered', 'discount', 'line_net_amount')


@admin.register(models.Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'business_partner', 'date_invoiced', 'doc_status', 'invoice_type', 'grand_total', 'is_paid')
    list_filter = ('doc_status', 'invoice_type', 'organization', 'is_paid', 'is_posted')
    search_fields = ('document_no', 'business_partner__name', 'description')
    date_hierarchy = 'date_invoiced'
    inlines = [InvoiceLineInline]
    
    fieldsets = (
        ('Document Information', {
            'fields': ('organization', 'document_no', 'description', 'doc_status', 'invoice_type')
        }),
        ('Dates', {
            'fields': ('date_invoiced', 'date_accounting', 'due_date')
        }),
        ('Business Partner', {
            'fields': ('business_partner', 'bill_to_address')
        }),
        ('References', {
            'fields': ('sales_order',)
        }),
        ('Pricing', {
            'fields': ('price_list', 'currency', 'payment_terms', 'total_lines', 'tax_amount', 'grand_total', 'paid_amount', 'open_amount')
        }),
        ('Sales Rep', {
            'fields': ('sales_rep',)
        }),
        ('Flags', {
            'fields': ('is_printed', 'is_paid', 'is_posted')
        }),
    )
    readonly_fields = ('total_lines', 'tax_amount', 'grand_total', 'paid_amount', 'open_amount')


@admin.register(models.InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'line_no', 'product', 'charge', 'quantity_invoiced', 'price_actual', 'line_net_amount')
    list_filter = ('invoice__organization', 'product__product_category')
    search_fields = ('invoice__document_no', 'product__code', 'product__name', 'description')


class ShipmentLineInline(admin.TabularInline):
    model = models.ShipmentLine
    extra = 0
    fields = ('line_no', 'product', 'description', 'movement_quantity', 'quantity_entered')


@admin.register(models.Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'business_partner', 'movement_date', 'doc_status', 'movement_type', 'warehouse', 'is_in_transit')
    list_filter = ('doc_status', 'movement_type', 'organization', 'warehouse', 'is_in_transit')
    search_fields = ('document_no', 'business_partner__name', 'description', 'tracking_no')
    date_hierarchy = 'movement_date'
    inlines = [ShipmentLineInline]
    
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
            'fields': ('sales_order',)
        }),
        ('Shipping', {
            'fields': ('delivery_via', 'tracking_no', 'freight_amount')
        }),
        ('Flags', {
            'fields': ('is_printed', 'is_in_transit')
        }),
    )


@admin.register(models.ShipmentLine)
class ShipmentLineAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'line_no', 'product', 'movement_quantity', 'quantity_entered')
    list_filter = ('shipment__organization', 'product__product_category')
    search_fields = ('shipment__document_no', 'product__code', 'product__name', 'description')


