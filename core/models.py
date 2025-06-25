"""
Core models for Modern ERP system.
These models provide the foundation for the entire system,
inspired by iDempiere's architecture but modernized.
"""

# Workflow models will be defined below

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, EmailValidator
from django.contrib.contenttypes.fields import GenericForeignKey
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
    partner_type = models.CharField(max_length=20, choices=PARTNER_TYPES, default='customer')
    
    # Contact information
    country = models.CharField(max_length=100, default='United States')
    phone = models.CharField(max_length=20, blank=True)
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
    
    # Data quality flag
    is_orphan = models.BooleanField(default=False, help_text="Business partner with no locations or related documents - candidate for deletion")
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-generate code if not provided
        if not self.code:
            self.code = self._generate_code()
        
        # Set boolean flags based on partner_type
        self.is_customer = self.partner_type in ['customer', 'prospect']
        self.is_vendor = self.partner_type == 'vendor'
        self.is_employee = self.partner_type == 'employee'
        self.is_prospect = self.partner_type == 'prospect'
        super().save(*args, **kwargs)
    
    def _generate_code(self):
        """Generate next business partner code (7-digit starting from 1500000)"""
        # Find the highest numeric code
        max_num = 1499999  # Start just below 1500000
        
        # Get all business partner codes
        for code in BusinessPartner.objects.all().values_list('code', flat=True):
            if code and code.isdigit():
                num = int(code)
                if num >= 1500000:  # Only consider codes in our range
                    max_num = max(max_num, num)
        
        # Return the next number (minimum 1500000)
        return str(max_num + 1)


class Opportunity(BaseModel):
    """
    Opportunity/Project model - Serves as a reference point for all related documents.
    Can be linked to sales orders, purchase orders, invoices, shipments, etc.
    Format: Q #718923
    """
    # Opportunity identification
    opportunity_number = models.CharField(max_length=50, unique=True, help_text="Q #718923 format")
    name = models.CharField(max_length=200, help_text="Descriptive name for the opportunity/project")
    description = models.TextField(blank=True)
    
    # Simple status tracking
    is_active = models.BooleanField(default=True, help_text="Whether this opportunity is currently active")
    
    class Meta:
        ordering = ['-opportunity_number']
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
    city = models.CharField(max_length=60, blank=True)
    state = models.CharField(max_length=40, blank=True, verbose_name="State/Province")
    postal_code = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=60, default='United States')
    
    # Contact information specific to this location
    phone = models.CharField(max_length=40, blank=True)
    
    # Address type flags
    is_bill_to = models.BooleanField(default=False, help_text="Billing address")
    is_ship_to = models.BooleanField(default=False, help_text="Shipping address")
    
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
            self.address2
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
    
    @property
    def full_address_with_name(self):
        """Return formatted full address with customer name on top"""
        address_lines = [self.business_partner.name]
        
        # Add the standard address lines
        if self.address1:
            address_lines.append(self.address1)
        if self.address2:
            address_lines.append(self.address2)
        
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
    
    
    # Personal information
    name = models.CharField(max_length=60, help_text="Contact full name")
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    title = models.CharField(max_length=40, blank=True, help_text="Job title")
    
    # Contact information
    email = models.EmailField(blank=True, validators=[EmailValidator()])
    phone = models.CharField(max_length=40, blank=True, verbose_name="Primary Phone")
    
    # Additional information
    description = models.CharField(max_length=255, blank=True)
    comments = models.TextField(blank=True)
    
    
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
        # Auto-populate name from first_name and last_name
        if self.first_name or self.last_name:
            name_parts = []
            if self.first_name:
                name_parts.append(self.first_name.strip())
            if self.last_name:
                name_parts.append(self.last_name.strip())
            self.name = ' '.join(name_parts)
        elif not self.name:
            # If no first/last name and no existing name, set a default
            self.name = 'Unnamed Contact'
        
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


# =============================================================================
# WORKFLOW MODELS
# =============================================================================

class WorkflowDefinition(BaseModel):
    """
    Defines workflow rules for document types
    """
    name = models.CharField(max_length=100)
    document_type = models.CharField(max_length=50, unique=True, 
                                   help_text="e.g., 'sales_order', 'purchase_order', 'invoice'")
    initial_state = models.CharField(max_length=30, default='draft')
    requires_approval = models.BooleanField(default=False)
    approval_threshold_amount = MoneyField(max_digits=15, decimal_places=2, 
                                         default_currency='USD', null=True, blank=True,
                                         help_text="Amount above which approval is required")
    approval_permission = models.CharField(max_length=100, blank=True,
                                         help_text="Permission required to approve")
    reactivation_permission = models.CharField(max_length=100, blank=True,
                                             help_text="Permission required to reactivate completed docs")
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.document_type})"


class WorkflowState(BaseModel):
    """
    Individual states in a workflow
    """
    workflow = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name='states')
    name = models.CharField(max_length=30)
    display_name = models.CharField(max_length=100)
    is_final = models.BooleanField(default=False, help_text="Cannot transition from this state")
    requires_approval = models.BooleanField(default=False)
    color_code = models.CharField(max_length=7, default='#6c757d', 
                                help_text="Hex color code for UI display")
    order = models.IntegerField(default=0, help_text="Display order")
    
    class Meta:
        unique_together = ['workflow', 'name']
        ordering = ['workflow', 'order']
        
    def __str__(self):
        return f"{self.workflow.name}: {self.display_name}"


class WorkflowTransition(BaseModel):
    """
    Valid transitions between states
    """
    workflow = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name='transitions')
    from_state = models.ForeignKey(WorkflowState, on_delete=models.CASCADE, related_name='transitions_from')
    to_state = models.ForeignKey(WorkflowState, on_delete=models.CASCADE, related_name='transitions_to')
    name = models.CharField(max_length=100, help_text="Action name (e.g., 'Submit for Approval')")
    required_permission = models.CharField(max_length=100, blank=True)
    requires_approval = models.BooleanField(default=False)
    button_color = models.CharField(max_length=20, default='blue',
                                  choices=[
                                      ('blue', 'Blue'),
                                      ('green', 'Green'),
                                      ('orange', 'Orange'),
                                      ('red', 'Red'),
                                      ('gray', 'Gray'),
                                  ])
    
    class Meta:
        unique_together = ['workflow', 'from_state', 'to_state']
        ordering = ['workflow', 'from_state__order']
        
    def __str__(self):
        return f"{self.workflow.name}: {self.from_state.name} → {self.to_state.name}"


class DocumentWorkflow(BaseModel):
    """
    Workflow instance for a specific document
    """
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    workflow_definition = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE)
    current_state = models.ForeignKey(WorkflowState, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='workflows_created')
    
    class Meta:
        unique_together = ['content_type', 'object_id']
        
    def __str__(self):
        return f"{self.content_object} - {self.current_state.display_name}"


class WorkflowApproval(BaseModel):
    """
    Approval requests and responses
    """
    APPROVAL_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    document_workflow = models.ForeignKey(DocumentWorkflow, on_delete=models.CASCADE, 
                                        related_name='approvals')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, 
                                   related_name='approval_requests_made')
    requested_at = models.DateTimeField(auto_now_add=True)
    
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='approvals_given')
    responded_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending')
    comments = models.TextField(blank=True)
    
    # Amount at time of request (for audit trail)
    amount_at_request = MoneyField(max_digits=15, decimal_places=2, default_currency='USD',
                                 null=True, blank=True)
    
    class Meta:
        ordering = ['-requested_at']
        
    def __str__(self):
        return f"{self.document_workflow.content_object} - {self.get_status_display()}"


class UserPermission(BaseModel):
    """
    User permissions for workflow actions
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workflow_permissions')
    permission_code = models.CharField(max_length=100)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='permissions_granted')
    granted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Optional limits
    approval_limit = MoneyField(max_digits=15, decimal_places=2, default_currency='USD',
                              null=True, blank=True, 
                              help_text="Maximum amount this user can approve")
    
    class Meta:
        unique_together = ['user', 'permission_code']
        
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.permission_code}"