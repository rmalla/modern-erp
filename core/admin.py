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


@admin.register(models.BusinessPartner)
class BusinessPartnerAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'partner_type', 'email', 'phone', 'is_active')
    list_filter = ('partner_type', 'is_customer', 'is_vendor', 'is_tax_exempt', 'is_active')
    search_fields = ('code', 'name', 'search_key', 'email', 'tax_id')
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