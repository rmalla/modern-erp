"""
URL configuration for purchasing app.
"""

from django.urls import path
from . import views

app_name = 'purchasing'

urlpatterns = [
    # Purchase Order PDF
    path('purchase-order/<uuid:order_id>/pdf/', views.purchase_order_pdf, name='purchase_order_pdf'),
    
    # AJAX endpoints for product selection
    path('ajax/search-products/', views.ajax_search_products, name='ajax_search_products'),
    path('ajax/get-manufacturers/', views.ajax_get_manufacturers, name='ajax_get_manufacturers'),
    path('ajax/add-order-line/', views.ajax_add_order_line, name='ajax_add_order_line'),
]