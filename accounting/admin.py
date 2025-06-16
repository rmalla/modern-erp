"""
Django admin configuration for accounting models.
"""

from django.contrib import admin
from django.utils.html import format_html
from . import models


@admin.register(models.ChartOfAccounts)
class ChartOfAccountsAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'is_active')
    list_filter = ('organization', 'is_active')
    search_fields = ('name', 'description')


@admin.register(models.AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'balance_type', 'show_in_balance_sheet', 'show_in_income_statement')
    list_filter = ('category', 'balance_type', 'show_in_balance_sheet', 'show_in_income_statement')
    search_fields = ('name', 'description')


@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'chart_of_accounts', 'is_summary', 'is_detail', 'is_active')
    list_filter = ('chart_of_accounts', 'account_type', 'is_summary', 'is_detail', 'is_bank_account', 'is_active')
    search_fields = ('code', 'name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('chart_of_accounts', 'account_type', 'code', 'name', 'description', 'parent')
        }),
        ('Properties', {
            'fields': ('is_summary', 'is_detail', 'is_bank_account', 'is_cash_account')
        }),
        ('US GAAP', {
            'fields': ('is_current', 'requires_1099')
        }),
        ('Controls', {
            'fields': ('require_budget', 'allow_negative', 'default_tax_category')
        }),
    )


@admin.register(models.FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'start_date', 'end_date', 'is_current', 'is_closed')
    list_filter = ('organization', 'is_current', 'is_closed')
    search_fields = ('name',)
    date_hierarchy = 'start_date'


@admin.register(models.Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ('name', 'fiscal_year', 'period_number', 'start_date', 'end_date', 'is_open', 'is_closed')
    list_filter = ('fiscal_year', 'period_type', 'is_open', 'is_closed')
    search_fields = ('name',)
    date_hierarchy = 'start_date'


@admin.register(models.TaxCategory)
class TaxCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'is_active')
    list_filter = ('is_default', 'is_active')
    search_fields = ('name', 'description')


@admin.register(models.Tax)
class TaxAdmin(admin.ModelAdmin):
    list_display = ('name', 'tax_type', 'rate', 'jurisdiction', 'valid_from', 'valid_to', 'is_active')
    list_filter = ('tax_type', 'tax_category', 'jurisdiction', 'is_active')
    search_fields = ('name', 'description', 'jurisdiction')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'tax_category', 'tax_type')
        }),
        ('Calculation', {
            'fields': ('rate', 'is_percentage')
        }),
        ('Accounts', {
            'fields': ('tax_due_account', 'tax_liability_account', 'tax_expense_account')
        }),
        ('US Specific', {
            'fields': ('jurisdiction', 'tax_authority')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_to')
        }),
    )


class JournalLineInline(admin.TabularInline):
    model = models.JournalLine
    extra = 2
    fields = ('line_no', 'account', 'description', 'debit_amount', 'credit_amount', 'business_partner')


@admin.register(models.Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'description', 'journal_type', 'accounting_date', 'total_debit', 'total_credit', 'is_balanced_display', 'is_posted')
    list_filter = ('journal_type', 'organization', 'is_approved', 'is_posted')
    search_fields = ('document_no', 'description')
    date_hierarchy = 'accounting_date'
    inlines = [JournalLineInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('organization', 'document_no', 'description', 'journal_type')
        }),
        ('Dates', {
            'fields': ('accounting_date', 'document_date')
        }),
        ('References', {
            'fields': ('period', 'currency', 'exchange_rate')
        }),
        ('Status', {
            'fields': ('is_approved', 'is_posted', 'date_posted')
        }),
        ('Source', {
            'fields': ('source_document_type', 'source_document_id')
        }),
    )
    readonly_fields = ('total_debit', 'total_credit', 'date_posted')
    
    def is_balanced_display(self, obj):
        if obj.is_balanced:
            return format_html('<span style="color: green;">✓ Balanced</span>')
        else:
            return format_html('<span style="color: red;">✗ Unbalanced</span>')
    is_balanced_display.short_description = 'Balanced'


@admin.register(models.JournalLine)
class JournalLineAdmin(admin.ModelAdmin):
    list_display = ('journal', 'line_no', 'account', 'debit_amount', 'credit_amount', 'business_partner')
    list_filter = ('journal__organization', 'journal__journal_type', 'account__account_type')
    search_fields = ('journal__document_no', 'account__code', 'account__name', 'description')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('journal', 'line_no', 'account', 'description')
        }),
        ('Amounts', {
            'fields': ('debit_amount', 'credit_amount')
        }),
        ('Currency Conversion', {
            'fields': ('source_debit', 'source_credit', 'currency_rate')
        }),
        ('Dimensions', {
            'fields': ('business_partner', 'tax')
        }),
        ('References', {
            'fields': ('source_table', 'source_record_id')
        }),
    )