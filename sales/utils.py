"""
Sales Order Utility Functions

Business logic for handling sales orders, including:
- Multi-vendor purchase order generation
- Shipment tracking
- Status calculations
"""

from collections import defaultdict
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from .models import SalesOrder, SalesOrderLine
from purchasing.models import PurchaseOrder, PurchaseOrderLine
from inventory.models import Product, PriceList, Warehouse
from core.models import NumberSequence, Organization, Currency


class SalesOrderManager:
    """Handles sales order business logic"""
    
    def __init__(self, sales_order):
        self.sales_order = sales_order
    
    def analyze_purchase_requirements(self):
        """
        Analyze what needs to be purchased for this sales order.
        Returns a dictionary grouped by vendor.
        """
        requirements = defaultdict(list)
        
        for line in self.sales_order.lines.all():
            if not line.product:
                continue
                
            # Skip if no purchase needed (service, already have stock, etc.)
            if not line.product.is_purchased:
                continue
            
            # Calculate quantity needed
            qty_needed = line.quantity_ordered - line.quantity_delivered
            qty_already_on_po = line.quantity_on_purchase_order
            qty_to_purchase = max(0, qty_needed - qty_already_on_po)
            
            if qty_to_purchase > 0:
                vendor = line.product.primary_vendor
                if vendor:
                    requirements[vendor].append({
                        'so_line': line,
                        'product': line.product,
                        'quantity_needed': qty_to_purchase,
                        'vendor_product_code': line.product.vendor_product_code,
                        'estimated_cost': line.product.standard_cost,
                    })
                else:
                    # No vendor assigned - flag for manual handling
                    requirements[None].append({
                        'so_line': line,
                        'product': line.product,
                        'quantity_needed': qty_to_purchase,
                        'vendor_product_code': '',
                        'estimated_cost': line.product.standard_cost,
                        'error': 'No primary vendor assigned'
                    })
        
        return dict(requirements)
    
    def generate_purchase_orders(self, requirements=None, user=None):
        """
        Generate purchase orders based on requirements analysis.
        Returns list of created PO objects.
        """
        if requirements is None:
            requirements = self.analyze_purchase_requirements()
        
        created_pos = []
        
        with transaction.atomic():
            for vendor, items in requirements.items():
                if vendor is None:
                    continue  # Skip items without vendors
                
                # Create purchase order for this vendor
                po = self._create_purchase_order_for_vendor(vendor, items, user)
                created_pos.append(po)
                
                # Update sales order line tracking
                for item in items:
                    so_line = item['so_line']
                    so_line.quantity_on_purchase_order += item['quantity_needed']
                    so_line.quantity_to_purchase = max(0, 
                        so_line.quantity_ordered - so_line.quantity_delivered - so_line.quantity_on_purchase_order)
                    so_line.save()
        
        return created_pos
    
    def _create_purchase_order_for_vendor(self, vendor, items, user):
        """Create a single purchase order for one vendor"""
        
        # Generate PO number
        po_number = self._generate_po_number()
        
        # Create PO header
        po = PurchaseOrder.objects.create(
            organization=self.sales_order.organization,
            document_no=po_number,
            description=f"Auto-generated from SO {self.sales_order.document_no}",
            business_partner=vendor,
            currency=self.sales_order.currency,
            price_list=vendor.primary_products.first().product_category.product_set.first().standard_cost if vendor.primary_products.exists() else None,
            date_ordered=timezone.now().date(),
            date_promised=timezone.now().date() + timezone.timedelta(days=7),  # Default 7 days
            created_by=user,
            updated_by=user,
        )
        
        # Create PO lines
        line_no = 10
        for item in items:
            PurchaseOrderLine.objects.create(
                order=po,
                line_no=line_no,
                product=item['product'],
                quantity_ordered=item['quantity_needed'],
                price_entered=item['estimated_cost'],
                price_actual=item['estimated_cost'],
                vendor_product_no=item['vendor_product_code'],
                source_sales_order=self.sales_order,
                source_sales_order_line=item['so_line'],
                created_by=user,
                updated_by=user,
            )
            line_no += 10
        
        return po
    
    def _generate_po_number(self):
        """Generate next PO number"""
        # Simple implementation - in production you'd use NumberSequence
        last_po = PurchaseOrder.objects.filter(
            organization=self.sales_order.organization
        ).order_by('-document_no').first()
        
        if last_po and last_po.document_no.startswith('PO'):
            try:
                last_num = int(last_po.document_no[2:])
                return f"PO{last_num + 1:06d}"
            except ValueError:
                pass
        
        return "PO000001"
    
    def get_status_summary(self):
        """Get comprehensive status summary for the sales order"""
        return {
            'order_status': self.sales_order.doc_status,
            'delivery_status': self.sales_order.delivery_status,
            'purchase_status': self.sales_order.purchase_status,
            'total_lines': self.sales_order.lines.count(),
            'total_quantity_ordered': self.sales_order.total_quantity_ordered,
            'total_quantity_delivered': self.sales_order.total_quantity_delivered,
            'total_quantity_pending': self.sales_order.total_quantity_pending,
            'lines_needing_purchase': self.sales_order.lines.filter(quantity_to_purchase__gt=0).count(),
            'purchase_orders_created': PurchaseOrder.objects.filter(
                lines__source_sales_order=self.sales_order
            ).distinct().count(),
        }


def bulk_analyze_sales_orders(queryset):
    """Analyze multiple sales orders for purchase requirements"""
    analysis = []
    
    for so in queryset:
        manager = SalesOrderManager(so)
        requirements = manager.analyze_purchase_requirements()
        status = manager.get_status_summary()
        
        analysis.append({
            'sales_order': so,
            'requirements': requirements,
            'status': status,
            'needs_attention': len(requirements.get(None, [])) > 0,  # Items without vendors
        })
    
    return analysis


def create_customer_order_from_data(customer, order_data, user):
    """
    Create a sales order from customer order data.
    Designed for easy integration with order intake forms.
    
    order_data format:
    {
        'customer_po': 'CUST-12345',
        'date_needed': '2025-01-15',
        'ship_to_address': '123 Main St...',
        'items': [
            {'product_code': 'PROD001', 'quantity': 10, 'notes': ''},
            {'product_code': 'PROD002', 'quantity': 5, 'notes': 'Rush order'},
        ]
    }
    """
    
    # Generate SO number
    so_number = _generate_so_number()
    
    # Get default organization and required objects
    default_org = Organization.objects.first()
    default_currency = Currency.objects.first()
    default_price_list = PriceList.objects.filter(is_sales_price_list=True).first()
    default_warehouse = Warehouse.objects.first()
    
    with transaction.atomic():
        # Create sales order
        so = SalesOrder.objects.create(
            organization=default_org,
            document_no=so_number,
            description=f"Customer Order {order_data.get('customer_po', '')}",
            business_partner=customer,
            date_ordered=timezone.now().date(),
            date_promised=order_data.get('date_needed'),
            ship_to_address=order_data.get('ship_to_address', ''),
            customer_po_reference=order_data.get('customer_po', ''),
            currency=default_currency,
            price_list=default_price_list,
            warehouse=default_warehouse,
            created_by=user,
            updated_by=user,
        )
        
        # Create order lines
        line_no = 10
        for item_data in order_data.get('items', []):
            try:
                product = Product.objects.get(code=item_data['product_code'])
                
                SalesOrderLine.objects.create(
                    order=so,
                    line_no=line_no,
                    product=product,
                    quantity_ordered=Decimal(str(item_data['quantity'])),
                    price_entered=product.list_price,
                    price_actual=product.list_price,
                    description=item_data.get('notes', ''),
                    # Calculate quantity to purchase based on stock
                    quantity_to_purchase=Decimal(str(item_data['quantity'])) if product.is_purchased else 0,
                    created_by=user,
                    updated_by=user,
                )
                line_no += 10
                
            except Product.DoesNotExist:
                # Handle missing products - could create placeholder or error
                SalesOrderLine.objects.create(
                    order=so,
                    line_no=line_no,
                    quantity_ordered=Decimal(str(item_data['quantity'])),
                    price_entered=0,
                    price_actual=0,
                    description=f"MISSING PRODUCT: {item_data['product_code']} - {item_data.get('notes', '')}",
                    created_by=user,
                    updated_by=user,
                )
                line_no += 10
    
    return so


def _generate_so_number(organization=None):
    """Generate next SO number"""
    # Simple implementation
    last_so = SalesOrder.objects.order_by('-document_no').first()
    
    if last_so and last_so.document_no.startswith('SO'):
        try:
            last_num = int(last_so.document_no[2:])
            return f"SO{last_num + 1:06d}"
        except ValueError:
            pass
    
    return "SO000001"