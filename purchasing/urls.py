"""
URL configuration for purchasing app.
"""

from django.urls import path
from . import views

app_name = 'purchasing'

urlpatterns = [
    # Purchase Order PDF
    path('purchase-order/<uuid:order_id>/pdf/', views.purchase_order_pdf, name='purchase_order_pdf'),
]