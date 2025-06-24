"""
Purchasing Views for Modern ERP

User-friendly views for managing the purchasing process:
- Purchase order management with status tracking
- Vendor order processing
- Receipt management
- Purchase order PDF generation

Updated: 2025-06-24 12:55 - Added purchase order PDF generation based on sales order template
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

from .models import PurchaseOrder, PurchaseOrderLine
from core.models import BusinessPartner


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
    
    canvas.restoreState()


@login_required
def purchase_order_pdf(request, order_id):
    """Generate PDF for a purchase order"""
    order = get_object_or_404(PurchaseOrder, id=order_id)
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="PO_{order.document_no}.pdf"'
    
    # Create the PDF object using BytesIO
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        topMargin=0.5*inch, 
        bottomMargin=0.75*inch,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        title=f"Purchase Order {order.document_no}",
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
    
    # Create a special style for PURCHASE ORDER title in header
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
    
    # Create purchase order title with order number and date below it
    purchase_order_title = Paragraph("PURCHASE ORDER", title_header_style)
    order_info = f"<b>Order Number:</b> PO #{order.document_no}<br/><b>Order Date:</b> {order.date_ordered.strftime('%Y-%m-%d') if order.date_ordered else ''}"
    order_info_para = Paragraph(order_info, order_info_style)
    
    # Create a nested table for the right column (title + order info only)
    right_column = Table([
        [purchase_order_title],
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
    vendor_contact_info = ''
    if order.contact:
        vendor_contact_info = order.contact.name
        if order.contact.email:
            vendor_contact_info += f" ({order.contact.email})"
    
    malla_contact_info = ''
    if order.internal_user:
        malla_contact_info = order.internal_user.get_full_name()
        if order.internal_user.email:
            malla_contact_info += f" ({order.internal_user.email})"
    
    # Build header data starting with core fields (adapted for vendors)
    header_data = [
        ['Vendor:', order.business_partner.name if order.business_partner else '', 'Vendor Reference:', order.vendor_reference or ''],
        ['Vendor Contact:', vendor_contact_info, '', ''],
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
    
    # Style the header table
    header_style = [
        ('FONT', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),  # Label column
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),  # Second label column
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold'),  # Bold labels
        ('FONT', (2, 0), (2, -1), 'Helvetica-Bold'),  # Bold labels
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]
    
    # Highlight Incoterms row if present
    if incoterms_row is not None:
        header_style.append(('BACKGROUND', (0, incoterms_row), (-1, incoterms_row), colors.yellow))
    
    header_table.setStyle(TableStyle(header_style))
    elements.append(header_table)
    
    # Addresses section
    if order.bill_to_location or order.ship_to_location:
        elements.append(Spacer(1, 0.2*inch))
        
        # Addresses
        address_data = []
        
        # Bill To Address
        bill_to_text = ""
        if order.bill_to_location:
            bill_to_text = order.bill_to_location.full_address_with_name
        elif order.bill_to_address:
            bill_to_text = order.bill_to_address
        
        # Ship To Address
        ship_to_text = ""
        if order.ship_to_location:
            ship_to_text = order.ship_to_location.full_address_with_name
        elif order.ship_to_address:
            ship_to_text = order.ship_to_address
        
        if bill_to_text or ship_to_text:
            address_data = [
                ['Bill To:', 'Ship To:'],
                [bill_to_text, ship_to_text]
            ]
            
            address_table = Table(address_data, colWidths=[4*inch, 4*inch])
            address_table.setStyle(TableStyle([
                ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONT', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ]))
            elements.append(address_table)
    
    elements.append(Spacer(1, 0.1*inch))
    
    # Order lines (removed "Order Details" title to move table higher)
    
    # Table header - Same 8-column structure as sales order
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
    
    # Build PDF with custom footer
    doc.build(elements, onFirstPage=footer_canvas, onLaterPages=footer_canvas)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response