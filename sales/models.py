"""
Sales models for Modern ERP system.
Sales orders, invoices, shipments, and related documents.
Based on iDempiere's C_Order, C_Invoice, M_InOut, etc.
"""

from django.db import models
from django.core.validators import MinValueValidator
from djmoney.models.fields import MoneyField
from decimal import Decimal
from core.models import BaseModel, Organization, BusinessPartner, NumberSequence, Opportunity, PaymentTerms, Incoterms, Contact, BusinessPartnerLocation
from inventory.models import Product, Warehouse, PriceList


class SalesOrderLineManager(models.Manager):
    """Custom manager for SalesOrderLine to ensure price_actual is always set"""
    
    def create(self, **kwargs):
        from djmoney.money import Money
        
        print(f"🔍 SalesOrderLineManager.create called with kwargs: {kwargs}")
        
        # Ensure price_actual is set
        if 'price_actual' not in kwargs and 'price_entered' in kwargs:
            kwargs['price_actual'] = kwargs['price_entered']
            print(f"🔍 Manager auto-set price_actual from price_entered: {kwargs['price_actual']}")
        elif 'price_actual' not in kwargs:
            kwargs['price_actual'] = Money(0, 'USD')
            print(f"🔍 Manager auto-set price_actual to 0")
            
        # Ensure price_list is set
        if 'price_list' not in kwargs:
            kwargs['price_list'] = kwargs.get('price_entered', Money(0, 'USD'))
            print(f"🔍 Manager auto-set price_list: {kwargs['price_list']}")
            
        return super().create(**kwargs)


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
    
    # Business partner and contact information
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT, limit_choices_to={'is_customer': True})
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, 
                               help_text="Customer contact for this order")
    internal_user = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='sales_orders_as_internal_contact',
                                     help_text="Our company contact handling this order")
    
    # Address information
    business_partner_location = models.ForeignKey(BusinessPartnerLocation, on_delete=models.SET_NULL, 
                                                 null=True, blank=True, 
                                                 help_text="Primary address for this order")
    bill_to_location = models.ForeignKey(BusinessPartnerLocation, on_delete=models.SET_NULL, 
                                        null=True, blank=True, related_name='sales_orders_bill_to',
                                        help_text="Billing address")
    ship_to_location = models.ForeignKey(BusinessPartnerLocation, on_delete=models.SET_NULL, 
                                        null=True, blank=True, related_name='sales_orders_ship_to',
                                        help_text="Shipping address")
    
    # Legacy address fields (for backward compatibility)
    bill_to_address = models.TextField(blank=True, help_text="Legacy billing address text")
    ship_to_address = models.TextField(blank=True, help_text="Legacy shipping address text")
    
    # Opportunity tracking
    opportunity = models.ForeignKey(Opportunity, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='sales_orders', help_text="Related opportunity (Q #XXXXXX)")
    
    # Transaction tracking
    transaction_id = models.CharField(
        max_length=32, 
        blank=True, 
        null=True,
        unique=True,
        help_text="32-character transaction code for remote payment system"
    )
    
    # Pricing and terms
    price_list = models.ForeignKey(PriceList, on_delete=models.PROTECT, limit_choices_to={'is_sales_price_list': True})
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
    
    # Sales rep
    sales_rep = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Flags
    is_printed = models.BooleanField(default=False)
    is_delivered = models.BooleanField(default=False)
    is_invoiced = models.BooleanField(default=False)
    is_drop_ship = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date_ordered', 'document_no']
        
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

    def __str__(self):
        # Add SO- prefix for display
        doc_display = f"SO-{self.document_no}" if self.document_no.isdigit() else self.document_no
        return f"{doc_display} - {self.business_partner.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate document number if not provided
        if not self.document_no:
            self.document_no = self._generate_document_number()
        super().save(*args, **kwargs)
    
    def _generate_document_number(self):
        """Generate next sales order number (numeric only)"""
        import re
        
        # Find the highest numeric document number
        max_num = 0
        
        # Get all document numbers
        for doc_no in SalesOrder.objects.all().values_list('document_no', flat=True):
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
    
    @property
    def payment_url(self):
        """Generate PayPal payment URL if transaction ID exists"""
        if self.transaction_id:
            return f"https://www.malla-group.com/toolbox/paypal-payment-gateway?transaction={self.transaction_id}"
        return None
    
    def get_workflow_instance(self):
        """Get or create workflow instance for this sales order"""
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
                workflow_def = WorkflowDefinition.objects.get(document_type='sales_order')
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
        """Check if this order needs approval based on amount"""
        workflow = self.get_workflow_instance()
        if not workflow or not workflow.workflow_definition.requires_approval:
            return False
        
        threshold = workflow.workflow_definition.approval_threshold_amount
        if threshold and self.grand_total.amount >= threshold.amount:
            return True
        
        return False
    
    def can_reactivate(self):
        """Check if this sales order can be reactivated"""
        return self.doc_status in ['complete', 'closed']
    
    def reactivate(self, user=None):
        """
        Reactivate a completed or closed sales order.
        Changes status back to 'in_progress' and resets workflow if applicable.
        """
        if not self.can_reactivate():
            raise ValueError(f"Cannot reactivate sales order with status '{self.doc_status}'")
        
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
            self.date_delivered = None
        
        # Update audit fields
        if user:
            self.updated_by = user
        
        # Save the changes
        self.save()
        
        return f"Sales order {self.document_no} reactivated from '{original_status}' to 'in_progress'"


class SalesOrderLine(BaseModel):
    """
    Sales Order line item.
    Based on iDempiere's C_OrderLine.
    """
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='lines')
    
    # Custom manager
    objects = SalesOrderLineManager()
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
    price_actual = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
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
        
    def save(self, *args, **kwargs):
        """Override save to ensure price_actual is always set"""
        from djmoney.money import Money
        
        print(f"🔍 SalesOrderLine.save() called for line_no={getattr(self, 'line_no', 'NEW')}")
        print(f"🔍 Before save - price_entered: {self.price_entered}, price_actual: {self.price_actual}")
        
        # If price_actual is not set but price_entered is, copy it
        if not self.price_actual and self.price_entered:
            self.price_actual = self.price_entered
            print(f"🔍 Copied price_entered to price_actual: {self.price_actual}")
        # If neither is set, set both to 0
        elif not self.price_actual and not self.price_entered:
            self.price_actual = Money(0, 'USD')
            self.price_entered = Money(0, 'USD')
            print(f"🔍 Set both prices to 0")
        # If only price_actual is missing, set it to 0
        elif not self.price_actual:
            self.price_actual = Money(0, 'USD')
            print(f"🔍 Set price_actual to 0")
            
        # Ensure price_list is set
        if not self.price_list:
            self.price_list = self.price_entered if self.price_entered else Money(0, 'USD')
            
        print(f"🔍 After save fixes - price_entered: {self.price_entered}, price_actual: {self.price_actual}")
        super().save(*args, **kwargs)
        print(f"🔍 SalesOrderLine.save() completed successfully")
        
        # Recalculate order totals after saving the line
        if self.order:
            self.order.calculate_totals()
            print(f"🔍 Recalculated order totals: {self.order.grand_total}")
        
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
    
    # Business partner and contact information
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT, limit_choices_to={'is_customer': True})
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True,
                               help_text="Customer contact for this invoice")
    internal_user = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='invoices_as_internal_contact',
                                     help_text="Our company contact handling this invoice")
    
    # Address information  
    business_partner_location = models.ForeignKey(BusinessPartnerLocation, on_delete=models.SET_NULL,
                                                 null=True, blank=True,
                                                 help_text="Primary address for this invoice")
    bill_to_location = models.ForeignKey(BusinessPartnerLocation, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='invoices_bill_to',
                                        help_text="Billing address")
    
    # Legacy address field (for backward compatibility)
    bill_to_address = models.TextField(blank=True, help_text="Legacy billing address text")
    
    # Reference to sales order
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Opportunity tracking
    opportunity = models.ForeignKey(Opportunity, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='invoices', help_text="Related opportunity (Q #XXXXXX)")
    
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
        # Add INV- prefix for display
        doc_display = f"INV-{self.document_no}" if self.document_no.isdigit() else self.document_no
        return f"{doc_display} - {self.business_partner.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate document number if not provided
        if not self.document_no:
            self.document_no = self._generate_document_number()
        super().save(*args, **kwargs)
    
    def _generate_document_number(self):
        """Generate next invoice number (numeric only)"""
        import re
        
        # Find the highest numeric document number
        max_num = 0
        
        # Get all document numbers
        for doc_no in Invoice.objects.all().values_list('document_no', flat=True):
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
    
    def get_workflow_instance(self):
        """Get or create workflow instance for this invoice"""
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
                workflow_def = WorkflowDefinition.objects.get(document_type='invoice')
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
        """Check if this invoice needs approval based on amount"""
        workflow = self.get_workflow_instance()
        if not workflow or not workflow.workflow_definition.requires_approval:
            return False
        
        threshold = workflow.workflow_definition.approval_threshold_amount
        if threshold and self.grand_total.amount >= threshold:
            return True
        
        return False
    
    def can_reactivate(self):
        """Check if this invoice can be reactivated"""
        return self.doc_status in ['paid', 'closed']
    
    def reactivate(self, user=None):
        """
        Reactivate a paid or closed invoice.
        Changes status back to 'sent' and resets workflow if applicable.
        """
        if not self.can_reactivate():
            raise ValueError(f"Cannot reactivate invoice with status '{self.doc_status}'")
        
        # Store original status for logging
        original_status = self.doc_status
        
        # Change status back to sent
        self.doc_status = 'sent'
        
        # Reset workflow state if workflow exists
        workflow_instance = self.get_workflow_instance()
        if workflow_instance and workflow_instance.workflow_definition:
            try:
                from core.models import WorkflowState
                sent_state = WorkflowState.objects.get(
                    workflow=workflow_instance.workflow_definition,
                    name='sent'
                )
                workflow_instance.current_state = sent_state
                workflow_instance.save()
            except WorkflowState.DoesNotExist:
                # If no sent state, try to find approved state
                try:
                    approved_state = WorkflowState.objects.get(
                        workflow=workflow_instance.workflow_definition,
                        name='approved'
                    )
                    workflow_instance.current_state = approved_state
                    workflow_instance.save()
                except WorkflowState.DoesNotExist:
                    pass  # No workflow states available
        
        # Reset payment-related fields
        if original_status == 'paid':
            self.paid_amount = 0
            self.open_amount = self.grand_total
        
        # Update audit fields
        if user:
            self.updated_by = user
        
        # Save the changes
        self.save()
        
        return f"Invoice {self.document_no} reactivated from '{original_status}' to 'sent'"


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
    
    # Business partner, contact, and warehouse
    business_partner = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT)
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True,
                               help_text="Customer contact for this shipment")
    internal_user = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='shipments_as_internal_contact',
                                     help_text="Our company contact handling this shipment")
    
    # Address information
    business_partner_location = models.ForeignKey(BusinessPartnerLocation, on_delete=models.SET_NULL,
                                                 null=True, blank=True,
                                                 help_text="Ship-to address")
    
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    
    # Reference to sales order
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Opportunity tracking
    opportunity = models.ForeignKey(Opportunity, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='shipments', help_text="Related opportunity (Q #XXXXXX)")
    
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
        # Add SH- prefix for display
        doc_display = f"SH-{self.document_no}" if self.document_no.isdigit() else self.document_no
        return f"{doc_display} - {self.business_partner.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate document number if not provided
        if not self.document_no:
            self.document_no = self._generate_document_number()
        super().save(*args, **kwargs)
    
    def _generate_document_number(self):
        """Generate next shipment number (numeric only)"""
        import re
        
        # Find the highest numeric document number
        max_num = 0
        
        # Get all document numbers
        for doc_no in Shipment.objects.all().values_list('document_no', flat=True):
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
        
        # Return the next number - start from 1 if no shipments exist
        return str(max_num + 1) if max_num > 0 else "1"
    
    def get_workflow_instance(self):
        """Get or create workflow instance for this shipment"""
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
                workflow_def = WorkflowDefinition.objects.get(document_type='shipment')
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
        """Check if this shipment needs approval - shipments generally don't need approval"""
        return False
    
    def can_reactivate(self):
        """Check if this shipment can be reactivated"""
        return self.doc_status in ['complete', 'closed']
    
    def reactivate(self, user=None):
        """
        Reactivate a completed or closed shipment.
        Changes status back to 'in_progress' and resets workflow if applicable.
        """
        if not self.can_reactivate():
            raise ValueError(f"Cannot reactivate shipment with status '{self.doc_status}'")
        
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
        
        # Reset tracking information if needed
        if original_status == 'complete':
            self.date_received = None
            self.is_in_transit = True
        
        # Update audit fields
        if user:
            self.updated_by = user
        
        # Save the changes
        self.save()
        
        return f"Shipment {self.document_no} reactivated from '{original_status}' to 'in_progress'"


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


