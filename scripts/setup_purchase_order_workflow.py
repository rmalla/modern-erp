#!/usr/bin/env python
"""
Setup Purchase Order Workflow Configuration
Creates workflow definition, states, and transitions for purchase orders.
Based on the sales order workflow pattern.

Run with: python manage.py shell_plus < scripts/setup_purchase_order_workflow.py
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from decimal import Decimal
from core.models import (
    WorkflowDefinition, WorkflowState, WorkflowTransition, 
    Currency
)

def setup_purchase_order_workflow():
    """Create Purchase Order workflow configuration"""
    
    print("🔧 Setting up Purchase Order Workflow...")
    
    # Get or create USD currency for thresholds
    usd_currency, _ = Currency.objects.get_or_create(
        code='USD',
        defaults={'name': 'US Dollar', 'symbol': '$'}
    )
    
    # 1. Create Workflow Definition
    print("📋 Creating Purchase Order Workflow Definition...")
    
    po_workflow, created = WorkflowDefinition.objects.get_or_create(
        document_type='purchase_order',
        defaults={
            'name': 'Purchase Order Approval Workflow',
            'initial_state': 'draft',
            'requires_approval': True,
            'approval_threshold_amount': Decimal('5000.00'),  # $5000 threshold for POs
            'approval_permission': 'approve_purchase_orders',
            'reactivation_permission': 'reactivate_documents'
        }
    )
    
    if created:
        print(f"✅ Created workflow definition: {po_workflow.name}")
    else:
        print(f"🔄 Updated existing workflow: {po_workflow.name}")
    
    # 2. Create Workflow States
    print("🎨 Creating Workflow States...")
    
    states_config = [
        # name, display_name, color_code, order, is_final, requires_approval
        ('draft', 'Draft', '#6c757d', 0, False, False),
        ('pending_approval', 'Pending Approval', '#fd7e14', 1, False, True),
        ('approved', 'Approved', '#20c997', 2, False, False),
        ('in_progress', 'In Progress', '#0d6efd', 3, False, False),
        ('complete', 'Complete', '#198754', 4, False, False),
        ('closed', 'Closed', '#495057', 5, True, False),
        ('rejected', 'Rejected', '#dc3545', 6, False, False),
    ]
    
    for state_name, display_name, color, order, is_final, requires_approval in states_config:
        state, created = WorkflowState.objects.get_or_create(
            workflow=po_workflow,
            name=state_name,
            defaults={
                'display_name': display_name,
                'color_code': color,
                'order': order,
                'is_final': is_final,
                'requires_approval': requires_approval
            }
        )
        
        if created:
            print(f"  ✅ Created state: {display_name} ({color})")
        else:
            print(f"  🔄 Updated state: {display_name}")
    
    # 3. Create Workflow Transitions
    print("🔄 Creating Workflow Transitions...")
    
    # Get all states for transitions
    states = {s.name: s for s in WorkflowState.objects.filter(workflow=po_workflow)}
    
    transitions_config = [
        # from_state, to_state, name, required_permission, requires_approval, button_color
        ('draft', 'pending_approval', 'Submit for Approval', 'submit_for_approval', False, 'orange'),
        ('draft', 'approved', 'Auto-Approve & Start', 'approve_purchase_orders', False, 'green'),
        ('pending_approval', 'approved', 'Approve', 'approve_purchase_orders', False, 'green'),
        ('pending_approval', 'rejected', 'Reject', 'approve_purchase_orders', False, 'red'),
        ('pending_approval', 'draft', 'Return to Draft', '', False, 'gray'),
        ('approved', 'in_progress', 'Start Processing', '', False, 'blue'),
        ('approved', 'draft', 'Reactivate', 'reactivate_documents', False, 'orange'),
        ('in_progress', 'complete', 'Mark Complete', '', False, 'green'),
        ('in_progress', 'draft', 'Reactivate', 'reactivate_documents', False, 'orange'),
        ('complete', 'closed', 'Close', '', False, 'gray'),
        ('complete', 'in_progress', 'Reactivate', 'reactivate_documents', False, 'orange'),
        ('closed', 'in_progress', 'Reactivate', 'reactivate_documents', False, 'orange'),
        ('rejected', 'draft', 'Return to Draft', '', False, 'blue'),
    ]
    
    for from_name, to_name, action_name, permission, requires_approval, color in transitions_config:
        from_state = states.get(from_name)
        to_state = states.get(to_name)
        
        if from_state and to_state:
            transition, created = WorkflowTransition.objects.get_or_create(
                workflow=po_workflow,
                from_state=from_state,
                to_state=to_state,
                defaults={
                    'name': action_name,
                    'required_permission': permission,
                    'requires_approval': requires_approval,
                    'button_color': color
                }
            )
            
            if created:
                print(f"  ✅ Created transition: {from_name} → {to_name} ({action_name})")
            else:
                print(f"  🔄 Updated transition: {from_name} → {to_name}")
    
    print("\n🎉 Purchase Order Workflow Setup Complete!")
    print(f"📊 Created workflow with {len(states_config)} states and {len(transitions_config)} transitions")
    print(f"💰 Approval threshold: ${po_workflow.approval_threshold_amount}")
    print(f"🔐 Required permissions: {po_workflow.approval_permission}, {po_workflow.reactivation_permission}")
    
    return po_workflow

def verify_workflow():
    """Verify the workflow setup"""
    print("\n🔍 Verifying Purchase Order Workflow Setup...")
    
    try:
        workflow = WorkflowDefinition.objects.get(document_type='purchase_order')
        states = WorkflowState.objects.filter(workflow=workflow).count()
        transitions = WorkflowTransition.objects.filter(workflow=workflow).count()
        
        print(f"✅ Workflow Definition: {workflow.name}")
        print(f"✅ States: {states}")
        print(f"✅ Transitions: {transitions}")
        print(f"✅ Approval Threshold: ${workflow.approval_threshold_amount}")
        
        print("\n📋 Available States:")
        for state in WorkflowState.objects.filter(workflow=workflow).order_by('order'):
            print(f"  • {state.display_name} ({state.name}) - {state.color_code}")
        
        return True
        
    except WorkflowDefinition.DoesNotExist:
        print("❌ Purchase Order workflow not found!")
        return False

if __name__ == "__main__":
    try:
        workflow = setup_purchase_order_workflow()
        verify_workflow()
        print("\n✅ Setup completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()