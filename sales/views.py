"""
Sales Views for Modern ERP

User-friendly views for managing the sales process:
- Customer order intake
- Sales order management with status tracking
- Multi-vendor PO generation
- Combined shipping/invoicing
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction, models
from django.utils import timezone
from decimal import Decimal
import json

from .models import SalesOrder, SalesOrderLine, Invoice, Shipment
from .utils import SalesOrderManager, create_customer_order_from_data, bulk_analyze_sales_orders
from core.models import BusinessPartner
from inventory.models import Product
from purchasing.models import PurchaseOrder


@login_required
def sales_dashboard(request):
    """Main sales dashboard with order status overview"""
    
    # Get sales orders with various statuses
    pending_orders = SalesOrder.objects.filter(doc_status='drafted').order_by('-date_ordered')
    in_progress_orders = SalesOrder.objects.filter(doc_status='in_progress').order_by('-date_ordered')
    
    # Orders needing purchase orders
    orders_needing_po = []
    for so in SalesOrder.objects.filter(doc_status__in=['drafted', 'in_progress']):
        manager = SalesOrderManager(so)
        requirements = manager.analyze_purchase_requirements()
        if any(len(items) > 0 for vendor, items in requirements.items()):
            orders_needing_po.append({
                'order': so,
                'vendors_needed': len([v for v in requirements.keys() if v is not None]),
                'items_without_vendor': len(requirements.get(None, [])),
            })
    
    # Orders ready to ship/invoice
    ready_to_ship = SalesOrder.objects.filter(
        doc_status='in_progress',
        lines__quantity_delivered__lt=models.F('lines__quantity_ordered')
    ).distinct()
    
    context = {
        'pending_orders': pending_orders[:10],
        'in_progress_orders': in_progress_orders[:10],
        'orders_needing_po': orders_needing_po[:10],
        'ready_to_ship': ready_to_ship[:10],
        'stats': {
            'total_pending': pending_orders.count(),
            'total_in_progress': in_progress_orders.count(),
            'total_needing_po': len(orders_needing_po),
            'total_ready_to_ship': ready_to_ship.count(),
        }
    }
    
    return render(request, 'sales/dashboard.html', context)


@login_required
def customer_order_intake(request):
    """Simple form for receiving customer orders"""
    
    if request.method == 'POST':
        try:
            # Get form data
            customer_id = request.POST.get('customer')
            customer_po = request.POST.get('customer_po')
            date_needed = request.POST.get('date_needed')
            ship_to_address = request.POST.get('ship_to_address')
            
            # Get customer
            customer = get_object_or_404(BusinessPartner, id=customer_id, is_customer=True)
            
            # Parse line items from form
            items = []
            item_count = int(request.POST.get('item_count', 0))
            
            for i in range(item_count):
                product_code = request.POST.get(f'item_{i}_product_code')
                quantity = request.POST.get(f'item_{i}_quantity')
                notes = request.POST.get(f'item_{i}_notes', '')
                
                if product_code and quantity:
                    items.append({
                        'product_code': product_code,
                        'quantity': float(quantity),
                        'notes': notes,
                    })
            
            # Create sales order
            order_data = {
                'customer_po': customer_po,
                'date_needed': date_needed,
                'ship_to_address': ship_to_address,
                'items': items,
            }
            
            sales_order = create_customer_order_from_data(customer, order_data, request.user)
            
            messages.success(request, f'Sales Order {sales_order.document_no} created successfully!')
            return redirect('sales:order_detail', order_id=sales_order.id)
            
        except Exception as e:
            messages.error(request, f'Error creating order: {str(e)}')
    
    # Get customers for dropdown
    customers = BusinessPartner.objects.filter(is_customer=True, is_active=True).order_by('name')
    products = Product.objects.filter(is_sold=True, is_active=True).order_by('code')
    
    context = {
        'customers': customers,
        'products': products,
    }
    
    return render(request, 'sales/customer_order_intake.html', context)


@login_required
def sales_order_detail(request, order_id):
    """Detailed view of a sales order with all tracking info"""
    
    order = get_object_or_404(SalesOrder, id=order_id)
    manager = SalesOrderManager(order)
    
    # Get purchase requirements and status
    requirements = manager.analyze_purchase_requirements()
    status = manager.get_status_summary()
    
    # Get related purchase orders
    related_pos = PurchaseOrder.objects.filter(
        lines__source_sales_order=order
    ).distinct().prefetch_related('lines', 'business_partner')
    
    # Get shipments
    shipments = Shipment.objects.filter(
        lines__sales_order_line__order=order
    ).distinct()
    
    # Get invoices
    invoices = Invoice.objects.filter(
        lines__sales_order_line__order=order
    ).distinct()
    
    context = {
        'order': order,
        'manager': manager,
        'requirements': requirements,
        'status': status,
        'related_pos': related_pos,
        'shipments': shipments,
        'invoices': invoices,
        'can_generate_po': any(len(items) > 0 for vendor, items in requirements.items() if vendor is not None),
        'items_without_vendor': requirements.get(None, []),
    }
    
    return render(request, 'sales/order_detail.html', context)


@login_required
@require_http_methods(["POST"])
def generate_purchase_orders(request, order_id):
    """Generate purchase orders for a sales order"""
    
    order = get_object_or_404(SalesOrder, id=order_id)
    manager = SalesOrderManager(order)
    
    try:
        with transaction.atomic():
            # Analyze requirements
            requirements = manager.analyze_purchase_requirements()
            
            # Generate POs
            created_pos = manager.generate_purchase_orders(requirements, request.user)
            
            if created_pos:
                po_numbers = [po.document_no for po in created_pos]
                messages.success(
                    request, 
                    f'Created {len(created_pos)} Purchase Orders: {", ".join(po_numbers)}'
                )
            else:
                messages.info(request, 'No purchase orders needed.')
    
    except Exception as e:
        messages.error(request, f'Error generating purchase orders: {str(e)}')
    
    return redirect('sales:order_detail', order_id=order.id)


@login_required
def quick_ship_invoice(request, order_id):
    """Quick ship and invoice - combined packing list and invoice generation"""
    
    order = get_object_or_404(SalesOrder, id=order_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get shipping data from form
                shipment_data = {}
                invoice_data = {}
                
                # Process each line for shipping quantities
                for line in order.lines.all():
                    ship_qty_key = f'ship_qty_{line.id}'
                    ship_qty = request.POST.get(ship_qty_key)
                    
                    if ship_qty and float(ship_qty) > 0:
                        shipment_data[line.id] = float(ship_qty)
                        invoice_data[line.id] = float(ship_qty)  # Invoice same quantity
                
                if shipment_data:
                    # Create shipment
                    shipment = _create_shipment_from_so(order, shipment_data, request.user)
                    
                    # Create invoice
                    invoice = _create_invoice_from_so(order, invoice_data, request.user)
                    
                    messages.success(
                        request,
                        f'Created Shipment {shipment.document_no} and Invoice {invoice.document_no}'
                    )
                    
                    # Redirect to combined view
                    return redirect('sales:ship_invoice_view', 
                                  shipment_id=shipment.id, 
                                  invoice_id=invoice.id)
                else:
                    messages.warning(request, 'No quantities specified for shipping.')
        
        except Exception as e:
            messages.error(request, f'Error creating shipment/invoice: {str(e)}')
    
    # Calculate available quantities
    lines_with_availability = []
    for line in order.lines.all():
        available_to_ship = line.quantity_ordered - line.quantity_delivered
        lines_with_availability.append({
            'line': line,
            'available_to_ship': available_to_ship,
        })
    
    context = {
        'order': order,
        'lines_with_availability': lines_with_availability,
    }
    
    return render(request, 'sales/quick_ship_invoice.html', context)


@login_required
def ship_invoice_combined_view(request, shipment_id, invoice_id):
    """Combined view showing shipment (packing list) and invoice for printing"""
    
    shipment = get_object_or_404(Shipment, id=shipment_id)
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    context = {
        'shipment': shipment,
        'invoice': invoice,
        'show_as_packing_list': True,
        'show_as_invoice': True,
    }
    
    return render(request, 'sales/ship_invoice_combined.html', context)


@login_required
def ajax_product_search(request):
    """AJAX endpoint for product search in order intake"""
    
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'products': []})
    
    products = Product.objects.filter(
        models.Q(code__icontains=query) | models.Q(name__icontains=query),
        is_sold=True,
        is_active=True
    )[:10]
    
    product_data = []
    for product in products:
        product_data.append({
            'code': product.code,
            'name': product.name,
            'list_price': str(product.list_price.amount),
            'has_vendor': product.primary_vendor is not None,
            'vendor_name': product.primary_vendor.name if product.primary_vendor else '',
        })
    
    return JsonResponse({'products': product_data})


@login_required
def purchase_requirements_report(request):
    """Report showing all sales orders and their purchase requirements"""
    
    # Get active sales orders
    orders = SalesOrder.objects.filter(
        doc_status__in=['drafted', 'in_progress']
    ).order_by('-date_ordered')
    
    # Analyze each order
    analysis = bulk_analyze_sales_orders(orders)
    
    # Summary statistics
    total_vendors_needed = set()
    total_items_without_vendor = 0
    
    for item in analysis:
        for vendor in item['requirements'].keys():
            if vendor is not None:
                total_vendors_needed.add(vendor)
        total_items_without_vendor += len(item['requirements'].get(None, []))
    
    context = {
        'analysis': analysis,
        'summary': {
            'total_orders': len(analysis),
            'orders_needing_po': len([a for a in analysis if any(len(items) > 0 for vendor, items in a['requirements'].items())]),
            'unique_vendors_needed': len(total_vendors_needed),
            'items_without_vendor': total_items_without_vendor,
        }
    }
    
    return render(request, 'sales/purchase_requirements_report.html', context)


# Helper functions

def _create_shipment_from_so(sales_order, line_quantities, user):
    """Create shipment from sales order with specified quantities"""
    # Implementation would create Shipment and ShipmentLine objects
    # This is a placeholder for the actual implementation
    pass


def _create_invoice_from_so(sales_order, line_quantities, user):
    """Create invoice from sales order with specified quantities"""
    # Implementation would create Invoice and InvoiceLine objects
    # This is a placeholder for the actual implementation
    pass