"""
Django admin configuration for sales models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django import forms
from . import models
from core.models import Contact


class DocumentContactForm(forms.ModelForm):
    """Custom form for documents with contact and location filtering based on business partner"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If we have an instance with a business partner, filter the contacts and locations
        if hasattr(self.instance, 'business_partner') and self.instance.business_partner:
            # Filter contacts
            self.fields['contact'].queryset = Contact.objects.filter(
                business_partner=self.instance.business_partner
            )
            self.fields['contact'].help_text = f"Contacts for {self.instance.business_partner.name}"
            
            # Filter locations for bill_to and ship_to
            from core.models import BusinessPartnerLocation
            locations = BusinessPartnerLocation.objects.filter(
                business_partner=self.instance.business_partner
            )
            
            if 'business_partner_location' in self.fields:
                self.fields['business_partner_location'].queryset = locations
                self.fields['business_partner_location'].help_text = f"Addresses for {self.instance.business_partner.name}"
            
            if 'bill_to_location' in self.fields:
                self.fields['bill_to_location'].queryset = locations
                self.fields['bill_to_location'].help_text = f"Billing addresses for {self.instance.business_partner.name}"
            
            if 'ship_to_location' in self.fields:
                self.fields['ship_to_location'].queryset = locations
                self.fields['ship_to_location'].help_text = f"Shipping addresses for {self.instance.business_partner.name}"
                
        else:
            # No business partner selected, clear all dependent fields
            self.fields['contact'].queryset = Contact.objects.none()
            self.fields['contact'].help_text = "Save with a business partner first to see available contacts"
            
            from core.models import BusinessPartnerLocation
            
            if 'business_partner_location' in self.fields:
                self.fields['business_partner_location'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['business_partner_location'].help_text = "Save with a business partner first to see available addresses"
            
            if 'bill_to_location' in self.fields:
                self.fields['bill_to_location'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['bill_to_location'].help_text = "Save with a business partner first to see available addresses"
            
            if 'ship_to_location' in self.fields:
                self.fields['ship_to_location'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['ship_to_location'].help_text = "Save with a business partner first to see available addresses"


class SalesOrderLineInline(admin.TabularInline):
    model = models.SalesOrderLine
    extra = 0
    fields = ('line_no', 'product', 'quantity_ordered', 'price_entered')
    readonly_fields = ('line_no',)


class SalesOrderForm(DocumentContactForm):
    class Meta:
        model = models.SalesOrder
        fields = '__all__'


class InvoiceForm(DocumentContactForm):
    class Meta:
        model = models.Invoice
        fields = '__all__'


class ShipmentForm(DocumentContactForm):
    class Meta:
        model = models.Shipment
        fields = '__all__'


@admin.register(models.SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    form = SalesOrderForm
    list_display = ('document_no', 'opportunity', 'business_partner', 'date_ordered', 'doc_status', 'grand_total', 'is_delivered', 'is_invoiced')
    list_filter = ('doc_status', 'opportunity', 'organization', 'warehouse', 'is_delivered', 'is_invoiced', 'is_drop_ship')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description')
    date_hierarchy = 'date_ordered'
    inlines = [SalesOrderLineInline]
    
    fieldsets = (
        ('Order Header', {
            'fields': (
                ('business_partner', 'opportunity'),
                ('date_ordered', 'date_promised'),
                ('payment_terms', 'incoterms'),
                ('incoterms_location',),
            ),
            'classes': ('wide',)
        }),
        ('Contact Information', {
            'fields': (
                ('internal_user', 'contact'),
            ),
            'classes': ('wide',),
            'description': 'Internal User: Our company contact | Contact: Customer contact (save document first to see filtered options)'
        }),
        ('Address Information', {
            'fields': (
                ('business_partner_location', 'bill_to_location'),
                ('ship_to_location',),
            ),
            'classes': ('wide',),
            'description': 'All addresses filtered by business partner (save document first to see available addresses)'
        }),
        ('Document Information', {
            'fields': (
                ('organization', 'document_no'),
                ('description', 'doc_status'),
            ),
            'classes': ('wide',)
        }),
        ('Pricing', {
            'fields': (
                ('currency', 'warehouse'),
                ('total_lines', 'grand_total'),
            ),
            'classes': ('wide',)
        }),
    )
    readonly_fields = ('total_lines', 'grand_total')


@admin.register(models.SalesOrderLine)
class SalesOrderLineAdmin(admin.ModelAdmin):
    list_display = ('order', 'line_no', 'product', 'charge', 'quantity_ordered', 'price_actual', 'line_net_amount')
    list_filter = ('order__organization', 'product__manufacturer')
    search_fields = ('order__document_no', 'product__manufacturer_part_number', 'product__name', 'description')


class InvoiceLineInline(admin.TabularInline):
    model = models.InvoiceLine
    extra = 0
    fields = ('line_no', 'product', 'charge', 'description', 'quantity_invoiced', 'price_entered', 'discount', 'line_net_amount')


@admin.register(models.Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    form = InvoiceForm
    list_display = ('document_no', 'opportunity', 'business_partner', 'date_invoiced', 'doc_status', 'invoice_type', 'grand_total', 'is_paid')
    list_filter = ('doc_status', 'opportunity', 'invoice_type', 'organization', 'is_paid', 'is_posted')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description')
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
        ('Contact Information', {
            'fields': (
                ('internal_user', 'contact'),
            ),
            'classes': ('wide',),
            'description': 'Internal User: Our company contact | Contact: Customer contact (save document first to see filtered options)'
        }),
        ('References', {
            'fields': ('opportunity', 'sales_order')
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
    list_filter = ('invoice__organization', 'product__manufacturer')
    search_fields = ('invoice__document_no', 'product__manufacturer_part_number', 'product__name', 'description')


class ShipmentLineInline(admin.TabularInline):
    model = models.ShipmentLine
    extra = 0
    fields = ('line_no', 'product', 'description', 'movement_quantity', 'quantity_entered')


@admin.register(models.Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    form = ShipmentForm
    list_display = ('document_no', 'opportunity', 'business_partner', 'movement_date', 'doc_status', 'movement_type', 'warehouse', 'is_in_transit')
    list_filter = ('doc_status', 'opportunity', 'movement_type', 'organization', 'warehouse', 'is_in_transit')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description', 'tracking_no')
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
        ('Contact Information', {
            'fields': (
                ('internal_user', 'contact'),
            ),
            'classes': ('wide',),
            'description': 'Internal User: Our company contact | Contact: Customer contact (save document first to see filtered options)'
        }),
        ('References', {
            'fields': ('opportunity', 'sales_order')
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
    list_filter = ('shipment__organization', 'product__manufacturer')
    search_fields = ('shipment__document_no', 'product__manufacturer_part_number', 'product__name', 'description')


