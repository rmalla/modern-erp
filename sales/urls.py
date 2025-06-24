"""
Sales app URL patterns
"""

from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    # Dashboard and main views
    path('', views.sales_dashboard, name='dashboard'),
    path('dashboard/', views.sales_dashboard, name='dashboard'),
    
    # Customer order intake
    path('order-intake/', views.customer_order_intake, name='order_intake'),
    
    # Sales order management
    path('order/<uuid:order_id>/', views.sales_order_detail, name='order_detail'),
    path('order/<uuid:order_id>/generate-pos/', views.generate_purchase_orders, name='generate_pos'),
    path('order/<uuid:order_id>/ship-invoice/', views.quick_ship_invoice, name='quick_ship_invoice'),
    path('order/<uuid:order_id>/pdf/', views.sales_order_pdf, name='order_pdf'),
    
    # Invoice management
    path('invoice/<uuid:invoice_id>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    
    # Shipping and invoicing
    path('ship-invoice/<uuid:shipment_id>/<uuid:invoice_id>/', 
         views.ship_invoice_combined_view, name='ship_invoice_view'),
    
    # Reports
    path('purchase-requirements/', views.purchase_requirements_report, name='purchase_requirements'),
    
    # AJAX endpoints
    path('ajax/product-search/', views.ajax_product_search, name='ajax_product_search'),
    
    # Workflow action endpoints
    path('admin/invoice/<uuid:invoice_id>/workflow-action/', views.invoice_workflow_action, name='admin:sales_invoice_workflow_action'),
    path('admin/shipment/<uuid:shipment_id>/workflow-action/', views.shipment_workflow_action, name='admin:sales_shipment_workflow_action'),
]