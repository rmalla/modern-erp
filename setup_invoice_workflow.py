#!/usr/bin/env python3
"""
Invoice Workflow Setup Script

This script creates the workflow definition, states, and transitions for invoices
in the Modern ERP system, similar to the sales order workflow.
"""

import os
import django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from core.models import WorkflowDefinition, WorkflowState, WorkflowTransition, Organization, Currency


def setup_invoice_workflow():
    """Setup complete invoice workflow with states and transitions"""
    
    print("Setting up Invoice Workflow...")
    
    # Get default organization and currency
    default_org = Organization.objects.first()
    default_currency = Currency.objects.filter(iso_code='USD').first()
    
    # Create or get the workflow definition
    workflow_def, created = WorkflowDefinition.objects.get_or_create(
        document_type='invoice',
        defaults={
            'name': 'Standard Invoice Workflow',
            'initial_state': 'draft',
            'requires_approval': True,
            'approval_threshold_amount': Decimal('1000.00'),  # $1000 threshold like sales orders
            'approval_permission': 'invoice_approve',
            'reactivation_permission': 'invoice_reactivate'
        }
    )
    
    if created:
        print(f"✓ Created workflow definition: {workflow_def.name}")
    else:
        print(f"✓ Workflow definition already exists: {workflow_def.name}")
    
    # Define invoice workflow states
    invoice_states = [
        {
            'name': 'draft',
            'display_name': 'Draft',
            'order': 10,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#6c757d'
        },
        {
            'name': 'pending_approval',
            'display_name': 'Pending Approval',
            'order': 20,
            'is_final': False,
            'requires_approval': True,
            'color_code': '#fd7e14'
        },
        {
            'name': 'approved',
            'display_name': 'Approved',
            'order': 30,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#20c997'
        },
        {
            'name': 'sent',
            'display_name': 'Sent',
            'order': 40,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#0d6efd'
        },
        {
            'name': 'partial_payment',
            'display_name': 'Partially Paid',
            'order': 50,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#ffc107'
        },
        {
            'name': 'paid',
            'display_name': 'Paid',
            'order': 60,
            'is_final': True,
            'requires_approval': False,
            'color_code': '#198754'
        },
        {
            'name': 'overdue',
            'display_name': 'Overdue',
            'order': 55,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#dc3545'
        },
        {
            'name': 'cancelled',
            'display_name': 'Cancelled',
            'order': 70,
            'is_final': True,
            'requires_approval': False,
            'color_code': '#495057'
        },
        {
            'name': 'rejected',
            'display_name': 'Rejected',
            'order': 25,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#dc3545'
        }
    ]
    
    # Create workflow states
    states_created = 0
    for state_data in invoice_states:
        state, created = WorkflowState.objects.get_or_create(
            workflow=workflow_def,
            name=state_data['name'],
            defaults={
                'display_name': state_data['display_name'],
                'order': state_data['order'],
                'is_final': state_data['is_final'],
                'requires_approval': state_data['requires_approval'],
                'color_code': state_data['color_code']
            }
        )
        
        if created:
            states_created += 1
            print(f"  ✓ Created state: {state.display_name}")
        else:
            print(f"  • State already exists: {state.display_name}")
    
    print(f"✓ Created {states_created} new workflow states")
    
    # Get states for creating transitions
    states = {state.name: state for state in WorkflowState.objects.filter(workflow=workflow_def)}
    
    # Define basic workflow transitions
    invoice_transitions = [
        # From Draft
        {'from_state': 'draft', 'to_state': 'pending_approval', 'name': 'Submit for Approval', 'button_color': 'orange'},
        {'from_state': 'draft', 'to_state': 'approved', 'name': 'Auto Approve', 'button_color': 'green'},
        {'from_state': 'draft', 'to_state': 'cancelled', 'name': 'Cancel', 'button_color': 'red'},
        
        # From Pending Approval
        {'from_state': 'pending_approval', 'to_state': 'approved', 'name': 'Approve', 'button_color': 'green'},
        {'from_state': 'pending_approval', 'to_state': 'rejected', 'name': 'Reject', 'button_color': 'red'},
        
        # From Approved
        {'from_state': 'approved', 'to_state': 'sent', 'name': 'Send to Customer', 'button_color': 'blue'},
        {'from_state': 'approved', 'to_state': 'cancelled', 'name': 'Cancel', 'button_color': 'red'},
        
        # From Sent
        {'from_state': 'sent', 'to_state': 'paid', 'name': 'Record Payment', 'button_color': 'green'},
        {'from_state': 'sent', 'to_state': 'partial_payment', 'name': 'Partial Payment', 'button_color': 'orange'},
        {'from_state': 'sent', 'to_state': 'overdue', 'name': 'Mark Overdue', 'button_color': 'red'},
        
        # From Partial Payment
        {'from_state': 'partial_payment', 'to_state': 'paid', 'name': 'Complete Payment', 'button_color': 'green'},
        {'from_state': 'partial_payment', 'to_state': 'overdue', 'name': 'Mark Overdue', 'button_color': 'red'},
        
        # From Overdue
        {'from_state': 'overdue', 'to_state': 'paid', 'name': 'Record Payment', 'button_color': 'green'},
        {'from_state': 'overdue', 'to_state': 'partial_payment', 'name': 'Partial Payment', 'button_color': 'orange'},
        
        # From Rejected
        {'from_state': 'rejected', 'to_state': 'draft', 'name': 'Return to Draft', 'button_color': 'blue'},
        {'from_state': 'rejected', 'to_state': 'cancelled', 'name': 'Cancel', 'button_color': 'red'}
    ]
    
    # Create workflow transitions
    transitions_created = 0
    for transition_data in invoice_transitions:
        from_state = states.get(transition_data['from_state'])
        to_state = states.get(transition_data['to_state'])
        
        if from_state and to_state:
            transition, created = WorkflowTransition.objects.get_or_create(
                workflow=workflow_def,
                from_state=from_state,
                to_state=to_state,
                defaults={
                    'name': transition_data['name'],
                    'required_permission': transition_data.get('required_permission', ''),
                    'requires_approval': transition_data.get('requires_approval', False),
                    'button_color': transition_data.get('button_color', 'blue')
                }
            )
            
            if created:
                transitions_created += 1
                print(f"  ✓ Created transition: {transition.name} ({from_state.name} → {to_state.name})")
            else:
                print(f"  • Transition already exists: {transition.name}")
    
    print(f"✓ Created {transitions_created} new workflow transitions")
    
    # Summary
    print(f"\nInvoice Workflow Setup Complete!")
    print(f"Workflow: {workflow_def.name}")
    print(f"States: {WorkflowState.objects.filter(workflow=workflow_def).count()}")
    print(f"Transitions: {WorkflowTransition.objects.filter(workflow=workflow_def).count()}")
    print(f"Approval threshold: {workflow_def.approval_threshold_amount}")


if __name__ == '__main__':
    setup_invoice_workflow()