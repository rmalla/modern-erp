"""
Contact and Address models for Modern ERP system.
Based on iDempiere's AD_User and C_BPartner_Location structure.
"""

from django.db import models
from django.core.validators import EmailValidator
from .models import BaseModel, BusinessPartner


class BusinessPartnerLocation(BaseModel):
    """
    Business Partner Location/Address model.
    Based on iDempiere's C_BPartner_Location and C_Location.
    Allows multiple addresses per business partner.
    """
    business_partner = models.ForeignKey(
        BusinessPartner, 
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
        BusinessPartner, 
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
    is_active = models.BooleanField(default=True)
    
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