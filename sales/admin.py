"""
Django admin configuration for sales models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django import forms
from django.http import JsonResponse
from django.contrib import messages
from . import models
from core.models import Contact
from .transaction_sync import create_remote_transaction
from .invoice_utils import create_invoice_from_sales_order


class DocumentContactForm(forms.ModelForm):
    """Custom form for documents with contact and location filtering based on business partner"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If we have an instance with a business partner, filter the contacts and locations
        if hasattr(self.instance, 'business_partner') and self.instance.business_partner:
            # Filter contacts (only if field is editable)
            try:
                if 'contact' in self.fields:
                    self.fields['contact'].queryset = Contact.objects.filter(
                        business_partner=self.instance.business_partner
                    )
                    self.fields['contact'].help_text = f"Contacts for {self.instance.business_partner.name}"
            except (KeyError, AttributeError):
                pass  # Field might not be available due to readonly status
            
            # Filter locations for bill_to and ship_to
            from core.models import BusinessPartnerLocation
            locations = BusinessPartnerLocation.objects.filter(
                business_partner=self.instance.business_partner
            )
            
            if 'business_partner_location' in self.fields:
                self.fields['business_partner_location'].queryset = locations
                self.fields['business_partner_location'].help_text = f"Addresses for {self.instance.business_partner.name}"
            
            if 'bill_to_location' in self.fields:
                self.fields['bill_to_location'].queryset = locations
                self.fields['bill_to_location'].help_text = f"Billing addresses for {self.instance.business_partner.name}"
            
            if 'ship_to_location' in self.fields:
                self.fields['ship_to_location'].queryset = locations
                self.fields['ship_to_location'].help_text = f"Shipping addresses for {self.instance.business_partner.name}"
                
        else:
            # No business partner selected, clear all dependent fields
            try:
                if 'contact' in self.fields:
                    self.fields['contact'].queryset = Contact.objects.none()
                    self.fields['contact'].help_text = "Save with a business partner first to see available contacts"
            except (KeyError, AttributeError):
                pass  # Field might not be available due to readonly status
            
            from core.models import BusinessPartnerLocation
            
            if 'business_partner_location' in self.fields:
                self.fields['business_partner_location'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['business_partner_location'].help_text = "Save with a business partner first to see available addresses"
            
            if 'bill_to_location' in self.fields:
                self.fields['bill_to_location'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['bill_to_location'].help_text = "Save with a business partner first to see available addresses"
            
            if 'ship_to_location' in self.fields:
                self.fields['ship_to_location'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['ship_to_location'].help_text = "Save with a business partner first to see available addresses"


class SalesOrderLineInline(admin.TabularInline):
    model = models.SalesOrderLine
    extra = 0  # No empty fields
    fields = ('line_link', 'product_display', 'quantity_display', 'price_display', 'line_total_display')
    readonly_fields = ('line_link', 'product_display', 'quantity_display', 'price_display', 'line_total_display')
    can_delete = True
    show_change_link = False  # We'll use our custom link
    verbose_name = "Order Line"
    verbose_name_plural = "Sales Order Lines"
    template = 'admin/sales/salesorderline_inline.html'  # Custom template
    
    def has_add_permission(self, request, obj=None):
        """Disable adding through inline - use the add button instead"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable changing through inline - use the edit link instead"""
        return False
    
    def line_link(self, obj):
        """Display line number as link to edit page"""
        if obj.pk:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:sales_salesorderline_change', args=[obj.pk])
            return format_html('<a href="{}" target="_blank"><strong>Line {}</strong></a>', url, obj.line_no)
        return f'Line {obj.line_no}'
    line_link.short_description = 'Line #'
    
    def product_display(self, obj):
        """Display product with name and part number"""
        if obj.product:
            return f"{obj.product.name}\n{obj.product.manufacturer_part_number or 'N/A'}"
        elif obj.charge:
            return f"⚡ {obj.charge.name}"
        return obj.description or '-'
    product_display.short_description = 'Product / Charge'
    
    def quantity_display(self, obj):
        """Display quantity ordered"""
        return f"{obj.quantity_ordered}"
    quantity_display.short_description = 'Qty'
    
    def price_display(self, obj):
        """Display unit price"""
        if obj.price_entered:
            return f"${obj.price_entered.amount:,.2f}"
        return '-'
    price_display.short_description = 'Unit Price'
    
    def line_total_display(self, obj):
        """Display line total"""
        if obj.line_net_amount:
            return f"${obj.line_net_amount.amount:,.2f}"
        return '-'
    line_total_display.short_description = 'Line Total'
    
    def get_readonly_fields(self, request, obj=None):
        """All fields are readonly - editing happens through popup"""
        return self.readonly_fields
    
    class Media:
        css = {
            'all': ('admin/css/custom_inline.css',)
        }


class SalesOrderForm(DocumentContactForm):
    class Meta:
        model = models.SalesOrder
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Additional safety check for readonly fields
        # This ensures form works even if fields become readonly
        if hasattr(self, 'instance') and self.instance and self.instance.pk:
            try:
                workflow = self.instance.get_workflow_instance()
                if workflow:
                    current_state = workflow.current_state.name
                    locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
                    
                    if current_state in locked_states:
                        # For locked documents, make sure contact filtering still works
                        # even if some fields might be removed from the form
                        pass  # The parent class already handles this safely
            except:
                pass  # Don't break if workflow check fails


class InvoiceForm(DocumentContactForm):
    class Meta:
        model = models.Invoice
        fields = '__all__'


class ShipmentForm(DocumentContactForm):
    class Meta:
        model = models.Shipment
        fields = '__all__'


@admin.register(models.SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    form = SalesOrderForm
    list_display = ('document_no_display', 'opportunity', 'business_partner', 'date_ordered', 'workflow_state_display', 'grand_total', 'is_delivered', 'is_invoiced', 'lock_status', 'print_order')
    list_filter = ('doc_status', 'opportunity', 'organization', 'warehouse', 'is_delivered', 'is_invoiced', 'is_drop_ship')
    readonly_fields = ('business_partner_address_display', 'bill_to_address_display', 'ship_to_address_display', 'transaction_id', 'transaction_actions')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description')
    date_hierarchy = 'date_ordered'
    inlines = [SalesOrderLineInline]
    actions = ['create_combined_invoice', 'reactivate_sales_orders']
    autocomplete_fields = ['opportunity', 'business_partner']
    
    def document_no_display(self, obj):
        """Display document number with SO- prefix"""
        if obj.document_no and obj.document_no.isdigit():
            return f"SO-{obj.document_no}"
        return obj.document_no
    document_no_display.short_description = 'Document No'
    document_no_display.admin_order_field = 'document_no'
    
    def print_order(self, obj):
        """Add print button in list view"""
        url = reverse('sales:order_pdf', args=[obj.id])
        return format_html('<a class="button" href="{}" target="_blank">Print PDF</a>', url)
    print_order.short_description = 'Print'
    print_order.allow_tags = True
    
    fieldsets = (
        ('Document Number', {
            'fields': (
                'document_no',
            ),
            'classes': ('wide',),
            'description': 'Document number is auto-generated when the sales order is saved'
        }),
        ('Order Header', {
            'fields': (
                ('business_partner', 'opportunity'),
                ('date_ordered', 'date_promised'),
                ('customer_po_reference',),
                ('payment_terms', 'incoterms'),
                ('incoterms_location',),
            ),
            'classes': ('wide',)
        }),
        ('Contact Information', {
            'fields': (
                ('internal_user', 'contact'),
            ),
            'classes': ('wide',),
            'description': 'Internal User: Our company contact | Contact: Customer contact (save document first to see filtered options)'
        }),
        ('Address Information', {
            'fields': (
                ('business_partner_location', 'business_partner_address_display'),
                ('bill_to_location', 'bill_to_address_display'),
                ('ship_to_location', 'ship_to_address_display'),
            ),
            'classes': ('wide',),
            'description': 'All addresses filtered by business partner (save document first to see available addresses)'
        }),
        ('Document Information', {
            'fields': (
                ('organization', 'doc_status'),
                ('description',),
            ),
            'classes': ('wide',)
        }),
        ('Pricing', {
            'fields': (
                ('price_list', 'currency'),
                ('warehouse',),
                ('total_lines', 'grand_total'),
            ),
            'classes': ('wide',)
        }),
        ('Delivery Information', {
            'fields': (
                ('estimated_delivery_weeks',),
            ),
            'classes': ('wide',)
        }),
        ('Payment Transaction', {
            'fields': (
                ('transaction_id', 'transaction_actions'),
                ('payment_url_display',),
            ),
            'classes': ('wide',),
            'description': 'Remote payment system transaction tracking'
        }),
        ('Invoice Management', {
            'fields': (
                ('invoice_actions',),
            ),
            'classes': ('wide',),
            'description': 'Create invoices from this sales order'
        }),
        ('Workflow & Approval', {
            'fields': (
                ('current_workflow_state', 'workflow_actions'),
                ('approval_status_display',),
            ),
            'classes': ('wide',),
            'description': 'Document workflow and approval management'
        }),
    )
    readonly_fields = ('document_no', 'total_lines', 'grand_total', 'business_partner_address_display', 'bill_to_address_display', 'ship_to_address_display', 'transaction_id', 'transaction_actions', 'payment_url_display', 'invoice_actions', 'current_workflow_state', 'workflow_actions', 'approval_status_display')
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make fields readonly based on workflow state.
        Once submitted for approval, most fields should be locked.
        """
        readonly_fields = list(super().get_readonly_fields(request, obj))
        
        if obj and obj.pk:
            workflow = obj.get_workflow_instance()
            if workflow:
                current_state = workflow.current_state.name
                
                # Lock fields for submitted orders (except draft and rejected)
                locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
                
                if current_state in locked_states:
                    # Core order fields that should be locked
                    locked_fields = [
                        'business_partner', 'opportunity', 'date_ordered', 'date_promised',
                        'customer_po_reference', 'payment_terms', 'incoterms', 
                        'incoterms_location', 'contact', 'internal_user',
                        'business_partner_location', 'bill_to_location', 'ship_to_location',
                        'organization', 'description', 'doc_status',
                        'currency', 'warehouse', 'estimated_delivery_weeks'
                    ]
                    
                    # Add locked fields to readonly_fields if not already there
                    for field in locked_fields:
                        if field not in readonly_fields:
                            readonly_fields.append(field)
                    
                    # For completely locked states (complete, closed), lock everything
                    if current_state in ['complete', 'closed']:
                        # Get all model fields except the workflow-related ones
                        all_fields = [f.name for f in obj._meta.fields if f.name not in [
                            'id', 'created', 'updated', 'created_by', 'updated_by', 
                            'is_active', 'legacy_id'
                        ]]
                        
                        for field in all_fields:
                            if field not in readonly_fields:
                                readonly_fields.append(field)
        
        return readonly_fields
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Add workflow lock message to change view"""
        extra_context = extra_context or {}
        
        try:
            obj = self.get_object(request, object_id)
            if obj:
                workflow = obj.get_workflow_instance()
                if workflow:
                    current_state = workflow.current_state.name
                    locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
                    
                    if current_state in locked_states:
                        from django.contrib import messages
                        state_messages = {
                            'pending_approval': 'This order is pending approval and cannot be modified.',
                            'approved': 'This order has been approved and most fields are locked.',
                            'in_progress': 'This order is in progress and fields are locked.',
                            'complete': 'This order is complete and all fields are locked.',
                            'closed': 'This order is closed and all fields are locked.'
                        }
                        
                        message = state_messages.get(current_state, 'This order is locked from editing.')
                        messages.warning(request, f"🔒 {message}")
        except:
            pass  # Don't break if something goes wrong
        
        return super().change_view(request, object_id, form_url, extra_context)
    
    def workflow_state_display(self, obj):
        """Display workflow state in list view"""
        workflow = obj.get_workflow_instance()
        if not workflow:
            return 'No workflow'
        
        state_colors = {
            'draft': '#6c757d',
            'pending_approval': '#fd7e14',
            'approved': '#20c997',
            'in_progress': '#0d6efd',
            'complete': '#198754',
            'rejected': '#dc3545',
            'closed': '#495057'
        }
        
        color = state_colors.get(workflow.current_state.name, '#6c757d')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, workflow.current_state.display_name
        )
    workflow_state_display.short_description = 'Workflow State'
    
    def lock_status(self, obj):
        """Display lock status in list view"""
        workflow = obj.get_workflow_instance()
        if not workflow:
            return ''
        
        locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
        
        if workflow.current_state.name in locked_states:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold; font-size: 14px;" title="Document is locked from editing">🔒</span>'
            )
        return format_html(
            '<span style="color: #198754; font-weight: bold; font-size: 14px;" title="Document is editable">✏️</span>'
        )
    lock_status.short_description = 'Lock'
    
    def transaction_actions(self, obj):
        """Display transaction action buttons"""
        if obj.pk:
            if not obj.transaction_id:
                url = reverse('admin:sales_salesorder_create_transaction', args=[obj.pk])
                return format_html(
                    '<a class="button" href="#" onclick="createTransaction(\'{}\'); return false;">Create Transaction</a>'
                    '<script>'
                    'function createTransaction(url) {{'
                    '    fetch(url).then(response => response.json()).then(data => {{'
                    '        if (data.success) {{'
                    '            alert("Transaction created successfully!\\n\\nTransaction ID: " + data.transaction_id + "\\n\\nPayment URL: " + data.payment_url);'
                    '            location.reload();'
                    '        }} else {{'
                    '            alert("Error: " + data.error);'
                    '        }}'
                    '    }});'
                    '}}'
                    '</script>',
                    url
                )
            else:
                return format_html(
                    '<span style="color: green;">✓ Transaction created</span><br>'
                    '<small>ID: {}</small><br>'
                    '<a href="{}" target="_blank" class="button" style="margin-top: 5px;">Payment Link</a>',
                    obj.transaction_id,
                    obj.payment_url
                )
        return '-'
    transaction_actions.short_description = 'Transaction Actions'
    
    def payment_url_display(self, obj):
        """Display payment URL if transaction exists"""
        if obj.payment_url:
            return format_html(
                '<a href="{}" target="_blank" style="color: #0073aa; text-decoration: none;">{}</a>',
                obj.payment_url,
                obj.payment_url
            )
        return '-'
    payment_url_display.short_description = 'Payment URL'
    
    def invoice_actions(self, obj):
        """Display invoice creation actions"""
        if not obj.pk:
            return '-'
        
        # Check if invoice already exists
        existing_invoice = models.Invoice.objects.filter(sales_order=obj).first()
        if existing_invoice:
            invoice_url = reverse('admin:sales_invoice_change', args=[existing_invoice.pk])
            return format_html(
                '<a href="{}" style="color: green; font-weight: bold;">View Invoice: {}</a>',
                invoice_url,
                existing_invoice.document_no
            )
        
        # Show create invoice button
        create_url = reverse('admin:sales_salesorder_create_invoice', args=[obj.pk])
        return format_html(
            '<a href="{}" style="background-color: #007cba; color: white; padding: 8px 16px; '
            'text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">'
            'Create Invoice</a>',
            create_url
        )
    invoice_actions.short_description = 'Invoice Actions'
    
    def current_workflow_state(self, obj):
        """Display current workflow state with visual indicator"""
        if not obj.pk:
            return '-'
        
        workflow = obj.get_workflow_instance()
        if not workflow:
            return 'No workflow configured'
        
        state_colors = {
            'draft': '#6c757d',           # Gray
            'pending_approval': '#fd7e14', # Orange  
            'approved': '#20c997',        # Teal
            'in_progress': '#0d6efd',     # Blue
            'complete': '#198754',        # Green
            'rejected': '#dc3545',        # Red
            'closed': '#495057'           # Dark gray
        }
        
        color = state_colors.get(workflow.current_state.name, '#6c757d')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            color, workflow.current_state.display_name
        )
    current_workflow_state.short_description = 'Workflow State'
    
    def workflow_actions(self, obj):
        """Display workflow action buttons based on current state and permissions"""
        if not obj.pk:
            return '-'
        
        workflow = obj.get_workflow_instance()
        if not workflow:
            return 'No workflow configured'
        
        # For display purposes, we'll show all possible actions
        # The actual permission check happens when the action is executed
        current_user = None  # We'll check permissions during action execution
        
        buttons = []
        current_state = workflow.current_state.name
        
        # State-specific buttons (permission checks happen during execution)
        if current_state == 'draft':
            if obj.needs_approval():
                buttons.append(self._create_workflow_button(
                    'Submit for Approval', 'submit_approval', obj.pk, 'orange'
                ))
            else:
                # Auto-approve under $1000
                buttons.append(self._create_workflow_button(
                    'Approve & Start', 'auto_approve', obj.pk, 'green'
                ))
        
        elif current_state == 'pending_approval':
            buttons.append(self._create_workflow_button(
                'Approve', 'approve', obj.pk, 'green'
            ))
            buttons.append(self._create_workflow_button(
                'Reject', 'reject', obj.pk, 'red'
            ))
        
        elif current_state == 'approved':
            buttons.append(self._create_workflow_button(
                'Start Processing', 'start_progress', obj.pk, 'blue'
            ))
            # Add reactivate button for approved orders too
            buttons.append(self._create_workflow_button(
                'Reactivate', 'reactivate', obj.pk, 'orange'
            ))
        
        elif current_state == 'in_progress':
            buttons.append(self._create_workflow_button(
                'Mark Complete', 'complete', obj.pk, 'green'
            ))
            # Add reactivate button for in_progress orders too
            buttons.append(self._create_workflow_button(
                'Reactivate', 'reactivate', obj.pk, 'orange'
            ))
        
        elif current_state == 'complete':
            buttons.append(self._create_workflow_button(
                'Reactivate', 'reactivate', obj.pk, 'orange'
            ))
            buttons.append(self._create_workflow_button(
                'Close', 'close', obj.pk, 'gray'
            ))
        
        elif current_state == 'closed':
            buttons.append(self._create_workflow_button(
                'Reactivate', 'reactivate', obj.pk, 'orange'
            ))
        
        elif current_state == 'rejected':
            buttons.append(self._create_workflow_button(
                'Return to Draft', 'return_draft', obj.pk, 'blue'
            ))
        
        if buttons:
            return format_html(' '.join(buttons))
        return 'No actions available'
    
    workflow_actions.short_description = 'Workflow Actions'
    
    def _create_workflow_button(self, label, action, obj_id, color):
        """Create a workflow action button as a simple link"""
        color_codes = {
            'blue': '#0d6efd',
            'green': '#198754', 
            'orange': '#fd7e14',
            'red': '#dc3545',
            'gray': '#6c757d'
        }
        
        url = reverse('admin:sales_salesorder_workflow_action', args=[obj_id])
        
        return format_html(
            '<a href="{}?action={}" class="button" style="background-color: {}; color: white; margin-right: 5px; padding: 4px 8px; border-radius: 3px; text-decoration: none; display: inline-block;">{}</a>',
            url, action, color_codes.get(color, '#6c757d'), label
        )
    
    def approval_status_display(self, obj):
        """Show approval status and pending approvals"""
        workflow = obj.get_workflow_instance()
        if not workflow:
            return '-'
        
        from core.models import WorkflowApproval
        
        if workflow.current_state.name == 'pending_approval':
            pending = WorkflowApproval.objects.filter(
                document_workflow=workflow, status='pending'
            ).first()
            
            if pending:
                return format_html(
                    '<div style="color: #fd7e14;">'
                    '<strong>⏳ Pending Approval</strong><br>'
                    'Submitted: {}<br>'
                    'Amount: ${:,.2f}'
                    '</div>',
                    pending.requested_at.strftime('%m/%d/%Y %I:%M %p'),
                    obj.grand_total.amount
                )
        
        elif workflow.current_state.name == 'approved':
            approval = WorkflowApproval.objects.filter(
                document_workflow=workflow, status='approved'
            ).first()
            
            if approval:
                return format_html(
                    '<div style="color: #198754;">'
                    '<strong>✅ Approved</strong><br>'
                    'By: {}<br>'
                    'Date: {}'
                    '</div>',
                    approval.approver.get_full_name() if approval.approver else 'System',
                    approval.responded_at.strftime('%m/%d/%Y %I:%M %p') if approval.responded_at else 'N/A'
                )
        
        return '-'
    approval_status_display.short_description = 'Approval Status'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<uuid:salesorder_id>/create-transaction/', 
                 self.admin_site.admin_view(self.create_transaction_view), 
                 name='sales_salesorder_create_transaction'),
            path('<uuid:object_id>/workflow-action/', 
                 self.admin_site.admin_view(self.workflow_action_view), 
                 name='sales_salesorder_workflow_action'),
            path('<uuid:salesorder_id>/create-invoice/', 
                 self.admin_site.admin_view(self.create_invoice_view), 
                 name='sales_salesorder_create_invoice'),
        ]
        return custom_urls + urls
    
    def create_transaction_view(self, request, salesorder_id):
        """Handle AJAX request to create transaction"""
        try:
            sales_order = models.SalesOrder.objects.get(pk=salesorder_id)
            result = create_remote_transaction(sales_order)
            return JsonResponse(result)
        except models.SalesOrder.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Sales order not found'
            })
    
    def create_invoice_view(self, request, salesorder_id):
        """Handle invoice creation from sales order"""
        from django.shortcuts import redirect
        from django.contrib import messages
        
        try:
            sales_order = models.SalesOrder.objects.get(pk=salesorder_id)
            
            # Create invoice using the utility function
            result = create_invoice_from_sales_order(sales_order, user=request.user)
            
            if result['success']:
                messages.success(request, result['message'])
                # Redirect to the created invoice
                return redirect('admin:sales_invoice_change', result['invoice'].pk)
            else:
                messages.error(request, result['error'])
                # If there's an existing invoice, redirect to it
                if 'existing_invoice' in result:
                    return redirect('admin:sales_invoice_change', result['existing_invoice'].pk)
                
        except models.SalesOrder.DoesNotExist:
            messages.error(request, 'Sales order not found')
        except Exception as e:
            messages.error(request, f'Error creating invoice: {str(e)}')
        
        # Redirect back to sales order on any error
        return redirect('admin:sales_salesorder_change', salesorder_id)
    
    def workflow_action_view(self, request, object_id):
        """Handle workflow action requests"""
        from django.shortcuts import redirect
        from django.contrib import messages
        from core.models import WorkflowApproval, WorkflowState
        from django.utils import timezone
        
        try:
            obj = models.SalesOrder.objects.get(pk=object_id)
            
            # Get action from query parameter
            action = request.GET.get('action')
            if not action:
                messages.error(request, 'No action specified')
                return redirect('admin:sales_salesorder_change', object_id)
            
            workflow = obj.get_workflow_instance()
            if not workflow:
                messages.error(request, 'No workflow configured for this document')
                return redirect('admin:sales_salesorder_change', object_id)
            
            # Set current user for permission checking
            self.current_user = request.user
            
            # Execute workflow action
            result = self.execute_workflow_action(obj, workflow, action, request.user, '')
            
            if result['success']:
                messages.success(request, result['message'])
            else:
                messages.error(request, result['error'])
            
            # Redirect back to the sales order change page
            return redirect('admin:sales_salesorder_change', object_id)
            
        except models.SalesOrder.DoesNotExist:
            messages.error(request, 'Sales order not found')
            return redirect('admin:sales_salesorder_changelist')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('admin:sales_salesorder_change', object_id)
    
    def execute_workflow_action(self, obj, workflow, action, user, comments):
        """Execute the workflow action with business logic"""
        from core.models import WorkflowApproval, WorkflowState
        from django.utils import timezone
        
        current_state = workflow.current_state.name
        
        # Check user permissions
        def has_permission(perm_code):
            if user.is_superuser:
                return True
            return user.workflow_permissions.filter(
                permission_code=perm_code, is_active=True
            ).exists()
        
        try:
            if action == 'submit_approval':
                # Submit for approval
                if current_state != 'draft':
                    return {'success': False, 'error': 'Can only submit draft orders for approval'}
                
                if not obj.needs_approval():
                    return {'success': False, 'error': 'This order does not require approval'}
                
                # Create approval request
                approval = WorkflowApproval.objects.create(
                    document_workflow=workflow,
                    requested_by=user,
                    comments=comments,
                    amount_at_request=obj.grand_total
                )
                
                # Change state to pending approval
                pending_state = WorkflowState.objects.get(
                    workflow=workflow.workflow_definition, 
                    name='pending_approval'
                )
                workflow.current_state = pending_state
                workflow.save()
                
                return {
                    'success': True,
                    'message': f'Order submitted for approval. Amount: ${obj.grand_total.amount:,.2f}'
                }
            
            elif action == 'auto_approve':
                # Auto-approve orders under threshold
                if current_state != 'draft':
                    return {'success': False, 'error': 'Can only approve draft orders'}
                
                if obj.needs_approval():
                    return {'success': False, 'error': 'This order requires manual approval'}
                
                # Move directly to approved state
                approved_state = WorkflowState.objects.get(
                    workflow=workflow.workflow_definition, 
                    name='approved'
                )
                workflow.current_state = approved_state
                workflow.save()
                
                return {
                    'success': True,
                    'message': 'Order auto-approved (under threshold)'
                }
            
            elif action == 'approve':
                # Approve the document
                if not has_permission('approve_sales_orders'):
                    return {'success': False, 'error': 'Insufficient permissions to approve orders'}
                
                if current_state != 'pending_approval':
                    return {'success': False, 'error': 'Can only approve pending orders'}
                
                # Update approval record
                approval = WorkflowApproval.objects.filter(
                    document_workflow=workflow, status='pending'
                ).first()
                
                if approval:
                    approval.status = 'approved'
                    approval.approver = user
                    approval.responded_at = timezone.now()
                    approval.comments = comments
                    approval.save()
                
                # Change state to approved
                approved_state = WorkflowState.objects.get(
                    workflow=workflow.workflow_definition, 
                    name='approved'
                )
                workflow.current_state = approved_state
                workflow.save()
                
                return {
                    'success': True,
                    'message': 'Order approved successfully'
                }
            
            elif action == 'reject':
                # Reject the document
                if not has_permission('approve_sales_orders'):
                    return {'success': False, 'error': 'Insufficient permissions to reject orders'}
                
                if current_state != 'pending_approval':
                    return {'success': False, 'error': 'Can only reject pending orders'}
                
                # Update approval record
                approval = WorkflowApproval.objects.filter(
                    document_workflow=workflow, status='pending'
                ).first()
                
                if approval:
                    approval.status = 'rejected'
                    approval.approver = user
                    approval.responded_at = timezone.now()
                    approval.comments = comments
                    approval.save()
                
                # Change state back to draft
                draft_state = WorkflowState.objects.get(
                    workflow=workflow.workflow_definition, 
                    name='draft'
                )
                workflow.current_state = draft_state
                workflow.save()
                
                return {
                    'success': True,
                    'message': 'Order rejected and returned to draft'
                }
            
            elif action == 'start_progress':
                # Start processing
                if current_state != 'approved':
                    return {'success': False, 'error': 'Can only start processing approved orders'}
                
                progress_state = WorkflowState.objects.get(
                    workflow=workflow.workflow_definition, 
                    name='in_progress'
                )
                workflow.current_state = progress_state
                workflow.save()
                
                return {
                    'success': True,
                    'message': 'Order processing started'
                }
            
            elif action == 'complete':
                # Mark complete
                if current_state != 'in_progress':
                    return {'success': False, 'error': 'Can only complete in-progress orders'}
                
                complete_state = WorkflowState.objects.get(
                    workflow=workflow.workflow_definition, 
                    name='complete'
                )
                workflow.current_state = complete_state
                workflow.save()
                
                return {
                    'success': True,
                    'message': 'Order marked as complete'
                }
            
            elif action == 'close':
                # Close order
                if current_state != 'complete':
                    return {'success': False, 'error': 'Can only close completed orders'}
                
                closed_state = WorkflowState.objects.get(
                    workflow=workflow.workflow_definition, 
                    name='closed'
                )
                workflow.current_state = closed_state
                workflow.save()
                
                return {
                    'success': True,
                    'message': 'Order closed'
                }
            
            elif action == 'reactivate':
                # Reactivate order from various states
                if not has_permission('reactivate_documents'):
                    return {'success': False, 'error': 'Insufficient permissions to reactivate orders'}
                
                if current_state not in ['approved', 'in_progress', 'complete', 'closed']:
                    return {'success': False, 'error': 'Can only reactivate approved, in-progress, completed or closed orders'}
                
                # Determine target state based on current state
                if current_state in ['approved', 'in_progress']:
                    # From approved or in_progress, go back to draft for full editing
                    target_state = WorkflowState.objects.get(
                        workflow=workflow.workflow_definition, 
                        name='draft'
                    )
                else:
                    # From complete/closed, go to in_progress
                    target_state = WorkflowState.objects.get(
                        workflow=workflow.workflow_definition, 
                        name='in_progress'
                    )
                
                workflow.current_state = target_state
                workflow.save()
                
                # Add audit comment
                from core.models import WorkflowApproval
                WorkflowApproval.objects.create(
                    document_workflow=workflow,
                    requested_by=user,
                    approver=user,
                    status='approved',
                    comments=f'Order reactivated from {current_state} state by {user.get_full_name() or user.username}',
                    requested_at=timezone.now(),
                    responded_at=timezone.now()
                )
                
                target_state_name = 'draft' if current_state in ['approved', 'in_progress'] else 'in-progress'
                return {
                    'success': True,
                    'message': f'Order reactivated from {current_state} state and moved to {target_state_name}'
                }
            
            elif action == 'return_draft':
                # Return rejected order to draft
                if current_state != 'rejected':
                    return {'success': False, 'error': 'Can only return rejected orders to draft'}
                
                draft_state = WorkflowState.objects.get(
                    workflow=workflow.workflow_definition, 
                    name='draft'
                )
                workflow.current_state = draft_state
                workflow.save()
                
                return {
                    'success': True,
                    'message': 'Order returned to draft'
                }
            
            else:
                return {
                    'success': False,
                    'error': f'Unknown action: {action}'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'Error executing workflow action: {str(e)}'
            }
    
    def business_partner_address_display(self, obj):
        """Display business partner location with customer name"""
        if obj.business_partner_location:
            return obj.business_partner_location.full_address_with_name
        return "-"
    business_partner_address_display.short_description = "Primary Address"
    
    def bill_to_address_display(self, obj):
        """Display bill to location with customer name"""
        if obj.bill_to_location:
            return obj.bill_to_location.full_address_with_name
        return "-"
    bill_to_address_display.short_description = "Bill To Address"
    
    def ship_to_address_display(self, obj):
        """Display ship to location with customer name"""
        if obj.ship_to_location:
            return obj.ship_to_location.full_address_with_name
        return "-"
    ship_to_address_display.short_description = "Ship To Address"
    
    def create_combined_invoice(self, request, queryset):
        """Create a single invoice from multiple selected sales orders"""
        from django.shortcuts import redirect
        from django.contrib import messages
        from .invoice_utils import create_invoice_from_multiple_orders
        
        orders = list(queryset)
        if not orders:
            messages.error(request, 'No orders selected')
            return
        
        # Validate that all orders have the same customer
        first_customer = orders[0].business_partner
        for order in orders:
            if order.business_partner != first_customer:
                messages.error(request, 'All selected orders must have the same customer')
                return
        
        # Check if any orders already have invoices
        orders_with_invoices = []
        for order in orders:
            if models.Invoice.objects.filter(sales_order=order).exists():
                orders_with_invoices.append(order.document_no)
        
        if orders_with_invoices:
            messages.error(request, f'Some orders already have invoices: {", ".join(orders_with_invoices)}')
            return
        
        # Create combined invoice
        try:
            result = create_invoice_from_multiple_orders(orders, user=request.user)
            
            if result['success']:
                messages.success(request, result['message'])
                # Redirect to the created invoice
                return redirect('admin:sales_invoice_change', result['invoice'].pk)
            else:
                messages.error(request, result['error'])
                
        except Exception as e:
            messages.error(request, f'Error creating combined invoice: {str(e)}')
    
    create_combined_invoice.short_description = "Create combined invoice from selected orders"
    
    def reactivate_sales_orders(self, request, queryset):
        """Reactivate selected completed or closed sales orders"""
        reactivated_count = 0
        skipped_count = 0
        error_count = 0
        
        for order in queryset:
            try:
                if order.can_reactivate():
                    result_message = order.reactivate(user=request.user)
                    reactivated_count += 1
                    self.message_user(request, f"✓ {result_message}", level=messages.SUCCESS)
                else:
                    skipped_count += 1
                    self.message_user(
                        request, 
                        f"⚠ Order {order.document_no} cannot be reactivated (status: {order.doc_status})", 
                        level=messages.WARNING
                    )
            except Exception as e:
                error_count += 1
                self.message_user(
                    request, 
                    f"❌ Error reactivating order {order.document_no}: {str(e)}", 
                    level=messages.ERROR
                )
        
        # Summary message
        if reactivated_count > 0:
            self.message_user(
                request,
                f"Reactivation complete: {reactivated_count} orders reactivated, {skipped_count} skipped, {error_count} errors",
                level=messages.INFO
            )
    
    reactivate_sales_orders.short_description = "Reactivate selected completed/closed orders"


@admin.register(models.SalesOrderLine)
class SalesOrderLineAdmin(admin.ModelAdmin):
    list_display = ('order', 'line_no', 'product', 'charge', 'quantity_ordered', 'price_actual', 'line_net_amount')
    list_filter = ('order__organization', 'product__manufacturer')
    search_fields = ('order__document_no', 'product__manufacturer_part_number', 'product__name', 'description')
    raw_id_fields = ('order',)  # Use search widget for order
    autocomplete_fields = ['product']  # Enable autocomplete for product selection
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order', 'line_no')
        }),
        ('Product/Service', {
            'fields': ('product', 'charge', 'description'),
            'description': 'Select either a Product OR a Charge (service/fee), not both. Use "Add Product" link below to create new products.'
        }),
        ('Quantities', {
            'fields': ('quantity_ordered', 'quantity_delivered', 'quantity_invoiced')
        }),
        ('Pricing', {
            'fields': ('price_entered', 'price_actual', 'discount', 'line_net_amount')
        }),
        ('Dates', {
            'fields': ('date_promised', 'date_delivered')
        }),
        ('Tax Information', {
            'fields': ('tax', 'tax_amount'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('line_no', 'price_actual', 'line_net_amount', 'quantity_delivered', 'quantity_invoiced')
    
    def get_changeform_initial_data(self, request):
        """Pre-fill order when adding from sales order page"""
        initial = super().get_changeform_initial_data(request)
        
        # Check if order parameter is in the URL
        order_id = request.GET.get('order')
        if order_id:
            try:
                order = models.SalesOrder.objects.get(pk=order_id)
                initial['order'] = order
                # Auto-generate next line number
                last_line = models.SalesOrderLine.objects.filter(order=order).order_by('-line_no').first()
                initial['line_no'] = (last_line.line_no + 10) if last_line else 10
            except models.SalesOrder.DoesNotExist:
                pass
        
        return initial
    
    def save_model(self, request, obj, form, change):
        """Auto-populate created_by and updated_by fields"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly based on parent order workflow state"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        
        if obj and obj.pk and obj.order:
            workflow = obj.order.get_workflow_instance()
            if workflow:
                current_state = workflow.current_state.name
                
                # Lock line items for submitted orders
                locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
                
                if current_state in locked_states:
                    # Make most fields readonly for locked orders
                    locked_fields = ['product', 'charge', 'description', 'quantity_ordered', 'price_entered', 'discount']
                    for field in locked_fields:
                        if field not in readonly_fields:
                            readonly_fields.append(field)
        
        return readonly_fields
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deleting lines for locked orders"""
        if obj and obj.order:
            workflow = obj.order.get_workflow_instance()
            if workflow:
                current_state = workflow.current_state.name
                locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
                if current_state in locked_states:
                    return False
        return super().has_delete_permission(request, obj)


class InvoiceLineInline(admin.TabularInline):
    model = models.InvoiceLine
    extra = 0
    fields = ('line_no', 'product', 'charge', 'description', 'quantity_invoiced', 'price_entered', 'discount', 'line_net_amount')
    readonly_fields = ('line_no',)
    
    def get_readonly_fields(self, request, obj=None):
        """Make line fields readonly based on parent invoice workflow state"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        
        if obj and obj.pk:
            workflow = obj.get_workflow_instance()
            if workflow:
                current_state = workflow.current_state.name
                
                # Lock line items for submitted invoices
                locked_states = ['pending_approval', 'approved', 'sent', 'partial_payment', 'paid', 'overdue', 'cancelled']
                
                if current_state in locked_states:
                    # Make all line fields readonly
                    line_fields = ['product', 'charge', 'description', 'quantity_invoiced', 'price_entered', 'discount', 'line_net_amount']
                    for field in line_fields:
                        if field not in readonly_fields:
                            readonly_fields.append(field)
        
        return readonly_fields


@admin.register(models.Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    form = InvoiceForm
    list_display = ('document_no_display', 'opportunity', 'business_partner', 'date_invoiced', 'doc_status', 'invoice_type', 'grand_total', 'is_paid', 'print_invoice')
    list_filter = ('doc_status', 'opportunity', 'invoice_type', 'organization', 'is_paid', 'is_posted')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description')
    date_hierarchy = 'date_invoiced'
    inlines = [InvoiceLineInline]
    autocomplete_fields = ['opportunity', 'business_partner', 'sales_order']
    
    fieldsets = (
        ('Document Number', {
            'fields': (
                'document_no',
            ),
            'classes': ('wide',),
            'description': 'Document number is auto-generated when the invoice is saved'
        }),
        ('Document Information', {
            'fields': ('organization', 'description', 'invoice_type')
        }),
        ('Dates', {
            'fields': ('date_invoiced', 'date_accounting', 'due_date')
        }),
        ('Address Information', {
            'fields': (
                ('business_partner_location', 'business_partner_address_display'),
                ('bill_to_location', 'bill_to_address_display'),
            ),
            'classes': ('wide',),
            'description': 'All addresses filtered by business partner (save document first to see available addresses)'
        }),
        ('Contact Information', {
            'fields': (
                ('internal_user', 'contact'),
            ),
            'classes': ('wide',),
            'description': 'Internal User: Our company contact | Contact: Customer contact (save document first to see filtered options)'
        }),
        ('References', {
            'fields': ('opportunity', 'sales_order')
        }),
        ('Pricing', {
            'fields': ('price_list', 'currency', 'payment_terms', 'total_lines', 'tax_amount', 'grand_total', 'paid_amount', 'open_amount')
        }),
        ('Sales Rep', {
            'fields': ('sales_rep',)
        }),
        ('Status', {
            'fields': ('is_paid', 'is_posted')
        }),
        ('Workflow & Status', {
            'fields': (
                ('current_workflow_state', 'workflow_actions'),
            ),
            'classes': ('wide',),
            'description': 'Invoice workflow and status management'
        }),
    )
    readonly_fields = ('document_no', 'total_lines', 'tax_amount', 'grand_total', 'paid_amount', 'open_amount', 'business_partner_address_display', 'bill_to_address_display', 'current_workflow_state', 'workflow_actions')
    
    def document_no_display(self, obj):
        """Display document number with INV- prefix"""
        if obj.document_no and obj.document_no.isdigit():
            return f"INV-{obj.document_no}"
        return obj.document_no
    document_no_display.short_description = 'Document No'
    document_no_display.admin_order_field = 'document_no'
    
    def business_partner_address_display(self, obj):
        """Display business partner location with customer name"""
        if obj.business_partner_location:
            return obj.business_partner_location.full_address_with_name
        return "-"
    business_partner_address_display.short_description = "Primary Address"
    
    def bill_to_address_display(self, obj):
        """Display bill to location with customer name"""
        if obj.bill_to_location:
            return obj.bill_to_location.full_address_with_name
        return "-"
    bill_to_address_display.short_description = "Bill To Address"
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make fields readonly based on workflow state.
        Once submitted for approval or completed, fields should be locked.
        """
        readonly_fields = list(super().get_readonly_fields(request, obj))
        
        if obj and obj.pk:
            workflow = obj.get_workflow_instance()
            if workflow:
                current_state = workflow.current_state.name
                
                # Lock fields for submitted/approved invoices
                locked_states = ['pending_approval', 'approved', 'sent', 'partial_payment', 'paid', 'overdue', 'cancelled']
                
                if current_state in locked_states:
                    # Core invoice fields that should be locked (description remains editable)
                    locked_fields = [
                        'business_partner', 'opportunity', 'date_invoiced', 'date_accounting', 'due_date',
                        'contact', 'internal_user', 'business_partner_location', 'bill_to_location',
                        'organization', 'invoice_type', 'sales_order',
                        'price_list', 'currency', 'payment_terms', 'sales_rep'
                    ]
                    
                    # Add locked fields to readonly_fields if not already there
                    for field in locked_fields:
                        if field not in readonly_fields:
                            readonly_fields.append(field)
                    
                    # For completely locked states (paid, cancelled), lock everything
                    if current_state in ['paid', 'cancelled']:
                        # Get all model fields except workflow-related ones
                        all_fields = [f.name for f in obj._meta.fields if f.name not in [
                            'id', 'created', 'updated', 'created_by', 'updated_by', 
                            'is_active', 'legacy_id'
                        ]]
                        
                        for field in all_fields:
                            if field not in readonly_fields:
                                readonly_fields.append(field)
        
        return readonly_fields
    
    def current_workflow_state(self, obj):
        """Display current workflow state with visual indicator"""
        if not obj.pk:
            return '-'
        
        workflow = obj.get_workflow_instance()
        if not workflow:
            return 'No workflow configured'
        
        state_colors = {
            'draft': '#6c757d',           # Gray
            'pending_approval': '#fd7e14', # Orange  
            'approved': '#20c997',        # Teal
            'in_progress': '#0d6efd',     # Blue
            'complete': '#198754',        # Green
            'rejected': '#dc3545',        # Red
            'closed': '#495057',          # Dark gray
            'paid': '#28a745'             # Success green
        }
        
        color = state_colors.get(workflow.current_state.name, '#6c757d')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            color, workflow.current_state.display_name
        )
    current_workflow_state.short_description = 'Workflow State'
    
    def workflow_actions(self, obj):
        """Display workflow action buttons based on current state and permissions"""
        if not obj.pk:
            return '-'
        
        workflow = obj.get_workflow_instance()
        if not workflow:
            return 'No workflow configured'
        
        # For display purposes, we'll show all possible actions
        # The actual permission check happens when the action is executed
        current_user = None  # We'll check permissions during action execution
        
        buttons = []
        current_state = workflow.current_state.name
        
        # State-specific buttons for invoices
        if current_state == 'draft':
            # Check if invoice needs approval based on amount
            if obj.grand_total.amount >= 1000:  # $1000 threshold
                buttons.append(self._create_invoice_workflow_button(
                    'Submit for Approval', 'submit_approval', obj.pk, 'orange'
                ))
            else:
                # Auto-approve under $1000
                buttons.append(self._create_invoice_workflow_button(
                    'Approve & Send', 'auto_approve', obj.pk, 'green'
                ))
            buttons.append(self._create_invoice_workflow_button(
                'Cancel', 'cancel', obj.pk, 'red'
            ))
        
        elif current_state == 'pending_approval':
            buttons.append(self._create_invoice_workflow_button(
                'Approve', 'approve', obj.pk, 'green'
            ))
            buttons.append(self._create_invoice_workflow_button(
                'Reject', 'reject', obj.pk, 'red'
            ))
        
        elif current_state == 'approved':
            buttons.append(self._create_invoice_workflow_button(
                'Send to Customer', 'send_invoice', obj.pk, 'blue'
            ))
            buttons.append(self._create_invoice_workflow_button(
                'Cancel', 'cancel_approved', obj.pk, 'red'
            ))
        
        elif current_state == 'sent':
            buttons.append(self._create_invoice_workflow_button(
                'Record Payment', 'full_payment', obj.pk, 'green'
            ))
            buttons.append(self._create_invoice_workflow_button(
                'Partial Payment', 'partial_payment', obj.pk, 'orange'
            ))
            buttons.append(self._create_invoice_workflow_button(
                'Mark Overdue', 'mark_overdue', obj.pk, 'red'
            ))
        
        elif current_state == 'partial_payment':
            buttons.append(self._create_invoice_workflow_button(
                'Complete Payment', 'complete_payment', obj.pk, 'green'
            ))
            buttons.append(self._create_invoice_workflow_button(
                'Mark Overdue', 'mark_overdue_partial', obj.pk, 'red'
            ))
        
        elif current_state == 'overdue':
            buttons.append(self._create_invoice_workflow_button(
                'Record Payment', 'overdue_payment', obj.pk, 'green'
            ))
            buttons.append(self._create_invoice_workflow_button(
                'Partial Payment', 'overdue_partial_payment', obj.pk, 'orange'
            ))
        
        elif current_state == 'rejected':
            buttons.append(self._create_invoice_workflow_button(
                'Return to Draft', 'return_draft', obj.pk, 'blue'
            ))
            buttons.append(self._create_invoice_workflow_button(
                'Cancel', 'cancel_rejected', obj.pk, 'red'
            ))
        
        if buttons:
            return format_html(' '.join(buttons))
        return 'No actions available'
    
    workflow_actions.short_description = 'Workflow Actions'
    
    def _create_invoice_workflow_button(self, label, action, obj_id, color):
        """Create workflow action button for invoices"""
        colors = {
            'blue': '#007cba',
            'green': '#28a745', 
            'orange': '#fd7e14',
            'red': '#dc3545',
            'gray': '#6c757d'
        }
        
        return format_html(
            '<a href="{}?action={}" style="background-color: {}; color: white; '
            'padding: 4px 8px; text-decoration: none; border-radius: 3px; '
            'margin-right: 5px; font-size: 11px;">{}</a>',
            reverse('admin:sales_invoice_workflow_action', args=[obj_id]),
            action,
            colors.get(color, '#007cba'),
            label
        )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<uuid:object_id>/workflow-action/', 
                 self.admin_site.admin_view(self.invoice_workflow_action_view), 
                 name='sales_invoice_workflow_action'),
        ]
        return custom_urls + urls
    
    def invoice_workflow_action_view(self, request, object_id):
        """Handle invoice workflow action requests"""
        from django.shortcuts import redirect
        from django.contrib import messages
        from core.models import WorkflowApproval, WorkflowState
        from django.utils import timezone
        
        try:
            obj = models.Invoice.objects.get(pk=object_id)
            
            # Get action from query parameter
            action = request.GET.get('action')
            if not action:
                messages.error(request, 'No action specified')
                return redirect('admin:sales_invoice_change', object_id)
            
            workflow = obj.get_workflow_instance()
            if not workflow:
                messages.error(request, 'No workflow configured for this invoice')
                return redirect('admin:sales_invoice_change', object_id)
            
            # Execute workflow action
            result = self.execute_invoice_workflow_action(obj, workflow, action, request.user)
            
            if result['success']:
                messages.success(request, result['message'])
            else:
                messages.error(request, result['error'])
            
            # Redirect back to the invoice change page
            return redirect('admin:sales_invoice_change', object_id)
            
        except models.Invoice.DoesNotExist:
            messages.error(request, 'Invoice not found')
            return redirect('admin:sales_invoice_changelist')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('admin:sales_invoice_change', object_id)
    
    def execute_invoice_workflow_action(self, obj, workflow, action, user):
        """Execute the invoice workflow action with business logic"""
        from core.models import WorkflowState
        from django.utils import timezone
        from decimal import Decimal
        
        current_state = workflow.current_state.name
        
        try:
            # Find the target state based on action
            state_transitions = {
                'submit_approval': 'pending_approval',
                'auto_approve': 'approved',
                'cancel': 'cancelled',
                'approve': 'approved',
                'reject': 'rejected',
                'send_invoice': 'sent',
                'cancel_approved': 'cancelled',
                'full_payment': 'paid',
                'partial_payment': 'partial_payment',
                'mark_overdue': 'overdue',
                'complete_payment': 'paid',
                'mark_overdue_partial': 'overdue',
                'overdue_payment': 'paid',
                'overdue_partial_payment': 'partial_payment',
                'return_draft': 'draft',
                'cancel_rejected': 'cancelled'
            }
            
            target_state_name = state_transitions.get(action)
            if not target_state_name:
                return {'success': False, 'error': f'Unknown action: {action}'}
            
            # Find target state
            target_state = WorkflowState.objects.filter(
                workflow=workflow.workflow_definition,
                name=target_state_name
            ).first()
            
            if not target_state:
                return {'success': False, 'error': f'Target state {target_state_name} not found'}
            
            # Update workflow state
            workflow.current_state = target_state
            workflow.updated = timezone.now()
            workflow.updated_by = user
            workflow.save()
            
            # Update invoice status if needed
            if target_state_name == 'paid':
                obj.is_paid = True
                obj.paid_amount = obj.grand_total
                obj.open_amount = obj.grand_total - obj.paid_amount
            elif target_state_name == 'partial_payment':
                # This would normally require payment amount input
                # For now, we'll just mark it as partially paid
                obj.paid_amount = obj.grand_total * Decimal('0.5')  # Example: 50%
                obj.open_amount = obj.grand_total - obj.paid_amount
            
            obj.save()
            
            return {
                'success': True,
                'message': f'Invoice moved to {target_state.display_name}'
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Error processing action: {str(e)}'}
    
    def print_invoice(self, obj):
        """Add print button in list view"""
        url = reverse('sales:invoice_pdf', args=[obj.id])
        return format_html('<a class="button" href="{}" target="_blank">Print PDF</a>', url)
    print_invoice.short_description = 'Print'


@admin.register(models.InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'line_no', 'product', 'charge', 'quantity_invoiced', 'price_actual', 'line_net_amount')
    list_filter = ('invoice__organization', 'product__manufacturer')
    search_fields = ('invoice__document_no', 'product__manufacturer_part_number', 'product__name', 'description')


class ShipmentLineInline(admin.TabularInline):
    model = models.ShipmentLine
    extra = 0
    fields = ('line_no', 'product', 'description', 'movement_quantity', 'quantity_entered')


@admin.register(models.Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    form = ShipmentForm
    list_display = ('document_no_display', 'opportunity', 'business_partner', 'movement_date', 'doc_status', 'movement_type', 'warehouse', 'is_in_transit')
    list_filter = ('doc_status', 'opportunity', 'movement_type', 'organization', 'warehouse', 'is_in_transit')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description', 'tracking_no')
    date_hierarchy = 'movement_date'
    inlines = [ShipmentLineInline]
    autocomplete_fields = ['opportunity', 'business_partner']
    
    fieldsets = (
        ('Document Number', {
            'fields': (
                'document_no',
            ),
            'classes': ('wide',),
            'description': 'Document number is auto-generated when the shipment is saved'
        }),
        ('Document Information', {
            'fields': ('organization', 'description', 'doc_status', 'movement_type')
        }),
        ('Dates', {
            'fields': ('movement_date', 'date_received')
        }),
        ('Business Partner & Warehouse', {
            'fields': (
                ('business_partner_location', 'business_partner_address_display'),
                ('warehouse',)
            ),
            'classes': ('wide',)
        }),
        ('Contact Information', {
            'fields': (
                ('internal_user', 'contact'),
            ),
            'classes': ('wide',),
            'description': 'Internal User: Our company contact | Contact: Customer contact (save document first to see filtered options)'
        }),
        ('References', {
            'fields': ('opportunity', 'sales_order')
        }),
        ('Shipping', {
            'fields': ('delivery_via', 'tracking_no', 'freight_amount')
        }),
        ('Flags', {
            'fields': ('is_printed', 'is_in_transit')
        }),
        ('Workflow & Status', {
            'fields': (
                ('current_workflow_state', 'workflow_actions'),
            ),
            'classes': ('wide',),
            'description': 'Shipment workflow and status management'
        }),
    )
    readonly_fields = ('document_no', 'business_partner_address_display', 'current_workflow_state', 'workflow_actions')
    
    def document_no_display(self, obj):
        """Display document number with SH- prefix"""
        if obj.document_no and obj.document_no.isdigit():
            return f"SH-{obj.document_no}"
        return obj.document_no
    document_no_display.short_description = 'Document No'
    document_no_display.admin_order_field = 'document_no'
    
    def business_partner_address_display(self, obj):
        """Display ship-to address with customer name"""
        if obj.business_partner_location:
            return obj.business_partner_location.full_address_with_name
        return "-"
    business_partner_address_display.short_description = "Ship To Address"
    
    def current_workflow_state(self, obj):
        """Display current workflow state with visual indicator"""
        if not obj.pk:
            return '-'
        
        workflow = obj.get_workflow_instance()
        if not workflow:
            return 'No workflow configured'
        
        state_colors = {
            'draft': '#6c757d',           # Gray
            'prepared': '#fd7e14',        # Orange  
            'in_transit': '#0d6efd',      # Blue
            'delivered': '#20c997',       # Teal
            'complete': '#198754',        # Green
            'returned': '#ffc107',        # Yellow
            'cancelled': '#495057',       # Dark gray
        }
        
        color = state_colors.get(workflow.current_state.name, '#6c757d')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-weight: bold;">{}</span>',
            color, workflow.current_state.display_name
        )
    current_workflow_state.short_description = 'Workflow State'
    
    def workflow_actions(self, obj):
        """Display workflow action buttons based on current state"""
        if not obj.pk:
            return '-'
        
        workflow = obj.get_workflow_instance()
        if not workflow:
            return 'No workflow configured'
        
        buttons = []
        current_state = workflow.current_state.name
        
        # State-specific buttons for shipments
        if current_state == 'draft':
            buttons.append(self._create_shipment_workflow_button(
                'Prepare Shipment', 'prepare', obj.pk, 'blue'
            ))
            buttons.append(self._create_shipment_workflow_button(
                'Cancel', 'cancel', obj.pk, 'red'
            ))
        
        elif current_state == 'prepared':
            buttons.append(self._create_shipment_workflow_button(
                'Ship', 'ship', obj.pk, 'blue'
            ))
            buttons.append(self._create_shipment_workflow_button(
                'Cancel', 'cancel_prepared', obj.pk, 'red'
            ))
        
        elif current_state == 'in_transit':
            buttons.append(self._create_shipment_workflow_button(
                'Mark Delivered', 'deliver', obj.pk, 'green'
            ))
            buttons.append(self._create_shipment_workflow_button(
                'Mark Returned', 'return_shipment', obj.pk, 'orange'
            ))
        
        elif current_state == 'delivered':
            buttons.append(self._create_shipment_workflow_button(
                'Complete', 'complete', obj.pk, 'green'
            ))
            buttons.append(self._create_shipment_workflow_button(
                'Process Return', 'process_return', obj.pk, 'orange'
            ))
        
        elif current_state == 'returned':
            buttons.append(self._create_shipment_workflow_button(
                'Reship', 'reship', obj.pk, 'blue'
            ))
            buttons.append(self._create_shipment_workflow_button(
                'Cancel Order', 'cancel_order', obj.pk, 'red'
            ))
        
        if buttons:
            return format_html(' '.join(buttons))
        return 'No actions available'
    
    workflow_actions.short_description = 'Workflow Actions'
    
    def _create_shipment_workflow_button(self, label, action, obj_id, color):
        """Create workflow action button for shipments"""
        colors = {
            'blue': '#007cba',
            'green': '#28a745', 
            'orange': '#fd7e14',
            'red': '#dc3545',
            'gray': '#6c757d'
        }
        
        return format_html(
            '<a href="{}?action={}" style="background-color: {}; color: white; '
            'padding: 4px 8px; text-decoration: none; border-radius: 3px; '
            'margin-right: 5px; font-size: 11px;">{}</a>',
            reverse('admin:sales_shipment_workflow_action', args=[obj_id]),
            action,
            colors.get(color, '#007cba'),
            label
        )


@admin.register(models.ShipmentLine)
class ShipmentLineAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'line_no', 'product', 'movement_quantity', 'quantity_entered')
    list_filter = ('shipment__organization', 'product__manufacturer')
    search_fields = ('shipment__document_no', 'product__manufacturer_part_number', 'product__name', 'description')


