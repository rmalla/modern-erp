"""
Invoice creation utilities for sales orders.
Handles automatic invoice generation from sales orders.
"""
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Invoice, InvoiceLine, SalesOrder
from core.models import Organization
from inventory.models import PriceList
import logging

logger = logging.getLogger(__name__)


def create_invoice_from_sales_order(sales_order, user=None):
    """
    Create an invoice from a sales order.
    
    Args:
        sales_order: SalesOrder instance
        user: User creating the invoice (optional)
    
    Returns:
        dict: Result with success status and invoice instance or error message
    """
    try:
        # Validate sales order
        if not sales_order:
            return {
                'success': False,
                'error': 'Sales order is required'
            }
        
        # Check if invoice already exists for this sales order
        existing_invoice = Invoice.objects.filter(sales_order=sales_order).first()
        if existing_invoice:
            return {
                'success': False,
                'error': f'Invoice already exists: {existing_invoice.document_no}',
                'existing_invoice': existing_invoice
            }
        
        # Get default organization
        organization = sales_order.organization
        
        # Generate invoice document number
        invoice_doc_no = generate_invoice_number(organization)
        
        # Get sales price list (default to first available)
        price_list = sales_order.price_list
        if not price_list:
            price_list = PriceList.objects.filter(is_sales_price_list=True).first()
            if not price_list:
                return {
                    'success': False,
                    'error': 'No sales price list found'
                }
        
        # Create invoice
        invoice = Invoice.objects.create(
            organization=organization,
            document_no=invoice_doc_no,
            description=f'Invoice for Sales Order {sales_order.document_no}',
            doc_status='drafted',  # Always start as drafted
            invoice_type='standard',
            
            # Dates
            date_invoiced=timezone.now().date(),
            date_accounting=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),  # Default 30 days
            
            # Business partner info (copy from sales order)
            business_partner=sales_order.business_partner,
            contact=sales_order.contact,
            internal_user=sales_order.internal_user,
            business_partner_location=sales_order.business_partner_location,
            bill_to_location=sales_order.bill_to_location,
            
            # References
            sales_order=sales_order,
            opportunity=sales_order.opportunity,
            
            # Pricing
            price_list=price_list,
            currency=sales_order.currency,
            payment_terms=sales_order.payment_terms.name if sales_order.payment_terms else 'Net 30',
            
            # Sales rep
            sales_rep=sales_order.internal_user,
            
            # Audit
            created_by=user,
            updated_by=user
        )
        
        # Create invoice lines from sales order lines
        total_amount = 0
        for so_line in sales_order.lines.all():
            invoice_line = InvoiceLine.objects.create(
                invoice=invoice,
                line_no=so_line.line_no,
                description=so_line.description,
                
                # Product/Charge
                product=so_line.product,
                charge=so_line.charge,
                
                # Reference to order line
                order_line=so_line,
                
                # Quantities
                quantity_invoiced=so_line.quantity_ordered,
                
                # Pricing (copy from sales order)
                price_entered=so_line.price_entered,
                price_actual=so_line.price_actual,
                discount=so_line.discount,
                line_net_amount=so_line.line_net_amount,
                
                # Tax
                tax=so_line.tax,
                tax_amount=so_line.tax_amount,
                
                # Audit
                created_by=user,
                updated_by=user
            )
            
            total_amount += invoice_line.line_net_amount.amount
        
        # Update invoice totals
        invoice.total_lines.amount = total_amount
        invoice.grand_total.amount = total_amount  # TODO: Add tax calculation
        invoice.open_amount.amount = total_amount
        invoice.save()
        
        logger.info(f"Successfully created invoice {invoice.document_no} from sales order {sales_order.document_no}")
        
        return {
            'success': True,
            'invoice': invoice,
            'message': f'Invoice {invoice.document_no} created successfully'
        }
        
    except Exception as e:
        logger.error(f"Error creating invoice from sales order {sales_order.document_no}: {str(e)}")
        return {
            'success': False,
            'error': f'Error creating invoice: {str(e)}'
        }


def generate_invoice_number(organization):
    """
    Generate the next invoice number for the organization.
    
    Args:
        organization: Organization instance
    
    Returns:
        str: Generated invoice number
    """
    # Simple invoice numbering - find the last invoice and increment
    last_invoice = Invoice.objects.filter(
        organization=organization
    ).order_by('-document_no').first()
    
    if last_invoice and last_invoice.document_no.isdigit():
        try:
            next_number = int(last_invoice.document_no) + 1
            return str(next_number).zfill(5)  # Pad to 5 digits
        except ValueError:
            pass
    
    # Default starting number
    return "10001"


def create_invoice_from_multiple_orders(sales_orders, user=None):
    """
    Create a single invoice from multiple sales orders.
    
    Args:
        sales_orders: List of SalesOrder instances
        user: User creating the invoice (optional)
    
    Returns:
        dict: Result with success status and invoice instance or error message
    """
    try:
        if not sales_orders:
            return {
                'success': False,
                'error': 'At least one sales order is required'
            }
        
        # Validate all sales orders have same customer
        first_order = sales_orders[0]
        for order in sales_orders[1:]:
            if order.business_partner != first_order.business_partner:
                return {
                    'success': False,
                    'error': 'All sales orders must have the same customer'
                }
        
        # Check if any orders already have invoices
        existing_invoices = []
        for order in sales_orders:
            existing = Invoice.objects.filter(sales_order=order).first()
            if existing:
                existing_invoices.append(f"{order.document_no} -> {existing.document_no}")
        
        if existing_invoices:
            return {
                'success': False,
                'error': f'Some orders already have invoices: {", ".join(existing_invoices)}'
            }
        
        # Get default organization from first order
        organization = first_order.organization
        
        # Generate invoice document number
        invoice_doc_no = generate_invoice_number(organization)
        
        # Create combined description
        order_numbers = [order.document_no for order in sales_orders]
        description = f'Invoice for Sales Orders: {", ".join(order_numbers)}'
        
        # Get price list from first order
        price_list = first_order.price_list
        if not price_list:
            price_list = PriceList.objects.filter(is_sales_price_list=True).first()
        
        # Create invoice (using data from first order)
        invoice = Invoice.objects.create(
            organization=organization,
            document_no=invoice_doc_no,
            description=description,
            doc_status='drafted',  # Always start as drafted
            invoice_type='standard',
            
            # Dates
            date_invoiced=timezone.now().date(),
            date_accounting=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            
            # Business partner info (from first order)
            business_partner=first_order.business_partner,
            contact=first_order.contact,
            internal_user=first_order.internal_user,
            business_partner_location=first_order.business_partner_location,
            bill_to_location=first_order.bill_to_location,
            
            # References (first order's opportunity)
            sales_order=first_order,  # Primary sales order
            opportunity=first_order.opportunity,
            
            # Pricing
            price_list=price_list,
            currency=first_order.currency,
            payment_terms=first_order.payment_terms.name if first_order.payment_terms else 'Net 30',
            
            # Sales rep
            sales_rep=first_order.internal_user,
            
            # Audit
            created_by=user,
            updated_by=user
        )
        
        # Create invoice lines from all sales orders
        total_amount = 0
        line_no = 10
        
        for order in sales_orders:
            for so_line in order.lines.all():
                invoice_line = InvoiceLine.objects.create(
                    invoice=invoice,
                    line_no=line_no,
                    description=f"[{order.document_no}] {so_line.description}",
                    
                    # Product/Charge
                    product=so_line.product,
                    charge=so_line.charge,
                    
                    # Reference to order line
                    order_line=so_line,
                    
                    # Quantities
                    quantity_invoiced=so_line.quantity_ordered,
                    
                    # Pricing
                    price_entered=so_line.price_entered,
                    price_actual=so_line.price_actual,
                    discount=so_line.discount,
                    line_net_amount=so_line.line_net_amount,
                    
                    # Tax
                    tax=so_line.tax,
                    tax_amount=so_line.tax_amount,
                    
                    # Audit
                    created_by=user,
                    updated_by=user
                )
                
                total_amount += invoice_line.line_net_amount.amount
                line_no += 10
        
        # Update invoice totals
        invoice.total_lines.amount = total_amount
        invoice.grand_total.amount = total_amount
        invoice.open_amount.amount = total_amount
        invoice.save()
        
        # Update all sales orders to reference this invoice
        for order in sales_orders[1:]:  # Skip first order, already set
            # Create additional reference (for tracking)
            pass  # The invoice lines already reference the order lines
        
        logger.info(f"Successfully created invoice {invoice.document_no} from {len(sales_orders)} sales orders")
        
        return {
            'success': True,
            'invoice': invoice,
            'message': f'Invoice {invoice.document_no} created from {len(sales_orders)} sales orders'
        }
        
    except Exception as e:
        logger.error(f"Error creating invoice from multiple sales orders: {str(e)}")
        return {
            'success': False,
            'error': f'Error creating invoice: {str(e)}'
        }