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
    extra = 0
    fields = ('line_no', 'product', 'quantity_ordered', 'price_entered')
    readonly_fields = ('line_no',)
    
    def get_readonly_fields(self, request, obj=None):
        """Make line fields readonly based on parent order workflow state"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        
        if obj and obj.pk:
            workflow = obj.get_workflow_instance()
            if workflow:
                current_state = workflow.current_state.name
                
                # Lock line items for submitted orders
                locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
                
                if current_state in locked_states:
                    # Make all line fields readonly
                    line_fields = ['product', 'quantity_ordered', 'price_entered']
                    for field in line_fields:
                        if field not in readonly_fields:
                            readonly_fields.append(field)
        
        return readonly_fields
    
    def has_add_permission(self, request, obj=None):
        """Prevent adding new lines for locked orders"""
        if obj and obj.pk:
            workflow = obj.get_workflow_instance()
            if workflow:
                current_state = workflow.current_state.name
                locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
                if current_state in locked_states:
                    return False
        return super().has_add_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deleting lines for locked orders"""
        if obj and obj.pk:
            workflow = obj.get_workflow_instance()
            if workflow:
                current_state = workflow.current_state.name
                locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
                if current_state in locked_states:
                    return False
        return super().has_delete_permission(request, obj)


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
    list_display = ('document_no', 'opportunity', 'business_partner', 'date_ordered', 'workflow_state_display', 'grand_total', 'is_delivered', 'is_invoiced', 'lock_status', 'print_order')
    list_filter = ('doc_status', 'opportunity', 'organization', 'warehouse', 'is_delivered', 'is_invoiced', 'is_drop_ship')
    readonly_fields = ('business_partner_address_display', 'bill_to_address_display', 'ship_to_address_display', 'transaction_id', 'transaction_actions')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description')
    date_hierarchy = 'date_ordered'
    inlines = [SalesOrderLineInline]
    
    def print_order(self, obj):
        """Add print button in list view"""
        url = reverse('sales:order_pdf', args=[obj.id])
        return format_html('<a class="button" href="{}" target="_blank">Print PDF</a>', url)
    print_order.short_description = 'Print'
    print_order.allow_tags = True
    
    fieldsets = (
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
                ('organization', 'document_no'),
                ('description', 'doc_status'),
            ),
            'classes': ('wide',)
        }),
        ('Pricing', {
            'fields': (
                ('currency', 'warehouse'),
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
        ('Workflow & Approval', {
            'fields': (
                ('current_workflow_state', 'workflow_actions'),
                ('approval_status_display',),
            ),
            'classes': ('wide',),
            'description': 'Document workflow and approval management'
        }),
    )
    readonly_fields = ('total_lines', 'grand_total', 'business_partner_address_display', 'bill_to_address_display', 'ship_to_address_display', 'transaction_id', 'transaction_actions', 'payment_url_display', 'current_workflow_state', 'workflow_actions', 'approval_status_display')
    
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
        
        elif current_state == 'in_progress':
            buttons.append(self._create_workflow_button(
                'Mark Complete', 'complete', obj.pk, 'green'
            ))
        
        elif current_state == 'complete':
            buttons.append(self._create_workflow_button(
                'Reactivate', 'reactivate', obj.pk, 'orange'
            ))
            buttons.append(self._create_workflow_button(
                'Close', 'close', obj.pk, 'gray'
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
                # Reactivate completed order
                if not has_permission('reactivate_documents'):
                    return {'success': False, 'error': 'Insufficient permissions to reactivate orders'}
                
                if current_state != 'complete':
                    return {'success': False, 'error': 'Can only reactivate completed orders'}
                
                progress_state = WorkflowState.objects.get(
                    workflow=workflow.workflow_definition, 
                    name='in_progress'
                )
                workflow.current_state = progress_state
                workflow.save()
                
                return {
                    'success': True,
                    'message': 'Order reactivated'
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


@admin.register(models.SalesOrderLine)
class SalesOrderLineAdmin(admin.ModelAdmin):
    list_display = ('order', 'line_no', 'product', 'charge', 'quantity_ordered', 'price_actual', 'line_net_amount')
    list_filter = ('order__organization', 'product__manufacturer')
    search_fields = ('order__document_no', 'product__manufacturer_part_number', 'product__name', 'description')


class InvoiceLineInline(admin.TabularInline):
    model = models.InvoiceLine
    extra = 0
    fields = ('line_no', 'product', 'charge', 'description', 'quantity_invoiced', 'price_entered', 'discount', 'line_net_amount')


@admin.register(models.Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    form = InvoiceForm
    list_display = ('document_no', 'opportunity', 'business_partner', 'date_invoiced', 'doc_status', 'invoice_type', 'grand_total', 'is_paid')
    list_filter = ('doc_status', 'opportunity', 'invoice_type', 'organization', 'is_paid', 'is_posted')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description')
    date_hierarchy = 'date_invoiced'
    inlines = [InvoiceLineInline]
    
    fieldsets = (
        ('Document Information', {
            'fields': ('organization', 'document_no', 'description', 'doc_status', 'invoice_type')
        }),
        ('Dates', {
            'fields': ('date_invoiced', 'date_accounting', 'due_date')
        }),
        ('Business Partner', {
            'fields': (
                ('business_partner_location', 'business_partner_address_display'),
                ('bill_to_location', 'bill_to_address_display'),
                ('bill_to_address',)
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
        ('Pricing', {
            'fields': ('price_list', 'currency', 'payment_terms', 'total_lines', 'tax_amount', 'grand_total', 'paid_amount', 'open_amount')
        }),
        ('Sales Rep', {
            'fields': ('sales_rep',)
        }),
        ('Flags', {
            'fields': ('is_printed', 'is_paid', 'is_posted')
        }),
    )
    readonly_fields = ('total_lines', 'tax_amount', 'grand_total', 'paid_amount', 'open_amount', 'business_partner_address_display', 'bill_to_address_display')
    
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
    list_display = ('document_no', 'opportunity', 'business_partner', 'movement_date', 'doc_status', 'movement_type', 'warehouse', 'is_in_transit')
    list_filter = ('doc_status', 'opportunity', 'movement_type', 'organization', 'warehouse', 'is_in_transit')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description', 'tracking_no')
    date_hierarchy = 'movement_date'
    inlines = [ShipmentLineInline]
    
    fieldsets = (
        ('Document Information', {
            'fields': ('organization', 'document_no', 'description', 'doc_status', 'movement_type')
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
    )
    readonly_fields = ('business_partner_address_display',)
    
    def business_partner_address_display(self, obj):
        """Display ship-to address with customer name"""
        if obj.business_partner_location:
            return obj.business_partner_location.full_address_with_name
        return "-"
    business_partner_address_display.short_description = "Ship To Address"


@admin.register(models.ShipmentLine)
class ShipmentLineAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'line_no', 'product', 'movement_quantity', 'quantity_entered')
    list_filter = ('shipment__organization', 'product__manufacturer')
    search_fields = ('shipment__document_no', 'product__manufacturer_part_number', 'product__name', 'description')


