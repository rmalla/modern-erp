"""
Core models for Modern ERP system.
These models provide the foundation for the entire system,
inspired by iDempiere's architecture but modernized.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, EmailValidator
from djmoney.models.fields import MoneyField
from django.utils import timezone
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


class Opportunity(BaseModel):
    """
    Opportunity model - Central hub for all related documents.
    Provides unified tracking across sales orders, purchase orders, invoices, shipments, etc.
    Format: Q #718923
    """
    OPPORTUNITY_STAGES = [
        ('prospecting', 'Prospecting'),
        ('qualification', 'Qualification'),
        ('proposal', 'Proposal'),
        ('negotiation', 'Negotiation'),
        ('closed_won', 'Closed Won'),
        ('closed_lost', 'Closed Lost'),
        ('on_hold', 'On Hold'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Opportunity identification
    opportunity_number = models.CharField(max_length=50, unique=True, help_text="Q #718923 format")
    name = models.CharField(max_length=200, help_text="Descriptive name for the opportunity")
    description = models.TextField(blank=True)
    
    # Business partner and contact
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT, 
                                       limit_choices_to={'is_customer': True},
                                       help_text="Primary customer for this opportunity")
    contact_person = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    
    # Opportunity details
    stage = models.CharField(max_length=20, choices=OPPORTUNITY_STAGES, default='prospecting')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    probability = models.DecimalField(max_digits=5, decimal_places=2, default=0, 
                                    help_text="Probability of closing (0-100%)")
    
    # Financial information
    estimated_value = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', 
                               null=True, blank=True, help_text="Estimated total opportunity value")
    actual_value = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', 
                            null=True, blank=True, help_text="Actual closed value")
    
    # Dates
    date_opened = models.DateField(default=timezone.now)
    expected_close_date = models.DateField(null=True, blank=True)
    actual_close_date = models.DateField(null=True, blank=True)
    
    # Sales information
    sales_rep = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='opportunities')
    source = models.CharField(max_length=100, blank=True, help_text="Lead source (website, referral, etc.)")
    
    # Internal notes
    notes = models.TextField(blank=True, help_text="Internal notes and updates")
    
    class Meta:
        ordering = ['-date_opened', 'opportunity_number']
        verbose_name_plural = 'Opportunities'
        
    def __str__(self):
        return f"{self.opportunity_number} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate opportunity number if not provided
        if not self.opportunity_number:
            self.opportunity_number = self._generate_opportunity_number()
        super().save(*args, **kwargs)
    
    def _generate_opportunity_number(self):
        """Generate next opportunity number in Q #XXXXXX format"""
        last_opp = Opportunity.objects.filter(
            opportunity_number__startswith='Q #'
        ).order_by('-opportunity_number').first()
        
        if last_opp and last_opp.opportunity_number.startswith('Q #'):
            try:
                last_num = int(last_opp.opportunity_number[3:])  # Remove 'Q #'
                return f"Q #{last_num + 1:06d}"
            except ValueError:
                pass
        
        return "Q #000001"
    
    @property
    def total_sales_orders(self):
        """Count of related sales orders"""
        return self.sales_orders.count()
    
    @property
    def total_purchase_orders(self):
        """Count of related purchase orders"""
        return self.purchase_orders.count()
    
    @property
    def total_invoices(self):
        """Count of related invoices"""
        return self.invoices.count()
    
    @property
    def total_shipments(self):
        """Count of related shipments"""
        return self.shipments.count()
    
    @property
    def is_closed(self):
        """Check if opportunity is closed (won or lost)"""
        return self.stage in ['closed_won', 'closed_lost']
    
    @property
    def is_active(self):
        """Check if opportunity is still active"""
        return self.stage not in ['closed_won', 'closed_lost']


class PaymentTerms(BaseModel):
    """
    Payment terms master data for orders and invoices.
    """
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    net_days = models.IntegerField(default=30, help_text="Number of days for payment")
    discount_days = models.IntegerField(default=0, help_text="Days for early payment discount")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Early payment discount percentage")
    
    class Meta:
        ordering = ['code']
        verbose_name_plural = 'Payment Terms'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Incoterms(BaseModel):
    """
    International Commercial Terms master data.
    """
    code = models.CharField(max_length=10, unique=True, help_text="Incoterm code (e.g., EXW, FOB, CIF)")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, help_text="Full description of the incoterm")
    seller_responsibility = models.TextField(blank=True, help_text="What seller is responsible for")
    buyer_responsibility = models.TextField(blank=True, help_text="What buyer is responsible for")
    
    class Meta:
        ordering = ['code']
        verbose_name_plural = 'Incoterms'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


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


class BusinessPartnerLocation(BaseModel):
    """
    Business Partner Location/Address model.
    Based on iDempiere's C_BPartner_Location and C_Location.
    Allows multiple addresses per business partner.
    """
    business_partner = models.ForeignKey(
        'BusinessPartner', 
        on_delete=models.CASCADE, 
        related_name='locations'
    )
    
    # Location identification
    name = models.CharField(
        max_length=60, 
        help_text="Location name (e.g., 'Main Office', 'Warehouse', 'Billing')"
    )
    
    # Address fields (based on C_Location)
    address1 = models.CharField(max_length=60, blank=True, verbose_name="Address Line 1")
    address2 = models.CharField(max_length=60, blank=True, verbose_name="Address Line 2") 
    address3 = models.CharField(max_length=60, blank=True, verbose_name="Address Line 3")
    city = models.CharField(max_length=60, blank=True)
    state = models.CharField(max_length=40, blank=True, verbose_name="State/Province")
    postal_code = models.CharField(max_length=10, blank=True)
    postal_code_add = models.CharField(max_length=10, blank=True, verbose_name="Additional Postal Code")
    country = models.CharField(max_length=60, default='United States')
    
    # Contact information specific to this location
    phone = models.CharField(max_length=40, blank=True)
    phone2 = models.CharField(max_length=40, blank=True, verbose_name="Phone 2")
    fax = models.CharField(max_length=40, blank=True)
    
    # Address type flags
    is_bill_to = models.BooleanField(default=False, help_text="Billing address")
    is_ship_to = models.BooleanField(default=False, help_text="Shipping address") 
    is_pay_from = models.BooleanField(default=False, help_text="Payment address")
    is_remit_to = models.BooleanField(default=False, help_text="Remit-to address")
    
    # Additional fields
    comments = models.TextField(blank=True, help_text="Address comments")
    
    class Meta:
        ordering = ['business_partner', 'name']
        verbose_name = 'Business Partner Location'
        verbose_name_plural = 'Business Partner Locations'
    
    def __str__(self):
        return f"{self.business_partner.name} - {self.name}"
    
    @property
    def full_address(self):
        """Return formatted full address"""
        address_lines = [
            self.address1,
            self.address2,
            self.address3
        ]
        address_lines = [line for line in address_lines if line.strip()]
        
        if self.city or self.state or self.postal_code:
            city_state_zip = []
            if self.city:
                city_state_zip.append(self.city)
            if self.state:
                city_state_zip.append(self.state)
            if self.postal_code:
                city_state_zip.append(self.postal_code)
            
            if city_state_zip:
                address_lines.append(' '.join(city_state_zip))
        
        if self.country and self.country != 'United States':
            address_lines.append(self.country)
        
        return '\n'.join(address_lines)


class Contact(BaseModel):
    """
    Contact model based on iDempiere's AD_User.
    Represents individual contacts associated with business partners.
    """
    business_partner = models.ForeignKey(
        'BusinessPartner', 
        on_delete=models.CASCADE, 
        related_name='contacts',
        null=True, 
        blank=True,
        help_text="Associated business partner"
    )
    
    business_partner_location = models.ForeignKey(
        BusinessPartnerLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Specific location this contact is associated with"
    )
    
    # Personal information
    name = models.CharField(max_length=60, help_text="Contact full name")
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    title = models.CharField(max_length=40, blank=True, help_text="Job title")
    
    # Contact information
    email = models.EmailField(blank=True, validators=[EmailValidator()])
    phone = models.CharField(max_length=40, blank=True, verbose_name="Primary Phone")
    phone2 = models.CharField(max_length=40, blank=True, verbose_name="Secondary Phone")
    fax = models.CharField(max_length=40, blank=True)
    
    # Additional information
    description = models.CharField(max_length=255, blank=True)
    comments = models.TextField(blank=True)
    birthday = models.DateField(null=True, blank=True)
    
    # Contact flags
    is_sales_lead = models.BooleanField(default=False, help_text="Sales lead contact")
    is_bill_to = models.BooleanField(default=False, help_text="Billing contact")
    is_ship_to = models.BooleanField(default=False, help_text="Shipping contact")
    
    # Supervisor relationship
    supervisor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Contact's supervisor"
    )
    
    class Meta:
        ordering = ['business_partner', 'name']
        
    def __str__(self):
        if self.business_partner:
            return f"{self.name} ({self.business_partner.name})"
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-populate first_name and last_name from name if they're empty
        if self.name and not self.first_name and not self.last_name:
            name_parts = self.name.strip().split()
            if len(name_parts) >= 2:
                self.first_name = name_parts[0]
                self.last_name = ' '.join(name_parts[1:])
            elif len(name_parts) == 1:
                self.first_name = name_parts[0]
        
        super().save(*args, **kwargs)
    
    @property
    def full_name(self):
        """Return formatted full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.name
    
    @property
    def display_name(self):
        """Return display name with title if available"""
        name = self.full_name
        if self.title:
            return f"{name}, {self.title}"
        return name