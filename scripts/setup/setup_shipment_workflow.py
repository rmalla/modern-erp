#!/usr/bin/env python3
"""
Shipment Workflow Setup Script

This script creates the workflow definition, states, and transitions for shipments
in the Modern ERP system, similar to the sales order workflow.
"""

import os
import django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from core.models import WorkflowDefinition, WorkflowState, WorkflowTransition, Organization, Currency


def setup_shipment_workflow():
    """Setup complete shipment workflow with states and transitions"""
    
    print("Setting up Shipment Workflow...")
    
    # Get default organization and currency
    default_org = Organization.objects.first()
    default_currency = Currency.objects.filter(iso_code='USD').first()
    
    # Create or get the workflow definition
    workflow_def, created = WorkflowDefinition.objects.get_or_create(
        document_type='shipment',
        defaults={
            'name': 'Standard Shipment Workflow',
            'initial_state': 'draft',
            'requires_approval': False,  # Shipments generally don't need approval
            'approval_threshold_amount': None,
            'approval_permission': 'shipment_approve',
            'reactivation_permission': 'shipment_reactivate'
        }
    )
    
    if created:
        print(f"✓ Created workflow definition: {workflow_def.name}")
    else:
        print(f"✓ Workflow definition already exists: {workflow_def.name}")
    
    # Define shipment workflow states
    shipment_states = [
        {
            'name': 'draft',
            'display_name': 'Draft',
            'order': 10,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#6c757d'
        },
        {
            'name': 'prepared',
            'display_name': 'Prepared',
            'order': 20,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#fd7e14'
        },
        {
            'name': 'in_transit',
            'display_name': 'In Transit',
            'order': 30,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#0d6efd'
        },
        {
            'name': 'delivered',
            'display_name': 'Delivered',
            'order': 40,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#20c997'
        },
        {
            'name': 'complete',
            'display_name': 'Complete',
            'order': 50,
            'is_final': True,
            'requires_approval': False,
            'color_code': '#198754'
        },
        {
            'name': 'returned',
            'display_name': 'Returned',
            'order': 45,
            'is_final': False,
            'requires_approval': False,
            'color_code': '#ffc107'
        },
        {
            'name': 'cancelled',
            'display_name': 'Cancelled',
            'order': 60,
            'is_final': True,
            'requires_approval': False,
            'color_code': '#495057'
        }
    ]
    
    # Create workflow states
    states_created = 0
    for state_data in shipment_states:
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
    shipment_transitions = [
        # From Draft
        {'from_state': 'draft', 'to_state': 'prepared', 'name': 'Prepare Shipment', 'button_color': 'blue'},
        {'from_state': 'draft', 'to_state': 'cancelled', 'name': 'Cancel', 'button_color': 'red'},
        
        # From Prepared
        {'from_state': 'prepared', 'to_state': 'in_transit', 'name': 'Ship', 'button_color': 'blue'},
        {'from_state': 'prepared', 'to_state': 'cancelled', 'name': 'Cancel', 'button_color': 'red'},
        
        # From In Transit
        {'from_state': 'in_transit', 'to_state': 'delivered', 'name': 'Mark Delivered', 'button_color': 'green'},
        {'from_state': 'in_transit', 'to_state': 'returned', 'name': 'Mark Returned', 'button_color': 'orange'},
        
        # From Delivered
        {'from_state': 'delivered', 'to_state': 'complete', 'name': 'Complete', 'button_color': 'green'},
        {'from_state': 'delivered', 'to_state': 'returned', 'name': 'Process Return', 'button_color': 'orange'},
        
        # From Returned
        {'from_state': 'returned', 'to_state': 'in_transit', 'name': 'Reship', 'button_color': 'blue'},
        {'from_state': 'returned', 'to_state': 'cancelled', 'name': 'Cancel Order', 'button_color': 'red'}
    ]
    
    # Create workflow transitions
    transitions_created = 0
    for transition_data in shipment_transitions:
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
    print(f"\nShipment Workflow Setup Complete!")
    print(f"Workflow: {workflow_def.name}")
    print(f"States: {WorkflowState.objects.filter(workflow=workflow_def).count()}")
    print(f"Transitions: {WorkflowTransition.objects.filter(workflow=workflow_def).count()}")
    print(f"Approval threshold: {workflow_def.approval_threshold_amount or 'None (no approval required)'}")


if __name__ == '__main__':
    setup_shipment_workflow()