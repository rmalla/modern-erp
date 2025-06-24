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
    list_display = ('opportunity_number', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('opportunity_number', 'name', 'description')
    
    fieldsets = (
        ('Opportunity Information', {
            'fields': ('opportunity_number', 'name', 'description', 'is_active')
        }),
    )
    
    readonly_fields = ('opportunity_number',)  # Auto-generated


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


# =============================================================================
# WORKFLOW ADMIN
# =============================================================================

class WorkflowStateInline(admin.TabularInline):
    model = models.WorkflowState
    extra = 0
    fields = ('name', 'display_name', 'order', 'color_code', 'is_final', 'requires_approval')
    ordering = ['order']


class WorkflowTransitionInline(admin.TabularInline):
    model = models.WorkflowTransition
    extra = 0
    fields = ('name', 'from_state', 'to_state', 'button_color', 'required_permission', 'requires_approval')


@admin.register(models.WorkflowDefinition)
class WorkflowDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'document_type', 'requires_approval', 'approval_threshold_amount', 'initial_state')
    list_filter = ('requires_approval', 'document_type')
    search_fields = ('name', 'document_type')
    inlines = [WorkflowStateInline, WorkflowTransitionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'document_type', 'initial_state')
        }),
        ('Approval Settings', {
            'fields': ('requires_approval', 'approval_threshold_amount', 'approval_permission')
        }),
        ('Permissions', {
            'fields': ('reactivation_permission',)
        }),
    )


@admin.register(models.WorkflowState)
class WorkflowStateAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'display_name', 'name', 'order', 'is_final', 'requires_approval')
    list_filter = ('workflow', 'is_final', 'requires_approval')
    search_fields = ('name', 'display_name', 'workflow__name')
    ordering = ['workflow', 'order']


@admin.register(models.WorkflowTransition)
class WorkflowTransitionAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'name', 'from_state', 'to_state', 'button_color', 'requires_approval')
    list_filter = ('workflow', 'button_color', 'requires_approval')
    search_fields = ('name', 'workflow__name')


@admin.register(models.DocumentWorkflow)
class DocumentWorkflowAdmin(admin.ModelAdmin):
    list_display = ('content_object', 'current_state', 'workflow_definition', 'created_by', 'created')
    list_filter = ('workflow_definition', 'current_state', 'created')
    search_fields = ('object_id',)
    readonly_fields = ('content_type', 'object_id', 'content_object')
    
    def has_add_permission(self, request):
        # Don't allow manual creation - these are auto-created
        return False


@admin.register(models.WorkflowApproval)
class WorkflowApprovalAdmin(admin.ModelAdmin):
    list_display = ('document_workflow', 'requested_by', 'status', 'approver', 'requested_at', 'responded_at')
    list_filter = ('status', 'requested_at', 'responded_at')
    search_fields = ('requested_by__username', 'approver__username', 'comments')
    readonly_fields = ('requested_at', 'responded_at')
    
    fieldsets = (
        ('Request Information', {
            'fields': ('document_workflow', 'requested_by', 'requested_at', 'amount_at_request')
        }),
        ('Response Information', {
            'fields': ('approver', 'responded_at', 'status', 'comments')
        }),
    )


@admin.register(models.UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'permission_code', 'is_active', 'approval_limit', 'granted_by', 'granted_at')
    list_filter = ('permission_code', 'is_active', 'granted_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'permission_code')
    
    fieldsets = (
        ('Permission Details', {
            'fields': ('user', 'permission_code', 'is_active')
        }),
        ('Limits', {
            'fields': ('approval_limit',)
        }),
        ('Audit Trail', {
            'fields': ('granted_by', 'granted_at'),
            'classes': ('collapse',)
        }),
    )