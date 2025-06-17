"""
Django admin configuration for core models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from . import models


@admin.register(models.User)
class UserAdmin(BaseUserAdmin):
    """Extended User admin with ERP fields."""
    fieldsets = BaseUserAdmin.fieldsets + (
        ('ERP Information', {
            'fields': ('employee_id', 'department', 'phone', 'mobile', 'title', 'is_system_admin')
        }),
    )
    list_display = BaseUserAdmin.list_display + ('department', 'title', 'is_system_admin')
    list_filter = BaseUserAdmin.list_filter + ('department', 'is_system_admin')


@admin.register(models.Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'parent', 'default_currency', 'is_active')
    list_filter = ('parent', 'default_currency', 'is_active')
    search_fields = ('code', 'name', 'tax_id')
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'parent')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Financial', {
            'fields': ('tax_id', 'state_tax_id', 'default_currency', 'fiscal_year_end')
        }),
        ('System', {
            'fields': ('is_active', 'created_by', 'updated_by')
        })
    )
    readonly_fields = ('created', 'updated', 'created_by', 'updated_by')


@admin.register(models.Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'organization', 'manager', 'is_active')
    list_filter = ('organization', 'is_active')
    search_fields = ('code', 'name')


class ContactInline(admin.TabularInline):
    model = models.Contact
    extra = 1
    fields = ('name', 'title', 'email', 'phone', 'is_sales_lead', 'is_bill_to', 'is_ship_to')
    readonly_fields = ()
    can_delete = True
    show_change_link = True
    verbose_name = "Contact"
    verbose_name_plural = "Contacts"


class BusinessPartnerLocationInline(admin.TabularInline):
    model = models.BusinessPartnerLocation
    extra = 1
    fields = ('name', 'address1', 'city', 'state', 'postal_code', 'is_bill_to', 'is_ship_to')
    readonly_fields = ()
    can_delete = True
    show_change_link = True
    verbose_name = "Location"
    verbose_name_plural = "Business Partner Locations"


@admin.register(models.BusinessPartner)
class BusinessPartnerAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'partner_type', 'email', 'phone', 'contact_count', 'location_count', 'is_active')
    list_filter = ('partner_type', 'is_customer', 'is_vendor', 'is_tax_exempt', 'is_active')
    search_fields = ('code', 'name', 'search_key', 'email', 'tax_id')
    inlines = [ContactInline, BusinessPartnerLocationInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'name2', 'search_key', 'partner_type')
        }),
        ('Contact Information', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country',
                      'phone', 'phone2', 'fax', 'email', 'website')
        }),
        ('Financial', {
            'fields': ('credit_limit', 'payment_terms', 'tax_id', 'is_tax_exempt', 'is_1099_vendor')
        }),
        ('Flags', {
            'fields': ('is_customer', 'is_vendor', 'is_employee', 'is_prospect')
        }),
    )
    readonly_fields = ('is_customer', 'is_vendor', 'is_employee', 'is_prospect')
    
    def contact_count(self, obj):
        """Display number of contacts for this business partner"""
        return obj.contacts.count()
    contact_count.short_description = 'Contacts'
    
    def location_count(self, obj):
        """Display number of locations for this business partner"""
        return obj.locations.count()
    location_count.short_description = 'Locations'


@admin.register(models.Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('iso_code', 'name', 'symbol', 'precision', 'is_base_currency', 'is_active')
    list_filter = ('is_base_currency', 'is_active')
    search_fields = ('iso_code', 'name')


@admin.register(models.UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'precision', 'is_active')
    search_fields = ('code', 'name')


@admin.register(models.NumberSequence)
class NumberSequenceAdmin(admin.ModelAdmin):
    list_display = ('name', 'prefix', 'current_next', 'increment', 'restart_sequence_every', 'is_active')
    list_filter = ('restart_sequence_every', 'is_active')
    search_fields = ('name', 'prefix')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Format', {
            'fields': ('prefix', 'suffix', 'padding')
        }),
        ('Sequence', {
            'fields': ('current_next', 'increment', 'restart_sequence_every')
        }),
    )


@admin.register(models.Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ('opportunity_number', 'name', 'business_partner', 'stage', 'priority', 
                   'estimated_value', 'probability', 'expected_close_date', 'sales_rep')
    list_filter = ('stage', 'priority', 'sales_rep', 'date_opened', 'expected_close_date')
    search_fields = ('opportunity_number', 'name', 'business_partner__name', 'description')
    date_hierarchy = 'date_opened'
    
    fieldsets = (
        ('Opportunity Information', {
            'fields': ('opportunity_number', 'name', 'description')
        }),
        ('Customer & Contact', {
            'fields': ('business_partner', 'contact_person', 'contact_email', 'contact_phone')
        }),
        ('Opportunity Details', {
            'fields': ('stage', 'priority', 'probability', 'sales_rep', 'source')
        }),
        ('Financial Information', {
            'fields': ('estimated_value', 'actual_value')
        }),
        ('Timeline', {
            'fields': ('date_opened', 'expected_close_date', 'actual_close_date')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    readonly_fields = ('opportunity_number',)  # Auto-generated
    
    # Add related document counts as readonly fields
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:  # Only show counts for existing opportunities
            readonly_fields.extend(['document_summary'])
        return readonly_fields
    
    def document_summary(self, obj):
        """Show summary of related documents"""
        if not obj:
            return "Save opportunity first"
        
        return f"Sales Orders: {obj.total_sales_orders} | " \
               f"Purchase Orders: {obj.total_purchase_orders} | " \
               f"Invoices: {obj.total_invoices} | " \
               f"Shipments: {obj.total_shipments}"
    
    document_summary.short_description = "Related Documents"


@admin.register(models.PaymentTerms)
class PaymentTermsAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'net_days', 'discount_days', 'discount_percent', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description')
        }),
        ('Payment Conditions', {
            'fields': ('net_days', 'discount_days', 'discount_percent')
        }),
    )


@admin.register(models.Incoterms)
class IncotermsAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description')
        }),
        ('Responsibilities', {
            'fields': ('seller_responsibility', 'buyer_responsibility')
        }),
    )


@admin.register(models.Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'business_partner', 'email', 'phone', 'title', 'is_active')
    list_filter = ('business_partner', 'is_sales_lead', 'is_bill_to', 'is_ship_to', 'is_active')
    search_fields = ('name', 'first_name', 'last_name', 'email', 'phone', 'business_partner__name')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'first_name', 'last_name', 'title')
        }),
        ('Business Partner', {
            'fields': ('business_partner', 'business_partner_location', 'supervisor')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'phone2', 'fax')
        }),
        ('Additional Information', {
            'fields': ('description', 'comments', 'birthday')
        }),
        ('Flags', {
            'fields': ('is_sales_lead', 'is_bill_to', 'is_ship_to')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries by selecting related objects"""
        return super().get_queryset(request).select_related('business_partner', 'business_partner_location', 'supervisor')


@admin.register(models.BusinessPartnerLocation)
class BusinessPartnerLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'business_partner', 'city', 'state', 'country', 'is_bill_to', 'is_ship_to')
    list_filter = ('business_partner', 'is_bill_to', 'is_ship_to', 'is_pay_from', 'is_remit_to', 'country', 'state')
    search_fields = ('name', 'business_partner__name', 'address1', 'city', 'postal_code')
    fieldsets = (
        ('Basic Information', {
            'fields': ('business_partner', 'name')
        }),
        ('Address', {
            'fields': ('address1', 'address2', 'address3', 'city', 'state', 'postal_code', 'postal_code_add', 'country')
        }),
        ('Contact Information', {
            'fields': ('phone', 'phone2', 'fax')
        }),
        ('Location Types', {
            'fields': ('is_bill_to', 'is_ship_to', 'is_pay_from', 'is_remit_to')
        }),
        ('Additional Information', {
            'fields': ('comments',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries by selecting related objects"""
        return super().get_queryset(request).select_related('business_partner')