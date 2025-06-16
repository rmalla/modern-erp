"""
Sales models for Modern ERP system.
Sales orders, invoices, shipments, and related documents.
Based on iDempiere's C_Order, C_Invoice, M_InOut, etc.
"""

from django.db import models
from django.core.validators import MinValueValidator
from djmoney.models.fields import MoneyField
from decimal import Decimal
from core.models import BaseModel, Organization, BusinessPartner, NumberSequence
from inventory.models import Product, Warehouse, PriceList


class SalesOrder(BaseModel):
    """
    Sales Order header.
    Based on iDempiere's C_Order.
    """
    DOC_STATUS_CHOICES = [
        ('drafted', 'Drafted'),
        ('in_progress', 'In Progress'), 
        ('waiting_payment', 'Waiting Payment'),
        ('waiting_pickup', 'Waiting Pickup'),
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
    date_delivered = models.DateField(null=True, blank=True)
    
    # Customer reference
    customer_po_reference = models.CharField(max_length=100, blank=True, help_text="Customer's PO number")
    
    # Business partner information
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT, limit_choices_to={'is_customer': True})
    bill_to_address = models.TextField(blank=True)
    ship_to_address = models.TextField(blank=True)
    
    # Pricing and terms
    price_list = models.ForeignKey(PriceList, on_delete=models.PROTECT, limit_choices_to={'is_sales_price_list': True})
    currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT)
    payment_terms = models.CharField(max_length=100, default='Net 30')
    
    # Totals
    total_lines = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    grand_total = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Warehouse and delivery
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    delivery_via = models.CharField(max_length=100, blank=True)
    delivery_rule = models.CharField(max_length=50, default='Availability')
    freight_cost_rule = models.CharField(max_length=50, default='Freight Included')
    
    # Sales rep
    sales_rep = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Flags
    is_printed = models.BooleanField(default=False)
    is_delivered = models.BooleanField(default=False)
    is_invoiced = models.BooleanField(default=False)
    is_drop_ship = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date_ordered', 'document_no']
        
    def __str__(self):
        return f"{self.document_no} - {self.business_partner.name}"
    
    @property
    def total_quantity_ordered(self):
        """Total quantity ordered across all lines"""
        return sum(line.quantity_ordered for line in self.lines.all())
    
    @property
    def total_quantity_delivered(self):
        """Total quantity delivered across all lines"""
        return sum(line.quantity_delivered for line in self.lines.all())
    
    @property
    def total_quantity_pending(self):
        """Total quantity pending delivery"""
        return self.total_quantity_ordered - self.total_quantity_delivered
    
    @property
    def delivery_status(self):
        """Delivery status: 'pending', 'partial', 'complete'"""
        total_ordered = self.total_quantity_ordered
        total_delivered = self.total_quantity_delivered
        
        if total_delivered == 0:
            return 'pending'
        elif total_delivered < total_ordered:
            return 'partial'
        else:
            return 'complete'
    
    @property
    def purchase_status(self):
        """Purchase status for items needed from vendors"""
        lines_needing_purchase = self.lines.filter(quantity_to_purchase__gt=0)
        if not lines_needing_purchase.exists():
            return 'not_required'
        
        total_to_purchase = sum(line.quantity_to_purchase for line in lines_needing_purchase)
        total_on_po = sum(line.quantity_on_purchase_order for line in lines_needing_purchase)
        
        if total_on_po == 0:
            return 'pending'
        elif total_on_po < total_to_purchase:
            return 'partial'
        else:
            return 'complete'


class SalesOrderLine(BaseModel):
    """
    Sales Order line item.
    Based on iDempiere's C_OrderLine.
    """
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='lines')
    line_no = models.IntegerField()
    description = models.TextField(blank=True)
    
    # Product information
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    charge = models.ForeignKey('purchasing.Charge', on_delete=models.PROTECT, null=True, blank=True)
    
    # Quantities
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    quantity_delivered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_invoiced = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_reserved = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_to_purchase = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Quantity that needs to be purchased")
    quantity_on_purchase_order = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Quantity on PO from vendors")
    
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
    date_delivered = models.DateField(null=True, blank=True)
    
    class Meta:
        unique_together = ['order', 'line_no']
        ordering = ['order', 'line_no']
        
    def __str__(self):
        product_name = self.product.name if self.product else self.charge.name if self.charge else 'N/A'
        return f"{self.order.document_no} - Line {self.line_no}: {product_name}"


class Invoice(BaseModel):
    """
    Sales Invoice header.
    Based on iDempiere's C_Invoice.
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
        ('proforma', 'Pro Forma'),
    ]
    
    # Document information
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    document_no = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    doc_status = models.CharField(max_length=20, choices=DOC_STATUS_CHOICES, default='drafted')
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPES, default='standard')
    
    # Dates
    date_invoiced = models.DateField()
    date_accounting = models.DateField()
    due_date = models.DateField()
    
    # Business partner information
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT, limit_choices_to={'is_customer': True})
    bill_to_address = models.TextField(blank=True)
    
    # Reference to sales order
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Pricing and terms
    price_list = models.ForeignKey(PriceList, on_delete=models.PROTECT, limit_choices_to={'is_sales_price_list': True})
    currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT)
    payment_terms = models.CharField(max_length=100, default='Net 30')
    
    # Totals
    total_lines = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    tax_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    grand_total = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    paid_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    open_amount = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Sales rep
    sales_rep = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Flags
    is_printed = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)
    is_posted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date_invoiced', 'document_no']
        
    def __str__(self):
        return f"{self.document_no} - {self.business_partner.name}"


class InvoiceLine(BaseModel):
    """
    Sales Invoice line item.
    Based on iDempiere's C_InvoiceLine.
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    line_no = models.IntegerField()
    description = models.TextField(blank=True)
    
    # Product information
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    charge = models.ForeignKey('purchasing.Charge', on_delete=models.PROTECT, null=True, blank=True)
    
    # Reference to order line
    order_line = models.ForeignKey(SalesOrderLine, on_delete=models.SET_NULL, null=True, blank=True)
    
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


class Shipment(BaseModel):
    """
    Shipment/Delivery document.
    Based on iDempiere's M_InOut.
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
        ('customer_shipment', 'Customer Shipment'),
        ('customer_return', 'Customer Return'),
        ('vendor_receipt', 'Vendor Receipt'),
        ('vendor_return', 'Vendor Return'),
    ]
    
    # Document information
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    document_no = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    doc_status = models.CharField(max_length=20, choices=DOC_STATUS_CHOICES, default='drafted')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES, default='customer_shipment')
    
    # Dates
    movement_date = models.DateField()
    date_received = models.DateField(null=True, blank=True)
    
    # Business partner and warehouse
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    
    # Reference to sales order
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True)
    
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


class ShipmentLine(BaseModel):
    """
    Shipment line item.
    Based on iDempiere's M_InOutLine.
    """
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='lines')
    line_no = models.IntegerField()
    description = models.TextField(blank=True)
    
    # Product information
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    
    # Reference to order line
    order_line = models.ForeignKey(SalesOrderLine, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Quantities
    movement_quantity = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    quantity_entered = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    
    class Meta:
        unique_together = ['shipment', 'line_no']
        ordering = ['shipment', 'line_no']
        
    def __str__(self):
        return f"{self.shipment.document_no} - Line {self.line_no}: {self.product.name}"


