"""
Sales Views for Modern ERP

User-friendly views for managing the sales process:
- Customer order intake
- Sales order management with status tracking
- Multi-vendor PO generation
- Combined shipping/invoicing

Updated: 2025-06-24 12:52 - Added proper labels for Order Number and Order Date in header
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
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image, PageTemplate, Frame
from reportlab.platypus.frames import Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY

from .models import SalesOrder, SalesOrderLine, Invoice, Shipment
from .utils import SalesOrderManager, create_customer_order_from_data, bulk_analyze_sales_orders
from core.models import BusinessPartner
from core.cache_utils import cached_function, TIMEOUT_SHORT, TIMEOUT_MEDIUM
from inventory.models import Product
from purchasing.models import PurchaseOrder
from django.core.cache import cache


@cached_function(timeout=TIMEOUT_SHORT, prefix="dashboard_pending_orders")
def get_pending_orders():
    """Get pending orders with caching."""
    return list(SalesOrder.objects.filter(doc_status='drafted').order_by('-date_ordered')[:20])


@cached_function(timeout=TIMEOUT_SHORT, prefix="dashboard_in_progress_orders")
def get_in_progress_orders():
    """Get in-progress orders with caching."""
    return list(SalesOrder.objects.filter(doc_status='in_progress').order_by('-date_ordered')[:20])


@cached_function(timeout=TIMEOUT_MEDIUM, prefix="dashboard_orders_needing_po")
def get_orders_needing_po():
    """Get orders needing purchase orders with caching."""
    orders_needing_po = []
    for so in SalesOrder.objects.filter(doc_status__in=['drafted', 'in_progress'])[:50]:
        manager = SalesOrderManager(so)
        requirements = manager.analyze_purchase_requirements()
        if any(len(items) > 0 for vendor, items in requirements.items()):
            orders_needing_po.append({
                'order': so,
                'requirements': requirements,
                'total_needed': sum(len(items) for items in requirements.values())
            })
    return orders_needing_po


@cached_function(timeout=TIMEOUT_SHORT, prefix="dashboard_stats")
def get_dashboard_stats():
    """Get dashboard statistics with caching."""
    return {
        'total_orders': SalesOrder.objects.count(),
        'pending_orders': SalesOrder.objects.filter(doc_status='drafted').count(),
        'in_progress_orders': SalesOrder.objects.filter(doc_status='in_progress').count(),
        'completed_orders': SalesOrder.objects.filter(doc_status='complete').count(),
        'total_invoices': Invoice.objects.count(),
        'unpaid_invoices': Invoice.objects.filter(is_paid=False).count(),
    }


@login_required
def sales_dashboard(request):
    """Main sales dashboard with order status overview"""
    
    # Use cached data for better performance
    pending_orders = get_pending_orders()
    in_progress_orders = get_in_progress_orders()
    orders_needing_po = get_orders_needing_po()
    stats = get_dashboard_stats()
    
    # Check if user requested cache refresh
    if request.GET.get('refresh_cache'):
        # Clear dashboard caches
        get_pending_orders.cache_clear()
        get_in_progress_orders.cache_clear()
        get_orders_needing_po.cache_clear()
        get_dashboard_stats.cache_clear()
        messages.success(request, "Dashboard cache refreshed successfully.")
        return redirect('sales:dashboard')
    
    # Legacy code for orders needing PO (keeping for backward compatibility)
    legacy_orders_needing_po = []
    if not orders_needing_po:  # If cache is empty, fall back to legacy method
        for so in SalesOrder.objects.filter(doc_status__in=['drafted', 'in_progress'])[:10]:
            manager = SalesOrderManager(so)
            requirements = manager.analyze_purchase_requirements()
            if any(len(items) > 0 for vendor, items in requirements.items()):
                legacy_orders_needing_po.append({
                'order': so,
                'vendors_needed': len([v for v in requirements.keys() if v is not None]),
                'items_without_vendor': len(requirements.get(None, [])),
            })
    
    # Orders ready to ship/invoice (use cache for this too)
    ready_to_ship_key = "dashboard_ready_to_ship"
    ready_to_ship = cache.get(ready_to_ship_key)
    if ready_to_ship is None:
        ready_to_ship = list(SalesOrder.objects.filter(
            doc_status='in_progress',
            lines__quantity_delivered__lt=models.F('lines__quantity_ordered')
        ).distinct()[:20])
        cache.set(ready_to_ship_key, ready_to_ship, TIMEOUT_SHORT)
    
    context = {
        'pending_orders': pending_orders[:10],
        'in_progress_orders': in_progress_orders[:10],
        'orders_needing_po': (orders_needing_po or legacy_orders_needing_po)[:10],
        'ready_to_ship': ready_to_ship[:10],
        'stats': {
            'total_orders': stats['total_orders'],
            'total_pending': stats['pending_orders'],
            'total_in_progress': stats['in_progress_orders'],
            'total_completed': stats['completed_orders'],
            'total_invoices': stats['total_invoices'],
            'unpaid_invoices': stats['unpaid_invoices'],
            'total_needing_po': len(orders_needing_po or legacy_orders_needing_po),
            'total_ready_to_ship': len(ready_to_ship),
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


def footer_canvas(canvas, doc):
    """Add footer to each page"""
    canvas.saveState()
    
    # Company information and contact details
    company_name = "Malla Group LLC"
    company_address = "1430 Brickell Bay Drive Unit 701, Miami, FL 33131, United States"
    contact_info = "+1 (305) 3954925 - orders@malla-group.com"
    
    # Set font and size
    canvas.setFont('Helvetica-Bold', 10)
    canvas.setFillColor(colors.HexColor('#666666'))
    
    # Page dimensions
    page_width = letter[0]
    
    # Draw company name (centered, top line)
    company_width = canvas.stringWidth(company_name, 'Helvetica-Bold', 10)
    x = (page_width - company_width) / 2
    y = 0.5 * inch
    canvas.drawString(x, y, company_name)
    
    # Draw address (centered, middle line)
    canvas.setFont('Helvetica', 9)
    address_width = canvas.stringWidth(company_address, 'Helvetica', 9)
    x = (page_width - address_width) / 2
    y = 0.37 * inch
    canvas.drawString(x, y, company_address)
    
    # Draw contact info (centered, bottom line)
    contact_width = canvas.stringWidth(contact_info, 'Helvetica', 9)
    x = (page_width - contact_width) / 2
    y = 0.24 * inch
    canvas.drawString(x, y, contact_info)
    
    # Add page number
    page_num = canvas.getPageNumber()
    canvas.setFont('Helvetica', 8)
    canvas.drawRightString(page_width - 0.5*inch, y, f"Page {page_num}")
    
    canvas.restoreState()


@login_required
def sales_order_pdf(request, order_id):
    """Generate PDF for a sales order"""
    order = get_object_or_404(SalesOrder, id=order_id)
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="SO_{order.document_no}.pdf"'
    
    # Create the PDF object using BytesIO
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        topMargin=0.5*inch, 
        bottomMargin=0.75*inch,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        title=f"Sales Order {order.document_no}",
        author="Malla Group LLC"
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12
    )
    company_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#333333')
    )
    
    # Create header with logo and company info
    header_data = []
    
    # Try to add logo
    import os
    logo_path = '/opt/modern-erp/modern-erp/static/images/company_logo.png'
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2*inch, height=1*inch, hAlign='LEFT')
        logo._restrictSize(2*inch, 1*inch)
    else:
        logo = Paragraph("Malla Group LLC", styles['Heading2'])
    
    # Create a special style for SALES ORDER title in header
    title_header_style = ParagraphStyle(
        'TitleHeader',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a5490'),
        alignment=TA_RIGHT,
        spaceAfter=10
    )
    
    # Order info style for below title
    order_info_style = ParagraphStyle(
        'OrderInfo',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_RIGHT,
        spaceAfter=5
    )
    
    # Create sales order title with order number and date below it
    sales_order_title = Paragraph("SALES ORDER", title_header_style)
    order_info = f"<b>Order Number:</b> SO #{order.document_no}<br/><b>Order Date:</b> {order.date_ordered.strftime('%Y-%m-%d') if order.date_ordered else ''}"
    order_info_para = Paragraph(order_info, order_info_style)
    
    # Create a nested table for the right column (title + order info only)
    right_column = Table([
        [sales_order_title],
        [order_info_para]
    ], colWidths=[4*inch])
    right_column.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    header_table = Table([[logo, right_column]], colWidths=[4*inch, 4*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Order header information
    # Format contact info as "Name (email)"
    customer_contact_info = ''
    if order.contact:
        customer_contact_info = order.contact.name
        if order.contact.email:
            customer_contact_info += f" ({order.contact.email})"
    
    malla_contact_info = ''
    if order.internal_user:
        malla_contact_info = order.internal_user.get_full_name()
        if order.internal_user.email:
            malla_contact_info += f" ({order.internal_user.email})"
    
    # Build header data starting with core fields (removed Order Number and Date since they're now in title area)
    header_data = [
        ['Customer:', order.business_partner.name if order.business_partner else '', 'Customer PO:', order.customer_po_reference or ''],
        ['Customer Contact:', customer_contact_info, '', ''],
        ['Malla Contact:', malla_contact_info, '', ''],
    ]
    
    # Add project number at the beginning if opportunity exists
    if order.opportunity:
        project_number = order.opportunity.opportunity_number
        if order.opportunity.name:
            project_number += f" - {order.opportunity.name}"
        header_data.insert(0, ['Project Number:', project_number, '', ''])
    
    incoterms_row = None
    if order.payment_terms:
        header_data.append(['Payment Terms:', order.payment_terms.name, '', ''])
    
    if order.incoterms:
        incoterms_row = len(header_data)  # Track which row contains Incoterms
        header_data.append(['Incoterms:', f"{order.incoterms.code} - {order.incoterms_location or ''}", '', ''])
    
    if order.estimated_delivery_weeks:
        weeks_text = f"{order.estimated_delivery_weeks} Week{'s' if order.estimated_delivery_weeks != 1 else ''}"
        header_data.append(['Estimated Delivery:', weeks_text, '', ''])
    
    header_table = Table(header_data, colWidths=[1.5*inch, 3.5*inch, 1.5*inch, 1.5*inch])
    
    # Base table style
    table_style = [
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONT', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    
    # Add yellow background for Incoterms row if it exists
    if incoterms_row is not None:
        table_style.append(('BACKGROUND', (0, incoterms_row), (-1, incoterms_row), colors.yellow))
    
    header_table.setStyle(TableStyle(table_style))
    elements.append(header_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # Addresses - Bill To and Ship To side by side (no title)
    if order.bill_to_location or order.ship_to_location:
        # Get address text
        bill_to_text = order.bill_to_location.full_address if order.bill_to_location else 'Not specified'
        ship_to_text = order.ship_to_location.full_address if order.ship_to_location else 'Not specified'
        
        # Create side-by-side layout
        address_data = [[
            Paragraph('<b>Bill To:</b><br/>' + bill_to_text.replace('\n', '<br/>'), styles['Normal']),
            Paragraph('<b>Ship To:</b><br/>' + ship_to_text.replace('\n', '<br/>'), styles['Normal'])
        ]]
        
        address_table = Table(address_data, colWidths=[4*inch, 4*inch])
        address_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(address_table)
    
    elements.append(Spacer(1, 0.1*inch))
    
    # Order lines (removed "Order Details" title to move table higher)
    
    # Table header - Removed Description column, fixed layout
    line_data = [['Line', 'Product', 'Manufacturer', 'Part Number', 'Qty', 'UOM', 'Unit Price', 'Total']]
    
    # Add order lines
    order_lines = order.lines.all().order_by('line_no')
    if order_lines.exists():
        for line in order_lines:
            # Extract product information
            product_name = ''
            manufacturer_name = ''
            part_number = ''
            
            if line.product:
                product_name = line.product.name or ''
                manufacturer_name = line.product.manufacturer.name if line.product.manufacturer else ''
                part_number = line.product.manufacturer_part_number or ''
            elif line.charge:
                product_name = line.charge.name
                manufacturer_name = ''
                part_number = ''
            
            line_data.append([
                str(line.line_no),
                product_name,
                manufacturer_name,
                part_number,
                f"{line.quantity_ordered:,.2f}",
                line.product.uom.code if line.product and line.product.uom else '',
                f"${line.price_entered.amount:,.2f}" if line.price_entered else '',
                f"${line.line_net_amount.amount:,.2f}" if line.line_net_amount else ''
            ])
    else:
        # Add a row indicating no items (8 columns now)
        line_data.append(['', 'No line items found', '', '', '', '', '', ''])
    
    # Updated column widths for 8 columns to fill full document width (8.0 inches total)
    # Line, Product, Manufacturer, Part Number, Qty, UOM, Unit Price, Total
    invoice_col_widths = [0.5*inch, 2.2*inch, 1.4*inch, 1.2*inch, 0.6*inch, 0.5*inch, 0.8*inch, 0.8*inch]

    # Create table with optimized column widths (8 columns, fits in 8.0" content area)
    # Use Paragraph objects for text wrapping to prevent overflow
    
    # Convert text fields to Paragraph objects to prevent overflow
    processed_line_data = []
    for i, row in enumerate(line_data):
        if i == 0:  # Header row
            processed_line_data.append(row)
        else:
            # Convert product name and manufacturer to Paragraph objects for wrapping
            product_para = Paragraph(str(row[1]), styles['Normal']) if row[1] else ''
            manufacturer_para = Paragraph(str(row[2]), styles['Normal']) if row[2] else ''
            part_number_para = Paragraph(str(row[3]), styles['Normal']) if row[3] else ''
            
            processed_row = [
                row[0],  # Line number
                product_para,  # Product (wrapped)
                manufacturer_para,  # Manufacturer (wrapped)
                part_number_para,  # Part Number (wrapped)
                row[4],  # Qty
                row[5],  # UOM
                row[6],  # Unit Price
                row[7],  # Total
            ]
            processed_line_data.append(processed_row)
    
    line_table = Table(processed_line_data, colWidths=invoice_col_widths)
    
    # Apply table style
    line_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows
        ('FONT', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('VALIGN', (0, 1), (-1, -1), 'TOP'),
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'),  # Qty
        ('ALIGN', (6, 1), (6, -1), 'RIGHT'),  # Unit Price
        ('ALIGN', (7, 1), (7, -1), 'RIGHT'),  # Total
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.grey),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
        
        # Add padding inside cells
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ALIGN', (0, 0), (3, -1), 'LEFT'),  # Force left align for first 4 columns
    ]))
    
    # Wrap table in a left-aligned container
    from reportlab.platypus import KeepTogether
    table_container = KeepTogether([line_table])
    elements.append(table_container)
    elements.append(Spacer(1, 0.2*inch))
    
    # Totals - align with the new 8-column structure
    totals_data = []
    if order.total_lines:
        totals_data.append(['', '', '', '', '', '', 'Subtotal:', f"${order.total_lines.amount:,.2f}"])
    if hasattr(order, 'tax_amount') and order.tax_amount:
        totals_data.append(['', '', '', '', '', '', 'Tax:', f"${order.tax_amount.amount:,.2f}"])
    if order.grand_total:
        totals_data.append(['', '', '', '', '', '', 'Total:', f"${order.grand_total.amount:,.2f}"])
    
    if totals_data:
        totals_table = Table(totals_data, colWidths=invoice_col_widths)
        totals_table.setStyle(TableStyle([
            ('ALIGN', (6, 0), (6, -1), 'RIGHT'),  # Labels aligned right
            ('ALIGN', (7, 0), (7, -1), 'RIGHT'),  # Values aligned right
            ('FONT', (6, -1), (-1, -1), 'Helvetica-Bold'),  # Bold total line
            ('FONTSIZE', (6, 0), (-1, -1), 11),
            ('LINEABOVE', (6, -1), (-1, -1), 2, colors.HexColor('#1a5490')),
            ('TOPPADDING', (6, -1), (-1, -1), 10),
            # Add padding to totals section
            ('LEFTPADDING', (6, 0), (-1, -1), 4),
            ('RIGHTPADDING', (6, 0), (-1, -1), 4),
        ]))
        elements.append(totals_table)
    
    # Notes/Description
    if order.description:
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("Notes", heading_style))
        elements.append(Paragraph(order.description, styles['Normal']))
    
    # Add page break for Terms and Conditions
    elements.append(PageBreak())
    
    # Terms and Conditions Page
    elements.append(Paragraph("TERMS AND CONDITIONS", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Get dynamic values for placeholders
    current_date = order.date_ordered.strftime('%B %d, %Y') if order.date_ordered else "Date TBD"
    buyer_name = order.business_partner.name if order.business_partner else "BUYER NAME"
    proposal_number = order.opportunity.opportunity_number if order.opportunity else "PROPOSAL NUMBER"
    incoterm_text = f"{order.incoterms.code} {order.incoterms_location}" if order.incoterms and order.incoterms_location else "INCOTERM LOCATION"
    
    # Terms and Conditions text with dynamic placeholders
    terms_text = f"""This SALES ORDER is presented {current_date} between MALLA Group LLC, located in 1430 Brickell Bay Drive UNIT 701 Miami, Florida 33131, USA (THE SELLER), and {buyer_name} (THE BUYER), for the purchase of the goods described on the Proposal Number {proposal_number} above. This proposal contains all the terms of the sale including, description (Manufacturer and Part Number), quantities, payment terms, incoterms, estimated delivery dates and validity.

<b>01. TERMS.</b> THE SELLER is responsible to deliver the goods to THE BUYER according to the Manufacturer and Part Number, Incoterms, Estimated Delivery Date and established payment terms. The Descriptions are ONLY for reference, what completely defines the product that is being purchased are the MANUFACTURER and the PART NUMBER.

<b>02. CHANGES.</b> Once this document is approved by THE BUYER, no changes to the order are allowed, nor the order can be cancelled. No returns are allowed for reasons other a defect on the product upon arrival.

<b>03. RISK OF LOSS OR DAMAGE.</b> The risk, of damage or loss, independent of the source, is THE SELLER's responsibility ONLY until the goods are delivered according to the Incoterms established on this SALES ORDER (The Incoterm for this order is {incoterm_text}). Once the goods are delivered according to the Incoterm, ALL responsibility over the goods are exclusively of the BUYER.

<b>04. ACCEPTANCE.</b> THE BUYER will need to notify the THE SELLER of any claim of damage or loss, quality or grade of the delivered goods, within 5 business days from the date of delivery. Inaction from the BUYER after this timeframe will mean the IRREVOCABLE acceptance of the goods from the BUYER. All claims and communications on this topic between parties need to be made in writing.

<b>05. PAYMENT TERMS.</b> Once a Commercial Invoice is issued, if credit (financing) is offered, the credit days will be counted starting from the day the Invoice is issued. Any delay on the payment will incur in a 2% late fee for every delayed week.

<b>06. WARRANTY.</b> THE SELLER ensures that the purchased products are free of substantial manufacturing details. THE SELLER's responsibility under this warranty is LIMITED to a supporting role, assisting THE BUYER to execute the warranty directly with the manufacturer. Any repair or replacement of damaged parts are to be processed directly with the manufacturer. THE SELLER is responsible to facilitate communication and assist on warranty claims according to each manufacturer's policy (if they offer warranty). It is possible that a specific manufacturer does not offer warranty or requires a re-stocking fee or other fees to process the warranty, if this is the case, THE SELLER will have to assume those terms. THE SELLER does not explicitly or implicitly assumes any other responsibility other than what is established above.

<b>07. TAXES.</b> All sales taxes, tariffs, and other governmental charges shall be paid by THE BUYER and are Buyer's Responsibility Except As Limited By Law.

<b>08. GOVERNING LAW.</b> This Contract shall be governed by the laws of the State of Florida, United States of America. Any disputes hereunder will be heard in the appropriate federal and state courts located in Florida, United States of America.

<b>09. FORCE MAJEURE.</b> THE SELLER may, without liability, delay performance or cancel this Contract on account of force majeure events or other circumstances beyond its control, including, but not limited to, strikes, acts of God, political unrest, embargo, failure of source of supply, or casualty.

<b>10. MISCELLANEOUS.</b> This Contract contains the entire agreement between the parties and supersedes and replaces all such prior agreements with respect to matters expressly set forth herein. No modification shall be made to this Contract except in writing and signed by both parties. This Contract shall be binding upon the parties and their respective heirs, executors, administrators, successors, assigns and personal representatives.

<b>11. ENTIRE AGREEMENT.</b> The parties intend this writing to be the final expression of the terms of their agreement and further intend that this writing be the complete and exclusive statement of all the terms of their agreement.

<b>12. LEGAL EXPENSE.</b> In any litigation, arbitration, or other proceeding by which one party either seeks to enforce its rights under this Sales Contract or seeks a declaration of any rights or obligations under this Sales Contract, the prevailing party shall be awarded reasonable attorney fees, together with any costs and expenses, to resolve the dispute and to enforce the final judgment."""
    
    # Create terms paragraph with smaller font and justified text
    terms_style = ParagraphStyle(
        'TermsStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        leftIndent=0,
        rightIndent=0
    )
    
    elements.append(Paragraph(terms_text, terms_style))
    
    # Build PDF with custom footer
    doc.build(elements, onFirstPage=footer_canvas, onLaterPages=footer_canvas)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response


@login_required
def invoice_pdf(request, invoice_id):
    """Generate PDF for an invoice"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="INV_{invoice.document_no}.pdf"'
    
    # Create the PDF object using BytesIO
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        topMargin=0.5*inch, 
        bottomMargin=0.75*inch,
        title=f"Invoice {invoice.document_no}",
        author="Malla Group LLC"
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12
    )
    company_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#333333')
    )
    
    # Create header with logo and company info
    header_data = []
    
    # Try to add logo
    import os
    logo_path = '/opt/modern-erp/modern-erp/static/images/company_logo.png'
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2*inch, height=1*inch, hAlign='LEFT')
        logo._restrictSize(2*inch, 1*inch)
    else:
        logo = Paragraph("Malla Group LLC", styles['Heading2'])
    
    # Create a special style for INVOICE title in header
    title_header_style = ParagraphStyle(
        'TitleHeader',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a5490'),
        alignment=TA_RIGHT,
        spaceAfter=10
    )
    
    # Company information with styled INVOICE title
    invoice_title = Paragraph("INVOICE", title_header_style)
    company_info = """<b>Malla Group LLC</b><br/>
    1430 Brickell Bay Drive Unit 701<br/>
    Miami, FL, 33131<br/>
    United States"""

    # Invoice number and date (right-aligned, more prominent)
    invoice_number_date_style = ParagraphStyle(
        'InvoiceNumberDate',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_RIGHT,
        spaceAfter=6,
        textColor=colors.HexColor('#333333')
    )
    invoice_number_date = Paragraph(
        f"<b>Invoice Number:</b> {invoice.document_no}<br/><b>Date:</b> {invoice.date_invoiced.strftime('%B %d, %Y')}",
        invoice_number_date_style
    )

    # Create a nested table for the right column (title, address, invoice number/date)
    right_column = Table([
        [invoice_title],
        [Paragraph(company_info, company_style)],
        [invoice_number_date],
    ], colWidths=[4*inch])
    right_column.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (2, 0), (2, 0), 12),  # More space above invoice number/date
        ('BOTTOMPADDING', (1, 0), (1, 0), 8),  # Space after company info
    ]))

    header_table = Table([[logo, right_column]], colWidths=[4*inch, 4*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))

    # --- MAIN DETAILS TABLE CHANGES ---
    header_data = []

    # Project Reference (was Project Number)
    if invoice.opportunity:
        project_reference = invoice.opportunity.opportunity_number
        if invoice.opportunity.name:
            project_reference += f" - {invoice.opportunity.name}"
        header_data.append([
            Paragraph('<b>Project Reference:</b>', styles['Normal']),
            Paragraph(project_reference, styles['Normal']),
            '', ''
        ])

    # Customer Information
    header_data.append([
        Paragraph('<b>Customer:</b>', styles['Normal']),
        Paragraph(invoice.business_partner.name, styles['Normal']),
        '', ''
    ])
    
    # Payment Terms
    if invoice.payment_terms:
        payment_terms_text = invoice.payment_terms.name if hasattr(invoice.payment_terms, 'name') else str(invoice.payment_terms)
        header_data.append([
            Paragraph('<b>Payment Terms:</b>', styles['Normal']),
            Paragraph(payment_terms_text, styles['Normal']),
            '', ''
        ])

    # Customer PO Reference (from related sales order)
    customer_po_ref = None
    if invoice.sales_order and invoice.sales_order.customer_po_reference:
        customer_po_ref = invoice.sales_order.customer_po_reference
    
    if customer_po_ref:
        header_data.append([
            Paragraph('<b>Customer PO:</b>', styles['Normal']),
            Paragraph(customer_po_ref, styles['Normal']),
            '', ''
        ])

    # Internal Contact
    if invoice.internal_user:
        header_data.append([
            Paragraph('<b>Internal Contact:</b>', styles['Normal']),
            Paragraph(f"{invoice.internal_user.first_name} {invoice.internal_user.last_name}", styles['Normal']),
            '', ''
        ])

    # Customer Contact
    if invoice.contact:
        contact_info = invoice.contact.name
        if invoice.contact.email:
            contact_info += f" ({invoice.contact.email})"
        header_data.append([
            Paragraph('<b>Customer Contact:</b>', styles['Normal']),
            Paragraph(contact_info, styles['Normal']),
            '', ''
        ])

    # Create the header details table if we have data
    if header_data:
        header_table = Table(header_data, colWidths=[1.5*inch, 2.5*inch, 1.5*inch, 2.5*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.2*inch))

    # Bill To and Ship To Addresses
    bill_to_address = ""
    ship_to_address = ""
    
    if invoice.bill_to_location:
        bill_to_address = invoice.bill_to_location.full_address_with_name
    elif invoice.business_partner_location:
        bill_to_address = invoice.business_partner_location.full_address_with_name

    # Get ship_to from related sales order since invoice doesn't have ship_to_location
    if invoice.sales_order and hasattr(invoice.sales_order, 'ship_to_location') and invoice.sales_order.ship_to_location:
        ship_to_address = invoice.sales_order.ship_to_location.full_address_with_name
    elif invoice.business_partner_location:
        ship_to_address = invoice.business_partner_location.full_address_with_name

    if bill_to_address or ship_to_address:
        address_data = []
        address_data.append([
            Paragraph('<b>Bill To:</b>', styles['Normal']),
            Paragraph('<b>Ship To:</b>', styles['Normal'])
        ])
        address_data.append([
            Paragraph(bill_to_address.replace('\n', '<br/>'), styles['Normal']),
            Paragraph(ship_to_address.replace('\n', '<br/>'), styles['Normal'])
        ])
        
        address_table = Table(address_data, colWidths=[3.75*inch, 3.75*inch])
        address_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(address_table)
        elements.append(Spacer(1, 0.3*inch))

    # Add Incoterms if present (from related sales order)
    related_sales_orders = []
    for line in invoice.lines.all():
        if line.order_line and line.order_line.order:
            if line.order_line.order not in related_sales_orders:
                related_sales_orders.append(line.order_line.order)
    
    # Show incoterms from the first related sales order
    if related_sales_orders and related_sales_orders[0].incoterms:
        so = related_sales_orders[0]
        incoterms_text = f"<b>Incoterms:</b> {so.incoterms.code}"
        if so.incoterms_location:
            incoterms_text += f" {so.incoterms_location}"
        
        # Create incoterms table with yellow background
        incoterms_data = [[Paragraph(incoterms_text, styles['Normal'])]]
        incoterms_table = Table(incoterms_data, colWidths=[7.5*inch])
        incoterms_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.yellow),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(incoterms_table)
        elements.append(Spacer(1, 0.2*inch))

    # Invoice Details
    elements.append(Paragraph("Invoice Details", heading_style))
    
    # New column widths for 8 columns (no Description), total 7.5 inches
    invoice_col_widths = [0.35*inch, 2.3*inch, 1.0*inch, 1.1*inch, 0.6*inch, 0.45*inch, 0.65*inch, 1.05*inch]

    # Table header - Remove Description column
    line_data = [['Line', 'Product', 'Manufacturer', 'Part Number', 'Qty', 'UOM', 'Unit Price', 'Total']]

    # Add invoice lines - Remove Description column from data rows
    invoice_lines = invoice.lines.all().order_by('line_no')
    if invoice_lines.exists():
        for line in invoice_lines:
            product_name = ''
            manufacturer_name = ''
            part_number = ''
            if line.product:
                product_name = line.product.name or ''
                manufacturer_name = line.product.manufacturer.name if line.product.manufacturer else ''
                part_number = line.product.manufacturer_part_number or ''
            elif line.charge:
                product_name = line.charge.name
            line_data.append([
                str(line.line_no),
                Paragraph(product_name, styles['Normal']) if product_name else '',
                manufacturer_name,
                part_number,
                f"{line.quantity_invoiced:,.2f}",
                line.product.uom.code if line.product and line.product.uom else '',
                f"${line.price_actual.amount:,.2f}" if line.price_actual else '',
                f"${line.line_net_amount.amount:,.2f}" if line.line_net_amount else ''
            ])
    else:
        line_data.append(['', 'No line items found', '', '', '', '', '', ''])

    # Create table with new column widths and left alignment
    line_table = Table(line_data, colWidths=invoice_col_widths, hAlign='LEFT')
    # Apply table style with extra padding for 'Line' column
    line_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('VALIGN', (0, 1), (-1, -1), 'TOP'),
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'),  # Qty
        ('ALIGN', (5, 1), (5, -1), 'CENTER'),  # UOM
        ('ALIGN', (6, 1), (6, -1), 'RIGHT'),  # Unit Price
        ('ALIGN', (7, 1), (7, -1), 'RIGHT'),  # Total
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Line numbers
        ('LEFTPADDING', (0, 0), (0, -1), 8),  # Extra left padding for 'Line' column
        ('RIGHTPADDING', (0, 0), (0, -1), 8), # Extra right padding for 'Line' column
        ('LEFTPADDING', (1, 0), (-1, -1), 3),
        ('RIGHTPADDING', (1, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        # Grid lines
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.grey),
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 0.3*inch))

    # Totals section (aligned to right side of invoice table)
    totals_data = []
    subtotal = f"${invoice.total_lines.amount:,.2f}"
    totals_data.append(['', '', '', '', '', '', 'Subtotal:', subtotal])
    if invoice.tax_amount and invoice.tax_amount.amount > 0:
        tax_amount = f"${invoice.tax_amount.amount:,.2f}"
        totals_data.append(['', '', '', '', '', '', 'Tax:', tax_amount])
    grand_total = f"${invoice.grand_total.amount:,.2f}"
    totals_data.append(['', '', '', '', '', '', 'Total:', grand_total])
    paid_amount = f"${invoice.paid_amount.amount:,.2f}"
    totals_data.append(['', '', '', '', '', '', 'Amount Paid:', paid_amount])
    balance_due = f"${invoice.open_amount.amount:,.2f}"
    totals_data.append(['', '', '', '', '', '', 'Balance Due:', balance_due])
    # Use same column widths as invoice table for perfect alignment (8 columns total)
    totals_table = Table(totals_data, colWidths=invoice_col_widths)
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (6, 0), (6, -1), 'RIGHT'),  # Labels right-aligned
        ('ALIGN', (7, 0), (7, -1), 'RIGHT'),  # Amounts right-aligned  
        ('FONTNAME', (6, -1), (-1, -1), 'Helvetica-Bold'),  # Bold for Balance Due row
        ('FONTSIZE', (6, -1), (-1, -1), 11),
        ('LINEBELOW', (6, -2), (-1, -2), 1, colors.black),  # Line above Balance Due
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # Footer with payment instructions
    footer_text = """
    <b>Payment Instructions:</b><br/>
    Please remit payment within the terms specified above. 
    Include invoice number {invoice_number} with your payment.<br/><br/>
    <b>Thank you for your business!</b><br/>
    For questions regarding this invoice, please contact us at info@malla-group.com
    """.format(invoice_number=invoice.document_no)
    
    elements.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer
    pdf = buffer.getvalue()
    
    
    buffer.close()
    response.write(pdf)
    
    return response


@login_required
def invoice_workflow_action(request, invoice_id):
    """Handle workflow actions for invoices"""
    from django.contrib.admin.views.decorators import staff_member_required
    from django.utils.decorators import method_decorator
    from django.contrib import messages
    from django.shortcuts import redirect
    from django.urls import reverse
    from django.utils import timezone
    from core.models import WorkflowState, WorkflowApproval
    
    if not request.user.is_staff:
        messages.error(request, "You must be a staff member to perform this action")
        return redirect('admin:sales_invoice_changelist')
    
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    action = request.GET.get('action')
    
    if not action:
        messages.error(request, "No action specified")
        return redirect('admin:sales_invoice_change', invoice.pk)
    
    try:
        # Get workflow instance
        workflow = invoice.get_workflow_instance()
        if not workflow:
            messages.error(request, "No workflow configured for this invoice")
            return redirect('admin:sales_invoice_change', invoice.pk)
        
        current_state = workflow.current_state.name
        success = False
        
        # Execute the action based on current state
        if action == 'submit_approval' and current_state == 'draft':
            # Submit for approval
            pending_state = WorkflowState.objects.get(
                workflow=workflow.workflow_definition, 
                name='pending_approval'
            )
            workflow.current_state = pending_state
            workflow.save()
            
            # Create approval request
            WorkflowApproval.objects.create(
                document_workflow=workflow,
                requested_by=request.user,
                status='pending',
                comments=f'Invoice {invoice.document_no} submitted for approval',
                requested_at=timezone.now()
            )
            messages.success(request, f'Invoice {invoice.document_no} submitted for approval')
            success = True
            
        elif action == 'auto_approve' and current_state == 'draft':
            # Auto-approve under threshold
            approved_state = WorkflowState.objects.get(
                workflow=workflow.workflow_definition, 
                name='approved'
            )
            workflow.current_state = approved_state
            workflow.save()
            
            WorkflowApproval.objects.create(
                document_workflow=workflow,
                requested_by=request.user,
                approver=request.user,
                status='approved',
                comments=f'Invoice {invoice.document_no} auto-approved (under threshold)',
                requested_at=timezone.now(),
                responded_at=timezone.now()
            )
            messages.success(request, f'Invoice {invoice.document_no} approved automatically')
            success = True
            
        elif action == 'approve' and current_state == 'pending_approval':
            # Approve pending invoice
            approved_state = WorkflowState.objects.get(
                workflow=workflow.workflow_definition, 
                name='approved'
            )
            workflow.current_state = approved_state
            workflow.save()
            
            # Update the pending approval
            pending_approval = WorkflowApproval.objects.filter(
                document_workflow=workflow,
                status='pending'
            ).first()
            if pending_approval:
                pending_approval.approver = request.user
                pending_approval.status = 'approved'
                pending_approval.responded_at = timezone.now()
                pending_approval.save()
            
            messages.success(request, f'Invoice {invoice.document_no} approved')
            success = True
            
        elif action == 'send_invoice' and current_state == 'approved':
            # Send invoice to customer
            sent_state = WorkflowState.objects.get(
                workflow=workflow.workflow_definition, 
                name='sent'
            )
            workflow.current_state = sent_state
            workflow.save()
            messages.success(request, f'Invoice {invoice.document_no} marked as sent')
            success = True
            
        elif action == 'full_payment' and current_state == 'sent':
            # Record full payment
            paid_state = WorkflowState.objects.get(
                workflow=workflow.workflow_definition, 
                name='paid'
            )
            workflow.current_state = paid_state
            workflow.save()
            
            # Update payment fields
            invoice.paid_amount = invoice.grand_total
            invoice.open_amount = 0
            invoice.is_paid = True
            invoice.save()
            
            messages.success(request, f'Payment recorded for invoice {invoice.document_no}')
            success = True
        
        if not success:
            messages.warning(request, f'Action "{action}" not available for current state "{current_state}"')
            
    except Exception as e:
        messages.error(request, f'Error executing workflow action: {str(e)}')
    
    return redirect('admin:sales_invoice_change', invoice.pk)


@login_required  
def shipment_workflow_action(request, shipment_id):
    """Handle workflow actions for shipments"""
    from django.contrib.admin.views.decorators import staff_member_required
    from django.utils.decorators import method_decorator
    from django.contrib import messages
    from django.shortcuts import redirect
    from django.urls import reverse
    from django.utils import timezone
    from core.models import WorkflowState, WorkflowApproval
    
    if not request.user.is_staff:
        messages.error(request, "You must be a staff member to perform this action")
        return redirect('admin:sales_shipment_changelist')
    
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    action = request.GET.get('action')
    
    if not action:
        messages.error(request, "No action specified")
        return redirect('admin:sales_shipment_change', shipment.pk)
    
    try:
        # Get workflow instance
        workflow = shipment.get_workflow_instance()
        if not workflow:
            messages.error(request, "No workflow configured for this shipment")
            return redirect('admin:sales_shipment_change', shipment.pk)
        
        current_state = workflow.current_state.name
        success = False
        
        # Execute the action based on current state
        if action == 'prepare' and current_state == 'draft':
            # Prepare shipment
            prepared_state = WorkflowState.objects.get(
                workflow=workflow.workflow_definition, 
                name='prepared'
            )
            workflow.current_state = prepared_state
            workflow.save()
            messages.success(request, f'Shipment {shipment.document_no} prepared for shipping')
            success = True
            
        elif action == 'ship' and current_state == 'prepared':
            # Ship the package
            in_transit_state = WorkflowState.objects.get(
                workflow=workflow.workflow_definition, 
                name='in_transit'
            )
            workflow.current_state = in_transit_state
            workflow.save()
            
            # Update shipment flags
            shipment.is_in_transit = True
            shipment.save()
            
            messages.success(request, f'Shipment {shipment.document_no} is now in transit')
            success = True
            
        elif action == 'deliver' and current_state == 'in_transit':
            # Mark as delivered
            delivered_state = WorkflowState.objects.get(
                workflow=workflow.workflow_definition, 
                name='delivered'
            )
            workflow.current_state = delivered_state
            workflow.save()
            
            # Update delivery fields
            shipment.date_received = timezone.now().date()
            shipment.is_in_transit = False
            shipment.save()
            
            messages.success(request, f'Shipment {shipment.document_no} marked as delivered')
            success = True
            
        elif action == 'complete' and current_state == 'delivered':
            # Complete the shipment
            complete_state = WorkflowState.objects.get(
                workflow=workflow.workflow_definition, 
                name='complete'
            )
            workflow.current_state = complete_state
            workflow.save()
            
            shipment.doc_status = 'complete'
            shipment.save()
            
            messages.success(request, f'Shipment {shipment.document_no} completed')
            success = True
        
        if not success:
            messages.warning(request, f'Action "{action}" not available for current state "{current_state}"')
            
    except Exception as e:
        messages.error(request, f'Error executing workflow action: {str(e)}')
    
    return redirect('admin:sales_shipment_change', shipment.pk)