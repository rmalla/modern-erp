"""
Django admin configuration for purchasing models.
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
            
            if 'bill_to_address' in self.fields:
                self.fields['bill_to_address'].queryset = locations
                self.fields['bill_to_address'].help_text = f"Addresses for {self.instance.business_partner.name}"
            
            if 'ship_to_address' in self.fields:
                self.fields['ship_to_address'].queryset = locations
                self.fields['ship_to_address'].help_text = f"Addresses for {self.instance.business_partner.name}"
                
        else:
            # No business partner selected, clear all dependent fields
            self.fields['contact'].queryset = Contact.objects.none()
            self.fields['contact'].help_text = "Save with a business partner first to see available contacts"
            
            from core.models import BusinessPartnerLocation
            
            if 'bill_to_address' in self.fields:
                self.fields['bill_to_address'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['bill_to_address'].help_text = "Save with a business partner first to see available addresses"
            
            if 'ship_to_address' in self.fields:
                self.fields['ship_to_address'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['ship_to_address'].help_text = "Save with a business partner first to see available addresses"


class PurchaseOrderForm(DocumentContactForm):
    class Meta:
        model = models.PurchaseOrder
        fields = '__all__'


class PurchaseOrderLineInline(admin.TabularInline):
    model = models.PurchaseOrderLine
    extra = 0
    fields = ('line_no', 'product', 'charge', 'description', 'quantity_ordered', 'price_entered', 'discount', 'line_net_amount')


@admin.register(models.PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    form = PurchaseOrderForm
    list_display = ('document_no', 'opportunity', 'business_partner', 'date_ordered', 'doc_status', 'grand_total', 'is_received', 'is_invoiced')
    list_filter = ('doc_status', 'opportunity', 'organization', 'warehouse', 'is_received', 'is_invoiced', 'is_drop_ship')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'vendor_reference', 'description')
    date_hierarchy = 'date_ordered'
    inlines = [PurchaseOrderLineInline]
    autocomplete_fields = ['opportunity', 'business_partner']
    
    fieldsets = (
        ('Purchase Order Header', {
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
            'description': 'Internal User: Our company contact | Contact: Vendor contact (save document first to see filtered options)'
        }),
        ('Document Information', {
            'fields': (
                ('organization', 'document_no'),
                ('description', 'doc_status'),
            ),
            'classes': ('wide',)
        }),
        ('Vendor Details', {
            'fields': (
                ('vendor_reference', 'buyer'),
                ('business_partner_location', 'business_partner_address_display'),
                ('bill_to_location', 'bill_to_address_display'),
                ('ship_to_location', 'ship_to_address_display'),
                ('bill_to_address', 'ship_to_address'),
            ),
            'classes': ('wide',)
        }),
        ('Pricing', {
            'fields': (
                ('price_list', 'currency'),
                ('total_lines', 'grand_total'),
            ),
            'classes': ('wide',)
        }),
        ('Delivery', {
            'fields': (
                ('warehouse', 'delivery_via'),
                ('delivery_rule', 'freight_cost_rule'),
                ('date_received', 'estimated_delivery_weeks'),
            ),
            'classes': ('wide',)
        }),
        ('Flags', {
            'fields': (
                ('is_printed', 'is_received'),
                ('is_invoiced', 'is_drop_ship'),
            ),
            'classes': ('wide',)
        }),
    )
    readonly_fields = ('total_lines', 'grand_total', 'business_partner_address_display', 'bill_to_address_display', 'ship_to_address_display')
    
    def business_partner_address_display(self, obj):
        """Display business partner location with vendor name"""
        if obj.business_partner_location:
            return obj.business_partner_location.full_address_with_name
        return "-"
    business_partner_address_display.short_description = "Primary Address"
    
    def bill_to_address_display(self, obj):
        """Display bill to location with vendor name"""
        if obj.bill_to_location:
            return obj.bill_to_location.full_address_with_name
        return "-"
    bill_to_address_display.short_description = "Bill To Address"
    
    def ship_to_address_display(self, obj):
        """Display ship to location with vendor name"""
        if obj.ship_to_location:
            return obj.ship_to_location.full_address_with_name
        return "-"
    ship_to_address_display.short_description = "Ship To Address"


@admin.register(models.PurchaseOrderLine)
class PurchaseOrderLineAdmin(admin.ModelAdmin):
    list_display = ('order', 'line_no', 'product', 'charge', 'quantity_ordered', 'price_actual', 'line_net_amount')
    list_filter = ('order__organization', 'product__manufacturer')
    search_fields = ('order__document_no', 'product__manufacturer_part_number', 'product__name', 'vendor_product_no', 'description')


class VendorBillLineInline(admin.TabularInline):
    model = models.VendorBillLine
    extra = 0
    fields = ('line_no', 'product', 'charge', 'description', 'quantity_invoiced', 'price_entered', 'discount', 'line_net_amount')


@admin.register(models.VendorBill)
class VendorBillAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'opportunity', 'vendor_invoice_no', 'business_partner', 'date_invoiced', 'doc_status', 'invoice_type', 'grand_total', 'is_paid', 'is_1099')
    list_filter = ('doc_status', 'opportunity', 'invoice_type', 'organization', 'is_paid', 'is_posted', 'is_1099')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'vendor_invoice_no', 'business_partner__name', 'description')
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
            'fields': ('opportunity', 'purchase_order')
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
    list_filter = ('invoice__organization', 'product__manufacturer')
    search_fields = ('invoice__document_no', 'invoice__vendor_invoice_no', 'product__manufacturer_part_number', 'product__name', 'description')


class ReceiptLineInline(admin.TabularInline):
    model = models.ReceiptLine
    extra = 0
    fields = ('line_no', 'product', 'description', 'movement_quantity', 'quantity_entered', 'is_quality_checked')


@admin.register(models.Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'opportunity', 'business_partner', 'movement_date', 'doc_status', 'movement_type', 'warehouse', 'is_in_transit')
    list_filter = ('doc_status', 'opportunity', 'movement_type', 'organization', 'warehouse', 'is_in_transit')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description', 'tracking_no')
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
            'fields': ('opportunity', 'purchase_order')
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
    list_filter = ('receipt__organization', 'product__manufacturer', 'is_quality_checked')
    search_fields = ('receipt__document_no', 'product__manufacturer_part_number', 'product__name', 'description')
    
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
