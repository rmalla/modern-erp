"""
Cache utilities for Modern ERP system.
Provides high-level caching functions for common patterns.
"""

from django.core.cache import cache, caches
from django.core.cache.utils import make_template_fragment_key
from django.utils.cache import get_cache_key
from functools import wraps
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

# Cache aliases
DEFAULT_CACHE = 'default'
STATIC_CACHE = 'static_data'
SESSION_CACHE = 'sessions'

# Common cache timeouts (in seconds)
TIMEOUT_SHORT = 300      # 5 minutes
TIMEOUT_MEDIUM = 1800    # 30 minutes  
TIMEOUT_LONG = 3600      # 1 hour
TIMEOUT_DAILY = 86400    # 24 hours


def cache_key_generator(prefix, *args, **kwargs):
    """Generate a consistent cache key from prefix and arguments."""
    key_data = {
        'args': args,
        'kwargs': sorted(kwargs.items())
    }
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_string.encode()).hexdigest()
    return f"{prefix}:{key_hash}"


def cached_function(timeout=TIMEOUT_MEDIUM, cache_alias=DEFAULT_CACHE, prefix=None):
    """
    Decorator to cache function results.
    
    Args:
        timeout: Cache timeout in seconds
        cache_alias: Which cache to use
        prefix: Cache key prefix (defaults to function name)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_instance = caches[cache_alias]
            key_prefix = prefix or f"func:{func.__name__}"
            cache_key = cache_key_generator(key_prefix, *args, **kwargs)
            
            # Try to get from cache
            result = cache_instance.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_instance.set(cache_key, result, timeout)
            logger.debug(f"Cache set for {cache_key}")
            return result
        
        # Add cache management methods to function
        wrapper.cache_clear = lambda: cache_instance.delete_pattern(f"{key_prefix}:*")
        wrapper.cache_key = lambda *args, **kwargs: cache_key_generator(key_prefix, *args, **kwargs)
        
        return wrapper
    return decorator


class ModelCacheManager:
    """Cache manager for Django models."""
    
    def __init__(self, model_class, cache_alias=DEFAULT_CACHE):
        self.model_class = model_class
        self.cache = caches[cache_alias]
        self.model_name = model_class._meta.label_lower.replace('.', '_')
    
    def get_object_key(self, pk):
        """Get cache key for a single object."""
        return f"model:{self.model_name}:pk:{pk}"
    
    def get_queryset_key(self, filters=None, ordering=None):
        """Get cache key for a queryset."""
        key_data = {
            'filters': filters or {},
            'ordering': ordering or []
        }
        return cache_key_generator(f"queryset:{self.model_name}", **key_data)
    
    def get_object(self, pk, timeout=TIMEOUT_MEDIUM):
        """Get object from cache or database."""
        cache_key = self.get_object_key(pk)
        obj = self.cache.get(cache_key)
        
        if obj is None:
            try:
                obj = self.model_class.objects.get(pk=pk)
                self.cache.set(cache_key, obj, timeout)
                logger.debug(f"Cached object {cache_key}")
            except self.model_class.DoesNotExist:
                # Cache the fact that object doesn't exist
                self.cache.set(cache_key, 'DOES_NOT_EXIST', timeout)
                raise
        elif obj == 'DOES_NOT_EXIST':
            raise self.model_class.DoesNotExist()
        
        return obj
    
    def invalidate_object(self, pk):
        """Invalidate cached object."""
        cache_key = self.get_object_key(pk)
        self.cache.delete(cache_key)
        logger.debug(f"Invalidated cache for {cache_key}")
    
    def invalidate_all(self):
        """Invalidate all cached objects for this model."""
        pattern = f"model:{self.model_name}:*"
        self.cache.delete_pattern(pattern)
        logger.debug(f"Invalidated all cache for {self.model_name}")


def cache_business_partner_data(business_partner_id, timeout=TIMEOUT_LONG):
    """Cache business partner related data (contacts, locations, etc.)."""
    from core.models import BusinessPartner, Contact, BusinessPartnerLocation
    
    cache_key = f"bp_data:{business_partner_id}"
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        try:
            bp = BusinessPartner.objects.get(id=business_partner_id)
            contacts = list(bp.contacts.filter(is_active=True).values(
                'id', 'name', 'email', 'phone'
            ))
            locations = list(bp.locations.all().values(
                'id', 'name', 'address_line_1', 'address_line_2', 
                'city', 'state', 'postal_code', 'country',
                'is_bill_to', 'is_ship_to'
            ))
            
            cached_data = {
                'business_partner': {
                    'id': str(bp.id),
                    'name': bp.name,
                    'search_key': bp.search_key,
                    'partner_type': bp.partner_type,
                },
                'contacts': contacts,
                'locations': locations,
            }
            
            cache.set(cache_key, cached_data, timeout)
            logger.debug(f"Cached business partner data for {business_partner_id}")
            
        except BusinessPartner.DoesNotExist:
            return None
    
    return cached_data


def invalidate_business_partner_cache(business_partner_id):
    """Invalidate business partner related cache."""
    cache_key = f"bp_data:{business_partner_id}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated business partner cache for {business_partner_id}")


def cache_product_data(product_id, timeout=TIMEOUT_LONG):
    """Cache product related data (pricing, inventory, etc.)."""
    from inventory.models import Product, ProductPrice, StorageDetail
    
    cache_key = f"product_data:{product_id}"
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        try:
            product = Product.objects.select_related('manufacturer', 'tax_category').get(id=product_id)
            
            # Get latest pricing
            latest_prices = ProductPrice.objects.filter(
                product=product
            ).select_related('price_list_version__price_list').order_by('-price_list_version__valid_from')[:5]
            
            # Get inventory levels
            storage_details = StorageDetail.objects.filter(
                product=product
            ).select_related('warehouse').values(
                'warehouse__name', 'quantity_on_hand', 'quantity_reserved'
            )
            
            cached_data = {
                'product': {
                    'id': str(product.id),
                    'name': product.name,
                    'manufacturer_part_number': product.manufacturer_part_number,
                    'manufacturer_name': product.manufacturer.name if product.manufacturer else None,
                    'product_type': product.product_type,
                    'weight': float(product.weight) if product.weight else None,
                    'volume': float(product.volume) if product.volume else None,
                },
                'prices': [
                    {
                        'price_list': price.price_list_version.price_list.name,
                        'price': float(price.standard_price),
                        'valid_from': price.price_list_version.valid_from.isoformat() if price.price_list_version.valid_from else None,
                    }
                    for price in latest_prices
                ],
                'inventory': list(storage_details),
            }
            
            cache.set(cache_key, cached_data, timeout)
            logger.debug(f"Cached product data for {product_id}")
            
        except Product.DoesNotExist:
            return None
    
    return cached_data


def invalidate_product_cache(product_id):
    """Invalidate product related cache."""
    cache_key = f"product_data:{product_id}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated product cache for {product_id}")


def warm_up_cache():
    """Warm up frequently accessed cache data."""
    from core.models import BusinessPartner
    from inventory.models import Product
    
    logger.info("Starting cache warm-up...")
    
    # Cache top business partners
    top_partners = BusinessPartner.objects.filter(
        is_active=True,
        is_customer=True
    )[:50]
    
    for partner in top_partners:
        cache_business_partner_data(partner.id)
    
    # Cache active products
    active_products = Product.objects.filter(is_active=True)[:100]
    
    for product in active_products:
        cache_product_data(product.id)
    
    logger.info("Cache warm-up completed")


def get_cache_stats():
    """Get cache statistics for monitoring."""
    stats = {}
    
    for cache_name in ['default', 'sessions', 'static_data']:
        try:
            cache_instance = caches[cache_name]
            # Get Redis connection info using django-redis API
            if hasattr(cache_instance, 'client') and hasattr(cache_instance.client, 'get_client'):
                client = cache_instance.client.get_client()
                info = client.info()
                stats[cache_name] = {
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory_human': info.get('used_memory_human', 'N/A'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'total_connections_received': info.get('total_connections_received', 0),
                    'total_commands_processed': info.get('total_commands_processed', 0),
                }
            else:
                # Fallback for other cache backends
                stats[cache_name] = {
                    'status': 'connected',
                    'backend': str(type(cache_instance)),
                }
        except Exception as e:
            stats[cache_name] = {'error': str(e)}
    
    return stats