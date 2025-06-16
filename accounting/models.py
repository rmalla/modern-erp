"""
Accounting models for Modern ERP system.
Implements double-entry bookkeeping with US GAAP compliance.
Based on iDempiere's accounting structure but modernized.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from djmoney.models.fields import MoneyField
from decimal import Decimal
from core.models import BaseModel, Organization, BusinessPartner, Currency


class ChartOfAccounts(BaseModel):
    """
    Chart of Accounts master.
    Based on iDempiere's C_Element.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['organization', 'name']
        verbose_name_plural = 'Charts of Accounts'
        
    def __str__(self):
        return f"{self.organization.name} - {self.name}"


class AccountType(BaseModel):
    """
    Account type classification following US GAAP.
    """
    ACCOUNT_CATEGORIES = [
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('revenue', 'Revenue'),
        ('expense', 'Expense'),
        ('contra', 'Contra Account'),
    ]
    
    BALANCE_TYPES = [
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    ]
    
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=ACCOUNT_CATEGORIES)
    balance_type = models.CharField(max_length=10, choices=BALANCE_TYPES)
    description = models.TextField(blank=True)
    
    # Financial statement presentation
    show_in_balance_sheet = models.BooleanField(default=False)
    show_in_income_statement = models.BooleanField(default=False)
    show_in_cash_flow = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['category', 'name']
        
    def __str__(self):
        return f"{self.get_category_display()} - {self.name}"


class Account(BaseModel):
    """
    General Ledger Account.
    Based on iDempiere's C_ElementValue with US GAAP enhancements.
    """
    chart_of_accounts = models.ForeignKey(ChartOfAccounts, on_delete=models.CASCADE)
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT)
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
    # Account properties
    is_summary = models.BooleanField(default=False, help_text="Summary account (no postings)")
    is_detail = models.BooleanField(default=True, help_text="Detail account (allows postings)")
    is_bank_account = models.BooleanField(default=False)
    is_cash_account = models.BooleanField(default=False)
    
    # US GAAP specific
    is_current = models.BooleanField(default=True, help_text="Current vs Non-current classification")
    requires_1099 = models.BooleanField(default=False, help_text="Requires 1099 reporting")
    
    # Controls
    require_budget = models.BooleanField(default=False)
    allow_negative = models.BooleanField(default=True)
    
    # Default dimensions
    default_tax_category = models.ForeignKey('TaxCategory', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = ['chart_of_accounts', 'code']
        ordering = ['chart_of_accounts', 'code']
        
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def full_path(self):
        """Get the full hierarchical path of the account."""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name


class FiscalYear(BaseModel):
    """
    Fiscal Year definition.
    Based on iDempiere's C_Year.
    """
    name = models.CharField(max_length=50)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['organization', 'name']
        ordering = ['-start_date']
        
    def __str__(self):
        return f"{self.organization.name} - {self.name}"


class Period(BaseModel):
    """
    Accounting Period.
    Based on iDempiere's C_Period.
    """
    PERIOD_TYPES = [
        ('standard', 'Standard Period'),
        ('adjustment', 'Adjustment Period'),
        ('opening', 'Opening Period'),
        ('closing', 'Closing Period'),
    ]
    
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPES, default='standard')
    start_date = models.DateField()
    end_date = models.DateField()
    period_number = models.IntegerField()
    
    # Period status
    is_open = models.BooleanField(default=True)
    is_closed = models.BooleanField(default=False)
    date_closed = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['fiscal_year', 'period_number']
        ordering = ['fiscal_year', 'period_number']
        
    def __str__(self):
        return f"{self.fiscal_year.name} - {self.name}"


class TaxCategory(BaseModel):
    """
    Tax Category for grouping tax rates.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Tax Categories'
        
    def __str__(self):
        return self.name


class Tax(BaseModel):
    """
    Tax definition (Sales Tax, VAT, etc.).
    Based on iDempiere's C_Tax with US tax enhancements.
    """
    TAX_TYPES = [
        ('sales', 'Sales Tax'),
        ('use', 'Use Tax'),
        ('vat', 'VAT'),
        ('excise', 'Excise Tax'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    tax_category = models.ForeignKey(TaxCategory, on_delete=models.CASCADE)
    tax_type = models.CharField(max_length=20, choices=TAX_TYPES, default='sales')
    
    # Tax calculation
    rate = models.DecimalField(max_digits=7, decimal_places=5, validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_percentage = models.BooleanField(default=True)
    
    # Accounts
    tax_due_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='taxes_due')
    tax_liability_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='taxes_liability')
    tax_expense_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='taxes_expense')
    
    # US specific
    jurisdiction = models.CharField(max_length=100, blank=True, help_text="State/County/City")
    tax_authority = models.CharField(max_length=200, blank=True)
    
    # Validity
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Taxes'
        
    def __str__(self):
        return f"{self.name} ({self.rate}%)"


class Journal(BaseModel):
    """
    Journal for grouping accounting entries.
    Based on iDempiere's GL_Journal.
    """
    JOURNAL_TYPES = [
        ('manual', 'Manual Entry'),
        ('sales', 'Sales'),
        ('purchase', 'Purchase'),
        ('cash', 'Cash Receipt/Payment'),
        ('bank', 'Bank Statement'),
        ('payroll', 'Payroll'),
        ('adjustment', 'Adjustment'),
        ('closing', 'Closing Entry'),
        ('allocation', 'Payment Allocation'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    document_no = models.CharField(max_length=50)
    description = models.TextField()
    journal_type = models.CharField(max_length=20, choices=JOURNAL_TYPES, default='manual')
    
    # Dates
    accounting_date = models.DateField()
    document_date = models.DateField()
    
    # References
    period = models.ForeignKey(Period, on_delete=models.PROTECT)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    
    # Amounts
    total_debit = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    total_credit = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Status
    is_approved = models.BooleanField(default=False)
    is_posted = models.BooleanField(default=False)
    date_posted = models.DateTimeField(null=True, blank=True)
    
    # References
    source_document_type = models.CharField(max_length=50, blank=True)
    source_document_id = models.UUIDField(null=True, blank=True)
    
    class Meta:
        unique_together = ['organization', 'document_no']
        ordering = ['-accounting_date', 'document_no']
        
    def __str__(self):
        return f"{self.document_no} - {self.description}"
    
    @property
    def is_balanced(self):
        """Check if journal is balanced (debits = credits)."""
        return abs(self.total_debit.amount - self.total_credit.amount) < Decimal('0.01')


class JournalLine(BaseModel):
    """
    Journal Line (individual accounting entry).
    Based on iDempiere's GL_JournalLine.
    """
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='lines')
    line_no = models.IntegerField()
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    description = models.TextField(blank=True)
    
    # Amounts
    debit_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    credit_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Currency conversion (if different from journal currency)
    source_debit = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    source_credit = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    currency_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    
    # Dimensions/Analytics
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.SET_NULL, null=True, blank=True)
    tax = models.ForeignKey(Tax, on_delete=models.SET_NULL, null=True, blank=True)
    
    # References
    source_table = models.CharField(max_length=50, blank=True)
    source_record_id = models.UUIDField(null=True, blank=True)
    
    class Meta:
        unique_together = ['journal', 'line_no']
        ordering = ['journal', 'line_no']
        
    def __str__(self):
        return f"{self.journal.document_no} - Line {self.line_no}"
    
    @property
    def amount(self):
        """Get the net amount (debit - credit)."""
        return self.debit_amount.amount - self.credit_amount.amount