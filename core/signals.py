"""
Signal handlers for cache invalidation in Modern ERP system.
Automatically invalidate relevant cache entries when models are modified.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .cache_utils import invalidate_business_partner_cache, invalidate_product_cache
import logging

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender='core.BusinessPartner')
def invalidate_business_partner_cache_handler(sender, instance, **kwargs):
    """Invalidate business partner cache when BP is modified."""
    invalidate_business_partner_cache(instance.id)
    # Also clear dashboard cache since it may include this BP
    clear_dashboard_cache()


@receiver([post_save, post_delete], sender='core.Contact')
def invalidate_contact_cache_handler(sender, instance, **kwargs):
    """Invalidate business partner cache when contact is modified."""
    if instance.business_partner_id:
        invalidate_business_partner_cache(instance.business_partner_id)


@receiver([post_save, post_delete], sender='core.BusinessPartnerLocation')
def invalidate_location_cache_handler(sender, instance, **kwargs):
    """Invalidate business partner cache when location is modified."""
    if instance.business_partner_id:
        invalidate_business_partner_cache(instance.business_partner_id)


@receiver([post_save, post_delete], sender='inventory.Product')
def invalidate_product_cache_handler(sender, instance, **kwargs):
    """Invalidate product cache when product is modified."""
    invalidate_product_cache(instance.id)


@receiver([post_save, post_delete], sender='inventory.ProductPrice')
def invalidate_product_price_cache_handler(sender, instance, **kwargs):
    """Invalidate product cache when pricing is modified."""
    if instance.product_id:
        invalidate_product_cache(instance.product_id)


@receiver([post_save, post_delete], sender='inventory.StorageDetail')
def invalidate_storage_cache_handler(sender, instance, **kwargs):
    """Invalidate product cache when inventory levels change."""
    if instance.product_id:
        invalidate_product_cache(instance.product_id)


@receiver([post_save, post_delete], sender='sales.SalesOrder')
def invalidate_sales_cache_handler(sender, instance, **kwargs):
    """Invalidate sales-related cache when sales order is modified."""
    clear_dashboard_cache()
    # Clear business partner cache if order affects BP data
    if instance.business_partner_id:
        cache_key = f"bp_sales_orders:{instance.business_partner_id}"
        cache.delete(cache_key)


@receiver([post_save, post_delete], sender='sales.SalesOrderLine')
def invalidate_sales_line_cache_handler(sender, instance, **kwargs):
    """Invalidate sales-related cache when sales order line is modified."""
    clear_dashboard_cache()
    # Clear product cache if line affects product data
    if instance.product_id:
        cache_key = f"product_sales_lines:{instance.product_id}"
        cache.delete(cache_key)


@receiver([post_save, post_delete], sender='sales.Invoice')
def invalidate_invoice_cache_handler(sender, instance, **kwargs):
    """Invalidate invoice-related cache when invoice is modified."""
    clear_dashboard_cache()
    # Clear business partner invoice cache
    if instance.business_partner_id:
        cache_key = f"bp_invoices:{instance.business_partner_id}"
        cache.delete(cache_key)


@receiver([post_save, post_delete], sender='purchasing.PurchaseOrder')
def invalidate_purchase_cache_handler(sender, instance, **kwargs):
    """Invalidate purchase-related cache when PO is modified."""
    clear_dashboard_cache()
    # Clear business partner cache
    if instance.business_partner_id:
        cache_key = f"bp_purchase_orders:{instance.business_partner_id}"
        cache.delete(cache_key)


def clear_dashboard_cache():
    """Clear all dashboard-related cache entries."""
    cache_keys = [
        'dashboard_pending_orders',
        'dashboard_in_progress_orders', 
        'dashboard_orders_needing_po',
        'dashboard_stats',
        'dashboard_ready_to_ship',
    ]
    
    for key in cache_keys:
        # Safe delete_pattern that works with DummyCache
        try:
            cache.delete_pattern(f"{key}:*")
        except AttributeError:
            # DummyCache doesn't have delete_pattern, just delete individual keys
            cache.delete(key)
    
    logger.debug("Cleared dashboard cache")


def clear_all_model_cache():
    """Clear all model-related cache entries."""
    patterns = [
        'model:*',
        'func:*',
        'queryset:*',
        'bp_data:*',
        'product_data:*',
        'dashboard_*',
    ]
    
    for pattern in patterns:
        # Safe delete_pattern that works with DummyCache
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            # DummyCache doesn't have delete_pattern, skip pattern-based clearing
            pass
    
    logger.info("Cleared all model cache")


# Connect workflow signals for cache invalidation
@receiver([post_save, post_delete], sender='core.DocumentWorkflow')
def invalidate_workflow_cache_handler(sender, instance, **kwargs):
    """Invalidate workflow-related cache when workflow changes."""
    # Clear cache for the specific document
    content_type = instance.content_type.model
    object_id = instance.object_id
    
    cache_keys = [
        f"workflow:{content_type}:{object_id}",
        f"workflow_state:{content_type}:{object_id}",
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    # Clear dashboard cache if it's a sales order workflow
    if content_type == 'salesorder':
        clear_dashboard_cache()


@receiver([post_save, post_delete], sender='core.WorkflowApproval') 
def invalidate_approval_cache_handler(sender, instance, **kwargs):
    """Invalidate approval-related cache when approval changes."""
    if instance.document_workflow:
        workflow = instance.document_workflow
        content_type = workflow.content_type.model
        object_id = workflow.object_id
        
        cache_keys = [
            f"approvals:{content_type}:{object_id}",
            f"workflow:{content_type}:{object_id}",
        ]
        
        for key in cache_keys:
            cache.delete(key)