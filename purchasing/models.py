"""
Purchasing models for Modern ERP system.
Purchase orders, vendor bills, receipts, and related documents.
Based on iDempiere's C_Order (purchasing), C_Invoice (vendor), M_InOut (receipts), etc.
"""

from django.db import models
from django.core.validators import MinValueValidator
from djmoney.models.fields import MoneyField
from decimal import Decimal
from django.utils import timezone
from core.models import BaseModel, Organization, BusinessPartner, NumberSequence, Opportunity, PaymentTerms, Incoterms, Contact, BusinessPartnerLocation
from inventory.models import Product, Warehouse, PriceList


def get_default_organization():
    """Get default organization (Main Organization)"""
    try:
        return Organization.objects.get(name='Main Organization')
    except Organization.DoesNotExist:
        return Organization.objects.first()


def get_default_currency():
    """Get default currency (USD)"""
    try:
        from core.models import Currency
        return Currency.objects.get(iso_code='USD')
    except:
        from core.models import Currency
        return Currency.objects.first()


def get_default_warehouse():
    """Get default warehouse (Main Organization - Main Warehouse)"""
    try:
        return Warehouse.objects.get(name='Main Warehouse')
    except Warehouse.DoesNotExist:
        return Warehouse.objects.first()


def get_default_purchase_price_list():
    """Get default purchase price list (Main Organization - Standard Purchase Price List)"""
    try:
        return PriceList.objects.get(
            name='Main Organization - Standard Purchase Price List',
            is_purchase_price_list=True
        )
    except PriceList.DoesNotExist:
        return PriceList.objects.filter(is_purchase_price_list=True).first()


def get_today_date():
    """Get today's date"""
    return timezone.now().date()


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
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, default=get_default_organization)
    document_no = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    doc_status = models.CharField(max_length=20, choices=DOC_STATUS_CHOICES, default='drafted')
    
    # Dates
    date_ordered = models.DateField(default=get_today_date)
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
    
    
    # Opportunity tracking
    opportunity = models.ForeignKey(Opportunity, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='purchase_orders', help_text="Related opportunity (Q #XXXXXX)")
    
    # Pricing and terms
    price_list = models.ForeignKey(PriceList, on_delete=models.PROTECT, limit_choices_to={'is_purchase_price_list': True}, default=get_default_purchase_price_list)
    currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT, default=get_default_currency)
    payment_terms = models.ForeignKey(PaymentTerms, on_delete=models.PROTECT, null=True, blank=True)
    incoterms = models.ForeignKey(Incoterms, on_delete=models.PROTECT, null=True, blank=True)
    incoterms_location = models.CharField(max_length=200, blank=True, help_text="Location for incoterms (e.g., 'Miami Port' for EXW Miami Port)")
    
    # Totals
    total_lines = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    grand_total = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    # Warehouse and delivery
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, default=get_default_warehouse)
    delivery_via = models.CharField(max_length=100, blank=True)
    delivery_rule = models.CharField(max_length=50, default='Availability')
    freight_cost_rule = models.CharField(max_length=50, default='Freight Included')
    estimated_delivery_weeks = models.PositiveSmallIntegerField(null=True, blank=True, 
                                                               verbose_name="Estimated Delivery (Weeks)",
                                                               help_text="Estimated delivery time in weeks")
    
    # Buyer
    buyer = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Flags
    is_received = models.BooleanField(default=False)
    is_invoiced = models.BooleanField(default=False)
    is_drop_ship = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date_ordered', 'document_no']
        
    def __str__(self):
        # Add PO- prefix for display
        doc_display = f"PO-{self.document_no}" if self.document_no.isdigit() else self.document_no
        return f"{doc_display} - {self.business_partner.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate document number if not provided
        if not self.document_no:
            self.document_no = self._generate_document_number()
        super().save(*args, **kwargs)
    
    def _generate_document_number(self):
        """Generate next purchase order number (numeric only)"""
        import re
        
        # Find the highest numeric document number
        max_num = 0
        
        # Get all document numbers
        for doc_no in PurchaseOrder.objects.all().values_list('document_no', flat=True):
            if doc_no:
                # Check if it's purely numeric
                if doc_no.isdigit():
                    max_num = max(max_num, int(doc_no))
                else:
                    # Extract any numbers from the string (for legacy data)
                    match = re.search(r'(\d+)', doc_no)
                    if match:
                        num = int(match.group(1))
                        max_num = max(max_num, num)
        
        # Return the next number
        return str(max_num + 1)
    
    # =============================================================================
    # WORKFLOW METHODS (copied from SalesOrder pattern)
    # =============================================================================
    
    def get_workflow_instance(self):
        """Get or create workflow instance for this purchase order"""
        # Return None if object hasn't been saved yet
        if self.pk is None:
            return None
            
        from django.contrib.contenttypes.models import ContentType
        from core.models import DocumentWorkflow, WorkflowDefinition, WorkflowState
        
        content_type = ContentType.objects.get_for_model(self)
        
        try:
            return DocumentWorkflow.objects.get(
                content_type=content_type,
                object_id=self.pk
            )
        except DocumentWorkflow.DoesNotExist:
            # Create workflow instance if it doesn't exist
            try:
                workflow_def = WorkflowDefinition.objects.get(document_type='purchase_order')
                initial_state = WorkflowState.objects.get(
                    workflow=workflow_def, 
                    name=workflow_def.initial_state
                )
                
                return DocumentWorkflow.objects.create(
                    content_type=content_type,
                    object_id=self.pk,
                    workflow_definition=workflow_def,
                    current_state=initial_state
                )
            except (WorkflowDefinition.DoesNotExist, WorkflowState.DoesNotExist):
                # Workflow not configured yet
                return None
    
    def needs_approval(self):
        """Check if this purchase order needs approval based on amount"""
        workflow = self.get_workflow_instance()
        if not workflow or not workflow.workflow_definition.requires_approval:
            return False
        
        threshold = workflow.workflow_definition.approval_threshold_amount
        if threshold and self.grand_total.amount >= threshold.amount:
            return True
        
        return False
    
    def can_reactivate(self):
        """Check if this purchase order can be reactivated"""
        return self.doc_status in ['complete', 'closed']
    
    def reactivate(self, user=None):
        """
        Reactivate a completed or closed purchase order.
        Changes status back to 'in_progress' and resets workflow if applicable.
        """
        if not self.can_reactivate():
            raise ValueError(f"Cannot reactivate purchase order with status '{self.doc_status}'")
        
        # Store original status for logging
        original_status = self.doc_status
        
        # Change status back to in_progress
        self.doc_status = 'in_progress'
        
        # Reset workflow state if workflow exists
        workflow_instance = self.get_workflow_instance()
        if workflow_instance and workflow_instance.workflow_definition:
            try:
                from core.models import WorkflowState
                in_progress_state = WorkflowState.objects.get(
                    workflow=workflow_instance.workflow_definition,
                    name='in_progress'
                )
                workflow_instance.current_state = in_progress_state
                workflow_instance.save()
            except WorkflowState.DoesNotExist:
                # If no in_progress state, try to find initial state
                try:
                    initial_state = WorkflowState.objects.get(
                        workflow=workflow_instance.workflow_definition,
                        name=workflow_instance.workflow_definition.initial_state
                    )
                    workflow_instance.current_state = initial_state
                    workflow_instance.save()
                except WorkflowState.DoesNotExist:
                    pass  # No workflow states available
        
        # Clear some completion-related fields if needed
        if original_status == 'complete':
            self.date_received = None
        
        # Update audit fields
        if user:
            self.updated_by = user
        
        # Save the changes
        self.save()
        
        return f"Purchase order {self.document_no} reactivated from '{original_status}' to 'in_progress'"
    
    def calculate_totals(self):
        """Calculate and update order totals from line items"""
        from djmoney.money import Money
        
        total_lines_amount = 0
        for line in self.lines.all():
            if line.line_net_amount:
                total_lines_amount += line.line_net_amount.amount
        
        self.total_lines = Money(total_lines_amount, 'USD')
        self.grand_total = self.total_lines  # For now, same as total_lines (no tax)
        self.save()
        
        return self.grand_total


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
    
    def save(self, *args, **kwargs):
        """Auto-calculate line_net_amount before saving"""
        if self.quantity_ordered and self.price_entered:
            from djmoney.money import Money
            self.line_net_amount = Money(
                float(self.quantity_ordered) * float(self.price_entered.amount),
                self.price_entered.currency
            )
        super().save(*args, **kwargs)
        
        # Recalculate order totals after saving the line
        if self.order:
            self.order.calculate_totals()


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
