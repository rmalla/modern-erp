"""
Django admin configuration for purchasing models.
Updated: 2025-06-24 13:01 - Added Purchase Order PDF functionality
"""

from django.contrib import admin
from django.utils.html import format_html
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import path, reverse
from django.http import JsonResponse
from django.utils import timezone
from django import forms
from . import models
from core.models import Contact


class DocumentContactForm(forms.ModelForm):
    """Custom form for documents with contact and location filtering based on business partner"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If we have an instance with a business partner, filter the contacts and locations
        if hasattr(self.instance, 'business_partner') and self.instance.business_partner:
            # Filter contacts
            self.fields['contact'].queryset = Contact.objects.filter(
                business_partner=self.instance.business_partner
            )
            self.fields['contact'].help_text = f"Contacts for {self.instance.business_partner.name}"
            
            # Filter locations for bill_to (vendor addresses)
            from core.models import BusinessPartnerLocation
            vendor_locations = BusinessPartnerLocation.objects.filter(
                business_partner=self.instance.business_partner
            )
            
            if 'bill_to_location' in self.fields:
                self.fields['bill_to_location'].queryset = vendor_locations
                self.fields['bill_to_location'].help_text = f"Vendor addresses for {self.instance.business_partner.name}"
            
            if 'business_partner_location' in self.fields:
                self.fields['business_partner_location'].queryset = vendor_locations
                self.fields['business_partner_location'].help_text = f"Primary vendor address for {self.instance.business_partner.name}"
                
        else:
            # No business partner selected, clear all dependent fields
            self.fields['contact'].queryset = Contact.objects.none()
            self.fields['contact'].help_text = "Save with a business partner first to see available contacts"
            
            from core.models import BusinessPartnerLocation
            
            if 'bill_to_location' in self.fields:
                self.fields['bill_to_location'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['bill_to_location'].help_text = "Save with a vendor first to see available addresses"
            
            if 'business_partner_location' in self.fields:
                self.fields['business_partner_location'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['business_partner_location'].help_text = "Save with a vendor first to see available addresses"
        
        # Handle ship-to customer filtering separately
        if hasattr(self.instance, 'ship_to_customer') and self.instance.ship_to_customer:
            from core.models import BusinessPartnerLocation
            customer_locations = BusinessPartnerLocation.objects.filter(
                business_partner=self.instance.ship_to_customer
            )
            
            if 'ship_to_location' in self.fields:
                self.fields['ship_to_location'].queryset = customer_locations
                self.fields['ship_to_location'].help_text = f"Customer addresses for {self.instance.ship_to_customer.name}"
        else:
            if 'ship_to_location' in self.fields:
                from core.models import BusinessPartnerLocation
                self.fields['ship_to_location'].queryset = BusinessPartnerLocation.objects.none()
                self.fields['ship_to_location'].help_text = "Select a ship-to customer first to see available addresses"


class PurchaseOrderForm(DocumentContactForm):
    class Meta:
        model = models.PurchaseOrder
        fields = '__all__'


class PurchaseOrderLineInline(admin.TabularInline):
    model = models.PurchaseOrderLine
    extra = 0  # No empty fields
    readonly_fields = ('line_link', 'product_display', 'quantity_display', 'price_display', 'line_total_display')
    can_delete = True
    show_change_link = False  # We'll use our custom link
    verbose_name = "Order Line"
    verbose_name_plural = "Purchase Order Lines"
    template = 'admin/purchasing/purchaseorderline_inline.html'  # Custom template
    
    def get_fields(self, request, obj=None):
        """Return the readonly fields for display"""
        return self.readonly_fields
    
    def line_link(self, obj):
        """Display line number as link to edit page"""
        if obj.pk:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:purchasing_purchaseorderline_change', args=[obj.pk])
            return format_html('<a href="{}" target="_blank"><strong>Line {}</strong></a>', url, obj.line_no)
        return "-"
    line_link.short_description = "Line #"
    
    def product_display(self, obj):
        """Display product information"""
        if obj.product:
            return f"{obj.product.name}"
        elif obj.charge:
            return f"⚡ {obj.charge.name}"
        else:
            return obj.description or "-"
    product_display.short_description = "Product/Charge"
    
    def quantity_display(self, obj):
        """Display quantity ordered"""
        return obj.quantity_ordered
    quantity_display.short_description = "Qty"
    
    def price_display(self, obj):
        """Display unit price"""
        if obj.price_entered:
            return f"${obj.price_entered.amount:.2f}"
        return "-"
    price_display.short_description = "Unit Price"
    
    def line_total_display(self, obj):
        """Display line total"""
        if obj.line_net_amount:
            return f"${obj.line_net_amount.amount:.2f}"
        return "-"
    line_total_display.short_description = "Line Total"
    
    def get_readonly_fields(self, request, obj=None):
        """Always return our display fields since we use custom template"""
        return ('line_link', 'product_display', 'quantity_display', 'price_display', 'line_total_display')
    
    def has_add_permission(self, request, obj=None):
        """Disable adding through inline - use the add button instead"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable changing through inline - use the edit link instead"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deleting lines when purchase order is locked"""
        if obj and hasattr(obj, 'order'):  # obj might be a line item
            parent_order = obj.order
        elif obj:  # obj is the parent PurchaseOrder
            parent_order = obj
        else:
            return super().has_delete_permission(request, obj)
        
        workflow_instance = parent_order.get_workflow_instance()
        if workflow_instance and workflow_instance.current_state:
            current_state = workflow_instance.current_state.name
            locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
            
            if current_state in locked_states:
                return False
        
        return super().has_delete_permission(request, obj)


@admin.register(models.PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    form = PurchaseOrderForm
    list_display = ('document_no_display', 'opportunity', 'business_partner', 'date_ordered', 'workflow_state_display', 'lock_status', 'grand_total', 'is_received', 'is_invoiced', 'pdf_link')
    list_filter = ('doc_status', 'opportunity', 'organization', 'warehouse', 'is_received', 'is_invoiced', 'is_drop_ship')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'vendor_reference', 'description')
    date_hierarchy = 'date_ordered'
    inlines = [PurchaseOrderLineInline]
    autocomplete_fields = ['opportunity', 'business_partner', 'ship_to_customer']
    
    def get_changeform_initial_data(self, request):
        """Set initial data for the change form (when adding new purchase orders)"""
        from purchasing.models import (
            get_default_organization,
            get_default_currency,
            get_default_warehouse,
            get_default_purchase_price_list,
            get_today_date
        )
        
        initial = super().get_changeform_initial_data(request)
        
        try:
            initial['date_ordered'] = get_today_date()
        except:
            pass
            
        try:
            initial['organization'] = get_default_organization()
        except:
            pass
            
        try:
            initial['currency'] = get_default_currency()
        except:
            pass
            
        try:
            initial['warehouse'] = get_default_warehouse()
        except:
            pass
            
        try:
            initial['price_list'] = get_default_purchase_price_list()
        except:
            pass
            
        return initial
    
    def get_urls(self):
        """Add workflow action URLs"""
        urls = super().get_urls()
        workflow_urls = [
            path(
                '<uuid:object_id>/workflow-action/<str:action>/',
                self.admin_site.admin_view(self.workflow_action_view),
                name='purchasing_purchaseorder_workflow_action'
            ),
        ]
        return workflow_urls + urls
    
    def get_readonly_fields(self, request, obj=None):
        """Dynamic readonly fields based on workflow state"""
        readonly_fields = list(self.readonly_fields)
        
        if obj:
            workflow_instance = obj.get_workflow_instance()
            if workflow_instance and workflow_instance.current_state:
                current_state = workflow_instance.current_state.name
                
                # Define which states lock which fields
                locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
                
                if current_state in locked_states:
                    # Lock core fields for approved and later states
                    locked_fields = [
                        'business_partner', 'opportunity', 'date_ordered', 'date_promised',
                        'payment_terms', 'incoterms', 'incoterms_location',
                        'contact', 'internal_user', 'vendor_reference',
                        'business_partner_location', 'bill_to_location',
                        'ship_to_customer', 'ship_to_location',
                        'price_list', 'currency', 'warehouse',
                        'delivery_via', 'delivery_rule', 'estimated_delivery_weeks'
                    ]
                    
                    # Complete lockdown for final states
                    if current_state in ['complete', 'closed']:
                        locked_fields.extend([
                            'description', 'buyer', 'freight_cost_rule',
                            'is_printed', 'is_received', 'is_invoiced', 'is_drop_ship'
                        ])
                    
                    readonly_fields.extend(locked_fields)
        
        return readonly_fields
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Add workflow state warnings to the change view"""
        extra_context = extra_context or {}
        
        try:
            obj = self.get_object(request, object_id)
            if obj:
                workflow_instance = obj.get_workflow_instance()
                if workflow_instance and workflow_instance.current_state:
                    state = workflow_instance.current_state.name
                    
                    # Add warning messages for locked states
                    if state == 'pending_approval':
                        messages.warning(request, "🔒 This purchase order is pending approval and cannot be modified.")
                    elif state == 'approved':
                        messages.info(request, "✅ This purchase order has been approved. Key fields are locked.")
                    elif state in ['in_progress', 'complete', 'closed']:
                        messages.info(request, f"🔒 This purchase order is {state.replace('_', ' ')} and most fields are locked.")
        except:
            pass
        
        return super().change_view(request, object_id, form_url, extra_context)
    
    def workflow_state_display(self, obj):
        """Display current workflow state with color coding"""
        workflow_instance = obj.get_workflow_instance()
        if not workflow_instance or not workflow_instance.current_state:
            return format_html('<span style="color: #999;">No Workflow</span>')
        
        state = workflow_instance.current_state
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            state.color_code,
            state.display_name
        )
    workflow_state_display.short_description = 'Workflow State'
    
    def lock_status(self, obj):
        """Display lock status icon"""
        workflow_instance = obj.get_workflow_instance()
        if not workflow_instance or not workflow_instance.current_state:
            return format_html('<span style="color: #999;">-</span>')
        
        state = workflow_instance.current_state.name
        locked_states = ['pending_approval', 'approved', 'in_progress', 'complete', 'closed']
        
        if state in locked_states:
            return format_html('<span style="font-size: 14px;" title="Document is locked">🔒</span>')
        else:
            return format_html('<span style="font-size: 14px;" title="Document is editable">✏️</span>')
    lock_status.short_description = 'Lock'
    
    def document_no_display(self, obj):
        """Display document number with PO- prefix"""
        if obj.document_no and obj.document_no.isdigit():
            return f"PO-{obj.document_no}"
        return obj.document_no
    document_no_display.short_description = 'Document No'
    document_no_display.admin_order_field = 'document_no'
    
    def pdf_link(self, obj):
        """Generate PDF link for the purchase order"""
        from django.urls import reverse
        url = reverse('purchasing:purchase_order_pdf', args=[obj.pk])
        return format_html('<a href="{}" target="_blank" style="color: #1a5490; font-weight: bold;">📄 PDF</a>', url)
    pdf_link.short_description = "PDF"
    
    fieldsets = (
        ('Document Number', {
            'fields': (
                'document_no',
            ),
            'classes': ('wide',),
            'description': 'Document number is auto-generated when the purchase order is saved'
        }),
        ('Purchase Order Header', {
            'fields': (
                ('business_partner', 'opportunity'),
                ('date_ordered', 'date_promised'),
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
            'description': 'Internal User: Our company contact | Contact: Vendor contact (save document first to see filtered options)'
        }),
        ('Document Information', {
            'fields': (
                ('organization', 'doc_status'),
                ('description',),
            ),
            'classes': ('wide',)
        }),
        ('Workflow & Approval', {
            'fields': (
                ('current_workflow_state', 'workflow_actions'),
                ('approval_status_display',),
            ),
            'classes': ('wide',),
            'description': 'Document workflow and approval management'
        }),
        ('Address Information', {
            'fields': (
                ('vendor_reference', 'buyer'),
                ('business_partner_location', 'business_partner_address_display'),
                ('bill_to_location', 'bill_to_address_display'),
                ('ship_to_customer', 'ship_to_location'),
                ('ship_to_address_display',),
                ('bill_to_address', 'ship_to_address'),
            ),
            'classes': ('wide',),
            'description': 'Ship-to Customer: Select customer for direct shipment | Ship-to Location: Customer address (save with customer first to see options)'
        }),
        ('Pricing', {
            'fields': (
                ('price_list', 'currency'),
                ('total_lines', 'grand_total'),
            ),
            'classes': ('wide',)
        }),
        ('Delivery', {
            'fields': (
                ('warehouse', 'delivery_via'),
                ('delivery_rule', 'freight_cost_rule'),
                ('date_received', 'estimated_delivery_weeks'),
            ),
            'classes': ('wide',)
        }),
        ('Flags', {
            'fields': (
                ('is_printed', 'is_received'),
                ('is_invoiced', 'is_drop_ship'),
            ),
            'classes': ('wide',)
        }),
    )
    readonly_fields = ('document_no', 'total_lines', 'grand_total', 'business_partner_address_display', 'bill_to_address_display', 'ship_to_address_display', 'current_workflow_state', 'workflow_actions', 'approval_status_display')
    
    
    def business_partner_address_display(self, obj):
        """Display business partner location with vendor name"""
        if obj.business_partner_location:
            return obj.business_partner_location.full_address_with_name
        return "-"
    business_partner_address_display.short_description = "Primary Address"
    
    def bill_to_address_display(self, obj):
        """Display bill to location with vendor name"""
        if obj.bill_to_location:
            return obj.bill_to_location.full_address_with_name
        return "-"
    bill_to_address_display.short_description = "Bill To Address"
    
    def ship_to_address_display(self, obj):
        """Display ship to location with customer name"""
        if obj.ship_to_location:
            return obj.ship_to_location.full_address_with_name
        elif obj.ship_to_customer:
            return f"Customer: {obj.ship_to_customer.name} (no address selected)"
        return "-"
    ship_to_address_display.short_description = "Ship To Address"
    
    def current_workflow_state(self, obj):
        """Display current workflow state with color coding"""
        workflow_instance = obj.get_workflow_instance()
        if not workflow_instance or not workflow_instance.current_state:
            return format_html('<span style="color: #999;">No Workflow</span>')
        
        state = workflow_instance.current_state
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">{}</span>',
            state.color_code,
            state.display_name
        )
    current_workflow_state.short_description = 'Current State'
    
    def workflow_actions(self, obj):
        """Display available workflow action buttons"""
        workflow_instance = obj.get_workflow_instance()
        if not workflow_instance or not workflow_instance.current_state:
            return format_html('<span style="color: #999;">No actions available</span>')
        
        current_state = workflow_instance.current_state.name
        actions = []
        
        # Define actions based on current state
        if current_state == 'draft':
            if obj.needs_approval():
                actions.append(('submit_approval', 'Submit for Approval', 'orange'))
            else:
                actions.append(('auto_approve', 'Auto-Approve & Start', 'green'))
        
        elif current_state == 'pending_approval':
            actions.append(('approve', 'Approve', 'green'))
            actions.append(('reject', 'Reject', 'red'))
            actions.append(('return_draft', 'Return to Draft', 'gray'))
        
        elif current_state == 'approved':
            actions.append(('start_progress', 'Start Processing', 'blue'))
            actions.append(('reactivate', 'Reactivate', 'orange'))
        
        elif current_state == 'in_progress':
            actions.append(('complete', 'Mark Complete', 'green'))
            actions.append(('reactivate', 'Reactivate', 'orange'))
        
        elif current_state == 'complete':
            actions.append(('close', 'Close', 'gray'))
            actions.append(('reactivate', 'Reactivate', 'orange'))
        
        elif current_state == 'closed':
            actions.append(('reactivate', 'Reactivate', 'orange'))
        
        elif current_state == 'rejected':
            actions.append(('return_draft', 'Return to Draft', 'blue'))
        
        if not actions:
            return format_html('<span style="color: #999;">No actions available</span>')
        
        # Generate action buttons
        buttons = []
        for action, label, color in actions:
            url = reverse('admin:purchasing_purchaseorder_workflow_action', args=[obj.pk, action])
            
            # Color mapping
            color_styles = {
                'blue': 'background: #0d6efd; color: white;',
                'green': 'background: #198754; color: white;',
                'orange': 'background: #fd7e14; color: white;',
                'red': 'background: #dc3545; color: white;',
                'gray': 'background: #6c757d; color: white;',
            }
            
            style = color_styles.get(color, 'background: #6c757d; color: white;')
            
            buttons.append(
                f'<a href="{url}" style="display: inline-block; padding: 4px 8px; margin: 2px; '
                f'border-radius: 3px; text-decoration: none; font-size: 11px; font-weight: bold; {style}"'
                f' onclick="return confirm(\'Are you sure you want to {label.lower()}?\');">{label}</a>'
            )
        
        return format_html(' '.join(buttons))
    workflow_actions.short_description = 'Actions'
    
    def approval_status_display(self, obj):
        """Display approval status and history"""
        workflow_instance = obj.get_workflow_instance()
        if not workflow_instance:
            return format_html('<span style="color: #999;">No workflow</span>')
        
        from core.models import WorkflowApproval
        
        # Get the most recent approval for this document
        latest_approval = WorkflowApproval.objects.filter(
            document_workflow=workflow_instance
        ).order_by('-requested_at').first()
        
        if not latest_approval:
            return format_html('<span style="color: #999;">No approval requests</span>')
        
        # Format the approval information
        if latest_approval.status == 'pending':
            return format_html(
                '<div><strong>Pending Approval</strong><br/>'
                'Requested by: {} on {}<br/>'
                'Amount: ${:,.2f}</div>',
                latest_approval.requested_by.get_full_name() if latest_approval.requested_by else 'Unknown',
                latest_approval.requested_at.strftime('%Y-%m-%d %H:%M'),
                float(latest_approval.amount_at_request.amount) if latest_approval.amount_at_request else 0
            )
        elif latest_approval.status == 'approved':
            return format_html(
                '<div><strong>✅ Approved</strong><br/>'
                'Approved by: {} on {}<br/>'
                'Amount: ${:,.2f}</div>',
                latest_approval.approver.get_full_name() if latest_approval.approver else 'Unknown',
                latest_approval.responded_at.strftime('%Y-%m-%d %H:%M') if latest_approval.responded_at else 'Unknown',
                float(latest_approval.amount_at_request.amount) if latest_approval.amount_at_request else 0
            )
        elif latest_approval.status == 'rejected':
            return format_html(
                '<div><strong>❌ Rejected</strong><br/>'
                'Rejected by: {} on {}<br/>'
                'Comments: {}</div>',
                latest_approval.approver.get_full_name() if latest_approval.approver else 'Unknown',
                latest_approval.responded_at.strftime('%Y-%m-%d %H:%M') if latest_approval.responded_at else 'Unknown',
                latest_approval.comments or 'No comments'
            )
        
        return format_html('<span style="color: #999;">Status: {}</span>', latest_approval.get_status_display())
    approval_status_display.short_description = 'Approval Status'
    
    def workflow_action_view(self, request, object_id, action):
        """Handle workflow action requests"""
        try:
            obj = models.PurchaseOrder.objects.get(pk=object_id)
            result = self.execute_workflow_action(obj, action, request.user)
            
            if result['success']:
                messages.success(request, result['message'])
            else:
                messages.error(request, result['message'])
                
        except models.PurchaseOrder.DoesNotExist:
            messages.error(request, "Purchase order not found.")
        except Exception as e:
            messages.error(request, f"Error executing action: {str(e)}")
        
        # Redirect back to the change page
        return redirect('admin:purchasing_purchaseorder_change', object_id)
    
    def execute_workflow_action(self, obj, action, user):
        """Execute a workflow action with business logic"""
        workflow_instance = obj.get_workflow_instance()
        if not workflow_instance:
            return {'success': False, 'message': 'No workflow instance found'}
        
        current_state = workflow_instance.current_state.name
        
        # Permission checking helper
        def has_permission(perm_code):
            if user.is_superuser:
                return True
            from core.models import UserPermission
            return UserPermission.objects.filter(
                user=user, 
                permission_code=perm_code, 
                is_active=True
            ).exists()
        
        try:
            from core.models import WorkflowState, WorkflowApproval
            
            if action == 'submit_approval':
                if current_state != 'draft':
                    return {'success': False, 'message': 'Can only submit draft purchase orders for approval'}
                
                # Check if user has permission to submit for approval
                if not has_permission('submit_for_approval'):
                    return {'success': False, 'message': 'You do not have permission to submit for approval'}
                
                # Change to pending approval state
                pending_state = WorkflowState.objects.get(
                    workflow=workflow_instance.workflow_definition,
                    name='pending_approval'
                )
                workflow_instance.current_state = pending_state
                workflow_instance.save()
                
                # Create approval request
                WorkflowApproval.objects.create(
                    document_workflow=workflow_instance,
                    requested_by=user,
                    status='pending',
                    amount_at_request=obj.grand_total
                )
                
                obj.doc_status = 'pending_approval'
                obj.save()
                
                return {'success': True, 'message': f'Purchase order {obj.document_no} submitted for approval'}
            
            elif action == 'auto_approve':
                if current_state != 'draft':
                    return {'success': False, 'message': 'Can only auto-approve draft purchase orders'}
                
                # Check if user has approval permission
                if not has_permission('approve_purchase_orders'):
                    return {'success': False, 'message': 'You do not have permission to approve purchase orders'}
                
                # Check if order is under threshold (doesn't need approval)
                if obj.needs_approval():
                    return {'success': False, 'message': f'Purchase order amount ${obj.grand_total} requires formal approval'}
                
                # Move to approved state
                approved_state = WorkflowState.objects.get(
                    workflow=workflow_instance.workflow_definition,
                    name='approved'
                )
                workflow_instance.current_state = approved_state
                workflow_instance.save()
                
                # Create auto-approval record
                WorkflowApproval.objects.create(
                    document_workflow=workflow_instance,
                    requested_by=user,
                    approver=user,
                    status='approved',
                    amount_at_request=obj.grand_total,
                    responded_at=timezone.now(),
                    comments='Auto-approved (under threshold)'
                )
                
                obj.doc_status = 'approved'
                obj.save()
                
                return {'success': True, 'message': f'Purchase order {obj.document_no} auto-approved and ready for processing'}
            
            elif action == 'approve':
                if current_state != 'pending_approval':
                    return {'success': False, 'message': 'Can only approve pending purchase orders'}
                
                # Check if user has approval permission
                if not has_permission('approve_purchase_orders'):
                    return {'success': False, 'message': 'You do not have permission to approve purchase orders'}
                
                # Move to approved state
                approved_state = WorkflowState.objects.get(
                    workflow=workflow_instance.workflow_definition,
                    name='approved'
                )
                workflow_instance.current_state = approved_state
                workflow_instance.save()
                
                # Update approval record
                approval = WorkflowApproval.objects.filter(
                    document_workflow=workflow_instance,
                    status='pending'
                ).order_by('-requested_at').first()
                
                if approval:
                    approval.approver = user
                    approval.status = 'approved'
                    approval.responded_at = timezone.now()
                    approval.save()
                
                obj.doc_status = 'approved'
                obj.save()
                
                return {'success': True, 'message': f'Purchase order {obj.document_no} approved'}
            
            elif action == 'reject':
                if current_state != 'pending_approval':
                    return {'success': False, 'message': 'Can only reject pending purchase orders'}
                
                # Check if user has approval permission
                if not has_permission('approve_purchase_orders'):
                    return {'success': False, 'message': 'You do not have permission to reject purchase orders'}
                
                # Move to rejected state
                rejected_state = WorkflowState.objects.get(
                    workflow=workflow_instance.workflow_definition,
                    name='rejected'
                )
                workflow_instance.current_state = rejected_state
                workflow_instance.save()
                
                # Update approval record
                approval = WorkflowApproval.objects.filter(
                    document_workflow=workflow_instance,
                    status='pending'
                ).order_by('-requested_at').first()
                
                if approval:
                    approval.approver = user
                    approval.status = 'rejected'
                    approval.responded_at = timezone.now()
                    approval.comments = 'Purchase order rejected'
                    approval.save()
                
                obj.doc_status = 'rejected'
                obj.save()
                
                return {'success': True, 'message': f'Purchase order {obj.document_no} rejected'}
            
            elif action == 'return_draft':
                if current_state not in ['pending_approval', 'rejected']:
                    return {'success': False, 'message': 'Can only return pending or rejected purchase orders to draft'}
                
                # Move to draft state
                draft_state = WorkflowState.objects.get(
                    workflow=workflow_instance.workflow_definition,
                    name='draft'
                )
                workflow_instance.current_state = draft_state
                workflow_instance.save()
                
                obj.doc_status = 'draft'
                obj.save()
                
                return {'success': True, 'message': f'Purchase order {obj.document_no} returned to draft'}
            
            elif action == 'start_progress':
                if current_state != 'approved':
                    return {'success': False, 'message': 'Can only start processing approved purchase orders'}
                
                # Move to in_progress state
                progress_state = WorkflowState.objects.get(
                    workflow=workflow_instance.workflow_definition,
                    name='in_progress'
                )
                workflow_instance.current_state = progress_state
                workflow_instance.save()
                
                obj.doc_status = 'in_progress'
                obj.save()
                
                return {'success': True, 'message': f'Purchase order {obj.document_no} processing started'}
            
            elif action == 'complete':
                if current_state != 'in_progress':
                    return {'success': False, 'message': 'Can only complete in-progress purchase orders'}
                
                # Move to complete state
                complete_state = WorkflowState.objects.get(
                    workflow=workflow_instance.workflow_definition,
                    name='complete'
                )
                workflow_instance.current_state = complete_state
                workflow_instance.save()
                
                obj.doc_status = 'complete'
                obj.date_received = timezone.now().date()  # Set received date
                obj.save()
                
                return {'success': True, 'message': f'Purchase order {obj.document_no} marked as complete'}
            
            elif action == 'close':
                if current_state != 'complete':
                    return {'success': False, 'message': 'Can only close completed purchase orders'}
                
                # Move to closed state
                closed_state = WorkflowState.objects.get(
                    workflow=workflow_instance.workflow_definition,
                    name='closed'
                )
                workflow_instance.current_state = closed_state
                workflow_instance.save()
                
                obj.doc_status = 'closed'
                obj.save()
                
                return {'success': True, 'message': f'Purchase order {obj.document_no} closed'}
            
            elif action == 'reactivate':
                if current_state not in ['approved', 'in_progress', 'complete', 'closed']:
                    return {'success': False, 'message': 'Cannot reactivate purchase order in current state'}
                
                # Check if user has reactivation permission
                if not has_permission('reactivate_documents'):
                    return {'success': False, 'message': 'You do not have permission to reactivate documents'}
                
                # Use the model's reactivate method
                result_message = obj.reactivate(user)
                
                return {'success': True, 'message': result_message}
            
            else:
                return {'success': False, 'message': f'Unknown action: {action}'}
        
        except WorkflowState.DoesNotExist:
            return {'success': False, 'message': 'Workflow state not found'}
        except Exception as e:
            return {'success': False, 'message': f'Error executing workflow action: {str(e)}'}


@admin.register(models.PurchaseOrderLine)
class PurchaseOrderLineAdmin(admin.ModelAdmin):
    list_display = ('order', 'line_no', 'product', 'charge', 'quantity_ordered', 'price_actual', 'line_net_amount')
    list_filter = ('order__organization', 'product__manufacturer')
    search_fields = ('order__document_no', 'product__manufacturer_part_number', 'product__name', 'vendor_product_no', 'description')


class VendorBillLineInline(admin.TabularInline):
    model = models.VendorBillLine
    extra = 0
    fields = ('line_no', 'product', 'charge', 'description', 'quantity_invoiced', 'price_entered', 'discount', 'line_net_amount')


@admin.register(models.VendorBill)
class VendorBillAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'opportunity', 'vendor_invoice_no', 'business_partner', 'date_invoiced', 'doc_status', 'invoice_type', 'grand_total', 'is_paid', 'is_1099')
    list_filter = ('doc_status', 'opportunity', 'invoice_type', 'organization', 'is_paid', 'is_posted', 'is_1099')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'vendor_invoice_no', 'business_partner__name', 'description')
    date_hierarchy = 'date_invoiced'
    inlines = [VendorBillLineInline]
    
    fieldsets = (
        ('Document Information', {
            'fields': ('organization', 'document_no', 'vendor_invoice_no', 'description', 'doc_status', 'invoice_type')
        }),
        ('Dates', {
            'fields': ('date_invoiced', 'date_accounting', 'due_date')
        }),
        ('Vendor', {
            'fields': ('business_partner', 'bill_to_address')
        }),
        ('References', {
            'fields': ('opportunity', 'purchase_order')
        }),
        ('Pricing', {
            'fields': ('price_list', 'currency', 'payment_terms', 'total_lines', 'tax_amount', 'grand_total', 'paid_amount', 'open_amount')
        }),
        ('Buyer', {
            'fields': ('buyer',)
        }),
        ('Flags', {
            'fields': ('is_printed', 'is_paid', 'is_posted', 'is_1099')
        }),
    )
    readonly_fields = ('total_lines', 'tax_amount', 'grand_total', 'paid_amount', 'open_amount')


@admin.register(models.VendorBillLine)
class VendorBillLineAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'line_no', 'product', 'charge', 'quantity_invoiced', 'price_actual', 'line_net_amount')
    list_filter = ('invoice__organization', 'product__manufacturer')
    search_fields = ('invoice__document_no', 'invoice__vendor_invoice_no', 'product__manufacturer_part_number', 'product__name', 'description')


class ReceiptLineInline(admin.TabularInline):
    model = models.ReceiptLine
    extra = 0
    fields = ('line_no', 'product', 'description', 'movement_quantity', 'quantity_entered', 'is_quality_checked')


@admin.register(models.Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'opportunity', 'business_partner', 'movement_date', 'doc_status', 'movement_type', 'warehouse', 'is_in_transit')
    list_filter = ('doc_status', 'opportunity', 'movement_type', 'organization', 'warehouse', 'is_in_transit')
    search_fields = ('document_no', 'opportunity__opportunity_number', 'business_partner__name', 'description', 'tracking_no')
    date_hierarchy = 'movement_date'
    inlines = [ReceiptLineInline]
    
    fieldsets = (
        ('Document Information', {
            'fields': ('organization', 'document_no', 'description', 'doc_status', 'movement_type')
        }),
        ('Dates', {
            'fields': ('movement_date', 'date_received')
        }),
        ('Business Partner & Warehouse', {
            'fields': ('business_partner', 'warehouse')
        }),
        ('References', {
            'fields': ('opportunity', 'purchase_order')
        }),
        ('Shipping', {
            'fields': ('delivery_via', 'tracking_no', 'freight_amount')
        }),
        ('Flags', {
            'fields': ('is_printed', 'is_in_transit')
        }),
    )


@admin.register(models.ReceiptLine)
class ReceiptLineAdmin(admin.ModelAdmin):
    list_display = ('receipt', 'line_no', 'product', 'movement_quantity', 'quantity_entered', 'is_quality_checked')
    list_filter = ('receipt__organization', 'product__manufacturer', 'is_quality_checked')
    search_fields = ('receipt__document_no', 'product__manufacturer_part_number', 'product__name', 'description')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('receipt', 'line_no', 'product', 'description')
        }),
        ('Quantities', {
            'fields': ('movement_quantity', 'quantity_entered')
        }),
        ('Quality Control', {
            'fields': ('is_quality_checked', 'quality_notes')
        }),
        ('References', {
            'fields': ('order_line',)
        }),
    )


@admin.register(models.Charge)
class ChargeAdmin(admin.ModelAdmin):
    list_display = ('name', 'charge_account', 'tax_category', 'is_active')
    list_filter = ('charge_account', 'tax_category', 'is_active')
    search_fields = ('name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Accounting', {
            'fields': ('charge_account', 'tax_category')
        }),
    )
