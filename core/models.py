"""
Core models for Modern ERP system.
These models provide the foundation for the entire system,
inspired by iDempiere's architecture but modernized.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator
from djmoney.models.fields import MoneyField
import uuid


class BaseModel(models.Model):
    """
    Abstract base model that provides common fields for all models.
    Based on iDempiere's AD_Table structure.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('core.User', on_delete=models.PROTECT, related_name='created_%(class)s', null=True, blank=True)
    updated_by = models.ForeignKey('core.User', on_delete=models.PROTECT, related_name='updated_%(class)s', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    legacy_id = models.CharField(max_length=50, null=True, blank=True, help_text="Original ID from migrated system")
    
    class Meta:
        abstract = True


class User(AbstractUser):
    """
    Extended user model with ERP-specific fields.
    Based on iDempiere's AD_User.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    title = models.CharField(max_length=100, blank=True)
    is_system_admin = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.username})"


class Organization(BaseModel):
    """
    Organization/Company model.
    Based on iDempiere's AD_Org.
    """
    code = models.CharField(max_length=20, unique=True, validators=[MinLengthValidator(2)])
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
    # Contact information
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='United States')
    
    # Tax information
    tax_id = models.CharField(max_length=50, blank=True, help_text="Federal Tax ID / EIN")
    state_tax_id = models.CharField(max_length=50, blank=True)
    
    # Financial
    default_currency = models.CharField(max_length=3, default='USD')
    fiscal_year_end = models.CharField(max_length=5, default='12-31', help_text="MM-DD format")
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return self.name


class Department(BaseModel):
    """
    Department/Division model for organizational structure.
    """
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    manager = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_departments')
    cost_center = models.CharField(max_length=20, blank=True)
    
    class Meta:
        unique_together = ['organization', 'code']
        ordering = ['organization', 'name']
        
    def __str__(self):
        return f"{self.organization.name} - {self.name}"


class BusinessPartner(BaseModel):
    """
    Business Partner model (Customers, Vendors, Employees).
    Based on iDempiere's C_BPartner.
    """
    PARTNER_TYPES = [
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('employee', 'Employee'),
        ('prospect', 'Prospect'),
        ('other', 'Other'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    name2 = models.CharField(max_length=200, blank=True, help_text="Additional name/DBA")
    search_key = models.CharField(max_length=100, unique=True)
    partner_type = models.CharField(max_length=20, choices=PARTNER_TYPES, default='customer')
    
    # Contact information
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='United States')
    
    phone = models.CharField(max_length=20, blank=True)
    phone2 = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    
    # Tax information
    tax_id = models.CharField(max_length=50, blank=True, help_text="SSN/EIN/Tax ID")
    is_tax_exempt = models.BooleanField(default=False)
    
    # Financial information
    credit_limit = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', null=True, blank=True)
    payment_terms = models.CharField(max_length=50, default='Net 30')
    
    # Flags
    is_customer = models.BooleanField(default=False)
    is_vendor = models.BooleanField(default=False)
    is_employee = models.BooleanField(default=False)
    is_prospect = models.BooleanField(default=False)
    
    # 1099 reporting (US specific)
    is_1099_vendor = models.BooleanField(default=False, help_text="Subject to 1099 reporting")
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Set boolean flags based on partner_type
        self.is_customer = self.partner_type in ['customer', 'prospect']
        self.is_vendor = self.partner_type == 'vendor'
        self.is_employee = self.partner_type == 'employee'
        self.is_prospect = self.partner_type == 'prospect'
        super().save(*args, **kwargs)


class Currency(BaseModel):
    """
    Currency master data.
    Based on iDempiere's C_Currency.
    """
    iso_code = models.CharField(max_length=3, unique=True, help_text="ISO 4217 currency code")
    symbol = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    precision = models.IntegerField(default=2, help_text="Number of decimal places")
    is_base_currency = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['iso_code']
        verbose_name_plural = 'Currencies'
        
    def __str__(self):
        return f"{self.iso_code} - {self.name}"


class UnitOfMeasure(BaseModel):
    """
    Unit of Measure model.
    Based on iDempiere's C_UOM.
    """
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)
    precision = models.IntegerField(default=0, help_text="Number of decimal places")
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.code})"


class NumberSequence(BaseModel):
    """
    Number sequence for generating document numbers.
    Based on iDempiere's AD_Sequence.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    prefix = models.CharField(max_length=10, blank=True)
    suffix = models.CharField(max_length=10, blank=True)
    current_next = models.BigIntegerField(default=1000)
    increment = models.IntegerField(default=1)
    padding = models.IntegerField(default=0, help_text="Minimum number of digits")
    
    # Date-based sequences
    restart_sequence_every = models.CharField(
        max_length=10,
        choices=[
            ('never', 'Never'),
            ('year', 'Every Year'),
            ('month', 'Every Month'),
            ('day', 'Every Day'),
        ],
        default='never'
    )
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return self.name
    
    def get_next_number(self):
        """Generate the next number in sequence."""
        current = self.current_next
        self.current_next += self.increment
        self.save(update_fields=['current_next'])
        
        # Format with padding
        number_str = str(current).zfill(self.padding)
        return f"{self.prefix}{number_str}{self.suffix}"