"""
Purchasing models for Modern ERP system.
Purchase orders, vendor bills, receipts, and related documents.
Based on iDempiere's C_Order (purchasing), C_Invoice (vendor), M_InOut (receipts), etc.
"""

from django.db import models
from django.core.validators import MinValueValidator
from djmoney.models.fields import MoneyField
from decimal import Decimal
from core.models import BaseModel, Organization, BusinessPartner, NumberSequence, Opportunity, PaymentTerms, Incoterms, Contact, BusinessPartnerLocation
from inventory.models import Product, Warehouse, PriceList


class PurchaseOrder(BaseModel):
    """
    Purchase Order header.
    Based on iDempiere's C_Order (for purchasing).
    """
    DOC_STATUS_CHOICES = [
        ('drafted', 'Drafted'),
        ('in_progress', 'In Progress'), 
        ('waiting_delivery', 'Waiting Delivery'),
        ('waiting_invoice', 'Waiting Invoice'),
        ('complete', 'Complete'),
        ('closed', 'Closed'),
        ('reversed', 'Reversed'),
        ('voided', 'Voided'),
    ]
    
    # Document information
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    document_no = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    doc_status = models.CharField(max_length=20, choices=DOC_STATUS_CHOICES, default='drafted')
    
    # Dates
    date_ordered = models.DateField()
    date_promised = models.DateField(null=True, blank=True)
    date_received = models.DateField(null=True, blank=True)
    
    # Vendor and contact information
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT, limit_choices_to={'is_vendor': True})
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True,
                               help_text="Vendor contact for this purchase order")
    internal_user = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='purchase_orders_as_internal_contact',
                                     help_text="Our company contact handling this purchase order")
    vendor_reference = models.CharField(max_length=100, blank=True, help_text="Vendor's PO number")
    
    # Address information
    business_partner_location = models.ForeignKey(BusinessPartnerLocation, on_delete=models.SET_NULL,
                                                 null=True, blank=True,
                                                 help_text="Primary vendor address")
    bill_to_location = models.ForeignKey(BusinessPartnerLocation, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='purchase_orders_bill_to',
                                        help_text="Billing address")
    
    # Customer shipping information (for direct-to-customer shipments)
    ship_to_customer = models.ForeignKey(BusinessPartner, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='purchase_orders_ship_to_customer',
                                        limit_choices_to={'is_customer': True},
                                        help_text="Customer to ship to (for direct shipments)")
    ship_to_location = models.ForeignKey(BusinessPartnerLocation, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='purchase_orders_ship_to',
                                        help_text="Shipping address (filtered by ship-to customer)")
    
    # Legacy address fields (for backward compatibility)
    bill_to_address = models.TextField(blank=True, help_text="Legacy billing address text")
    ship_to_address = models.TextField(blank=True, help_text="Legacy shipping address text")
    
    # Opportunity tracking
    opportunity = models.ForeignKey(Opportunity, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='purchase_orders', help_text="Related opportunity (Q #XXXXXX)")
    
    # Pricing and terms
    price_list = models.ForeignKey(PriceList, on_delete=models.PROTECT, limit_choices_to={'is_purchase_price_list': True})
    currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT)
    payment_terms = models.ForeignKey(PaymentTerms, on_delete=models.PROTECT, null=True, blank=True)
    incoterms = models.ForeignKey(Incoterms, on_delete=models.PROTECT, null=True, blank=True)
    incoterms_location = models.CharField(max_length=200, blank=True, help_text="Location for incoterms (e.g., 'Miami Port' for EXW Miami Port)")
    
    # Totals
    total_lines = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    grand_total = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Warehouse and delivery
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    delivery_via = models.CharField(max_length=100, blank=True)
    delivery_rule = models.CharField(max_length=50, default='Availability')
    freight_cost_rule = models.CharField(max_length=50, default='Freight Included')
    estimated_delivery_weeks = models.PositiveSmallIntegerField(null=True, blank=True, 
                                                               verbose_name="Estimated Delivery (Weeks)",
                                                               help_text="Estimated delivery time in weeks")
    
    # Buyer
    buyer = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Flags
    is_printed = models.BooleanField(default=False)
    is_received = models.BooleanField(default=False)
    is_invoiced = models.BooleanField(default=False)
    is_drop_ship = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date_ordered', 'document_no']
        
    def __str__(self):
        return f"{self.document_no} - {self.business_partner.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate document number if not provided
        if not self.document_no:
            self.document_no = self._generate_document_number()
        super().save(*args, **kwargs)
    
    def _generate_document_number(self):
        """Generate next purchase order number in PO-XXXXXX format"""
        last_po = PurchaseOrder.objects.filter(
            document_no__startswith='PO-'
        ).order_by('-document_no').first()
        
        if last_po and last_po.document_no.startswith('PO-'):
            try:
                last_num = int(last_po.document_no[3:])  # Remove 'PO-'
                return f"PO-{last_num + 1:06d}"
            except ValueError:
                pass
        
        return "PO-000001"


class PurchaseOrderLine(BaseModel):
    """
    Purchase Order line item.
    Based on iDempiere's C_OrderLine (for purchasing).
    """
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    line_no = models.IntegerField()
    description = models.TextField(blank=True)
    
    # Product information
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    charge = models.ForeignKey('Charge', on_delete=models.PROTECT, null=True, blank=True)
    
    # Vendor product info
    vendor_product_no = models.CharField(max_length=100, blank=True)
    
    # Source tracking
    source_sales_order = models.ForeignKey('sales.SalesOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                         help_text="Sales Order that triggered this purchase")
    source_sales_order_line = models.ForeignKey('sales.SalesOrderLine', on_delete=models.SET_NULL, null=True, blank=True,
                                               help_text="Specific SO line this PO line fulfills")
    
    # Quantities
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    quantity_received = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_invoiced = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Pricing
    price_entered = MoneyField(max_digits=15, decimal_places=2, default_currency='USD')
    price_actual = MoneyField(max_digits=15, decimal_places=2, default_currency='USD')
    price_list = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    discount = models.DecimalField(max_digits=7, decimal_places=4, default=0, help_text="Percentage discount")
    
    # Totals
    line_net_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Tax
    tax = models.ForeignKey('accounting.Tax', on_delete=models.SET_NULL, null=True, blank=True)
    tax_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Dates
    date_promised = models.DateField(null=True, blank=True)
    date_received = models.DateField(null=True, blank=True)
    
    class Meta:
        unique_together = ['order', 'line_no']
        ordering = ['order', 'line_no']
        
    def __str__(self):
        product_name = self.product.name if self.product else self.charge.name if self.charge else 'N/A'
        return f"{self.order.document_no} - Line {self.line_no}: {product_name}"


class VendorBill(BaseModel):
    """
    Vendor Bill/Invoice (Accounts Payable).
    Based on iDempiere's C_Invoice (vendor type).
    """
    DOC_STATUS_CHOICES = [
        ('drafted', 'Drafted'),
        ('in_progress', 'In Progress'),
        ('complete', 'Complete'),
        ('closed', 'Closed'),
        ('reversed', 'Reversed'),
        ('paid', 'Paid'),
        ('voided', 'Voided'),
    ]
    
    INVOICE_TYPES = [
        ('standard', 'Standard Invoice'),
        ('credit_memo', 'Credit Memo'),
        ('debit_memo', 'Debit Memo'),
        ('expense_report', 'Expense Report'),
    ]
    
    # Document information
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    document_no = models.CharField(max_length=50, unique=True)
    vendor_invoice_no = models.CharField(max_length=100, blank=True, help_text="Vendor's invoice number")
    description = models.TextField(blank=True)
    doc_status = models.CharField(max_length=20, choices=DOC_STATUS_CHOICES, default='drafted')
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPES, default='standard')
    
    # Dates
    date_invoiced = models.DateField()
    date_accounting = models.DateField()
    due_date = models.DateField()
    
    # Vendor information
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT, limit_choices_to={'is_vendor': True})
    bill_to_address = models.TextField(blank=True)
    
    # Reference to purchase order
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Opportunity tracking
    opportunity = models.ForeignKey(Opportunity, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='vendor_bills', help_text="Related opportunity (Q #XXXXXX)")
    
    # Pricing and terms
    price_list = models.ForeignKey(PriceList, on_delete=models.PROTECT, limit_choices_to={'is_purchase_price_list': True})
    currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT)
    payment_terms = models.CharField(max_length=100, default='Net 30')
    
    # Totals
    total_lines = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    tax_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    grand_total = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    paid_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    open_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Buyer
    buyer = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Flags
    is_printed = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)
    is_posted = models.BooleanField(default=False)
    is_1099 = models.BooleanField(default=False, help_text="Subject to 1099 reporting")
    
    class Meta:
        ordering = ['-date_invoiced', 'document_no']
        
    def __str__(self):
        return f"{self.document_no} - {self.business_partner.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate document number if not provided
        if not self.document_no:
            self.document_no = self._generate_document_number()
        super().save(*args, **kwargs)
    
    def _generate_document_number(self):
        """Generate next vendor bill number in VB-XXXXXX format"""
        last_vb = VendorBill.objects.filter(
            document_no__startswith='VB-'
        ).order_by('-document_no').first()
        
        if last_vb and last_vb.document_no.startswith('VB-'):
            try:
                last_num = int(last_vb.document_no[3:])  # Remove 'VB-'
                return f"VB-{last_num + 1:06d}"
            except ValueError:
                pass
        
        return "VB-000001"


class VendorBillLine(BaseModel):
    """
    Vendor Bill line item.
    Based on iDempiere's C_InvoiceLine (vendor type).
    """
    invoice = models.ForeignKey(VendorBill, on_delete=models.CASCADE, related_name='lines')
    line_no = models.IntegerField()
    description = models.TextField(blank=True)
    
    # Product information
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    charge = models.ForeignKey('Charge', on_delete=models.PROTECT, null=True, blank=True)
    
    # Reference to order line
    order_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Quantities
    quantity_invoiced = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Pricing
    price_entered = MoneyField(max_digits=15, decimal_places=2, default_currency='USD')
    price_actual = MoneyField(max_digits=15, decimal_places=2, default_currency='USD')
    discount = models.DecimalField(max_digits=7, decimal_places=4, default=0, help_text="Percentage discount")
    
    # Totals
    line_net_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Tax
    tax = models.ForeignKey('accounting.Tax', on_delete=models.SET_NULL, null=True, blank=True)
    tax_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    class Meta:
        unique_together = ['invoice', 'line_no']
        ordering = ['invoice', 'line_no']
        
    def __str__(self):
        product_name = self.product.name if self.product else self.charge.name if self.charge else 'N/A'
        return f"{self.invoice.document_no} - Line {self.line_no}: {product_name}"


class Receipt(BaseModel):
    """
    Receipt/Goods Receipt document.
    Based on iDempiere's M_InOut (vendor type).
    """
    DOC_STATUS_CHOICES = [
        ('drafted', 'Drafted'),
        ('in_progress', 'In Progress'),
        ('complete', 'Complete'),
        ('closed', 'Closed'),
        ('reversed', 'Reversed'),
        ('voided', 'Voided'),
    ]
    
    MOVEMENT_TYPES = [
        ('vendor_receipt', 'Vendor Receipt'),
        ('vendor_return', 'Vendor Return'),
        ('customer_return', 'Customer Return'),
        ('internal_use', 'Internal Use'),
    ]
    
    # Document information
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    document_no = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    doc_status = models.CharField(max_length=20, choices=DOC_STATUS_CHOICES, default='drafted')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES, default='vendor_receipt')
    
    # Dates
    movement_date = models.DateField()
    date_received = models.DateField(null=True, blank=True)
    
    # Business partner and warehouse
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    
    # Reference to purchase order
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Opportunity tracking
    opportunity = models.ForeignKey(Opportunity, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='receipts', help_text="Related opportunity (Q #XXXXXX)")
    
    # Shipping information
    delivery_via = models.CharField(max_length=100, blank=True)
    tracking_no = models.CharField(max_length=100, blank=True)
    freight_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Flags
    is_printed = models.BooleanField(default=False)
    is_in_transit = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-movement_date', 'document_no']
        
    def __str__(self):
        return f"{self.document_no} - {self.business_partner.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate document number if not provided
        if not self.document_no:
            self.document_no = self._generate_document_number()
        super().save(*args, **kwargs)
    
    def _generate_document_number(self):
        """Generate next receipt number in RC-XXXXXX format"""
        last_rc = Receipt.objects.filter(
            document_no__startswith='RC-'
        ).order_by('-document_no').first()
        
        if last_rc and last_rc.document_no.startswith('RC-'):
            try:
                last_num = int(last_rc.document_no[3:])  # Remove 'RC-'
                return f"RC-{last_num + 1:06d}"
            except ValueError:
                pass
        
        return "RC-000001"


class ReceiptLine(BaseModel):
    """
    Receipt line item.
    Based on iDempiere's M_InOutLine (vendor type).
    """
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='lines')
    line_no = models.IntegerField()
    description = models.TextField(blank=True)
    
    # Product information
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    
    # Reference to order line
    order_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Quantities
    movement_quantity = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    quantity_entered = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Quality control
    is_quality_checked = models.BooleanField(default=False)
    quality_notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['receipt', 'line_no']
        ordering = ['receipt', 'line_no']
        
    def __str__(self):
        return f"{self.receipt.document_no} - Line {self.line_no}: {self.product.name}"


class Charge(BaseModel):
    """
    Additional charges (shipping, handling, etc.).
    Based on iDempiere's C_Charge.
    Shared between sales and purchasing modules.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Accounting
    charge_account = models.ForeignKey('accounting.Account', on_delete=models.PROTECT, related_name='charges_purchasing')
    
    # Tax
    tax_category = models.ForeignKey('accounting.TaxCategory', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return self.name
