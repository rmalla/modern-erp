"""
Inventory models for Modern ERP system.
Product catalog, warehouses, and inventory management.
Based on iDempiere's M_Product, M_Warehouse, etc.
"""

from django.db import models
from django.core.validators import MinValueValidator
from djmoney.models.fields import MoneyField
from decimal import Decimal
from core.models import BaseModel, Organization, BusinessPartner, UnitOfMeasure


class Manufacturer(BaseModel):
    """
    Manufacturer/Brand master data for products.
    Simple placeholder for product attribution.
    """
    code = models.CharField(max_length=50, unique=True, help_text="Manufacturer code (e.g., APPLE, SAMSUNG)")
    name = models.CharField(max_length=200, help_text="Full manufacturer name")
    brand_name = models.CharField(max_length=200, blank=True, help_text="Brand name if different from company name")
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return self.name


class ProductCategory(BaseModel):
    """
    Product Category for classification.
    Based on iDempiere's M_Product_Category.
    """
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
    # Accounting defaults
    asset_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='product_categories_asset')
    expense_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='product_categories_expense')
    revenue_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='product_categories_revenue')
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Product Categories'
        
    def __str__(self):
        return f"{self.code} - {self.name}"


class Product(BaseModel):
    """
    Product master data.
    Based on iDempiere's M_Product.
    """
    PRODUCT_TYPES = [
        ('item', 'Item'),
        ('service', 'Service'),
        ('resource', 'Resource'),
        ('expense', 'Expense Type'),
        ('online', 'Online'),
    ]
    
    # Basic information
    name = models.CharField(max_length=200)
    short_description = models.TextField(blank=True, help_text="Brief product description")
    description = models.TextField(blank=True, help_text="Detailed product description")
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default='item')
    
    # Physical properties
    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, verbose_name="Unit of Measure")
    weight = models.DecimalField(max_digits=10, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    volume = models.DecimalField(max_digits=10, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    
    
    # Pricing
    list_price = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0, verbose_name="Price")
    standard_cost = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0, verbose_name="Cost")
    
    # Manufacturer information
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, null=True, blank=True, help_text="Product manufacturer/brand")
    manufacturer_part_number = models.CharField(max_length=100, blank=True, help_text="Manufacturer's part number")
    
    # Tax and accounting
    tax_category = models.ForeignKey('accounting.TaxCategory', on_delete=models.SET_NULL, null=True, blank=True)
    asset_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='products_asset')
    expense_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='products_expense')
    revenue_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='products_revenue')
    
    class Meta:
        ordering = ['manufacturer_part_number', 'name']
        
    def __str__(self):
        return f"{self.manufacturer_part_number} - {self.name}" if self.manufacturer_part_number else self.name
    
    @property
    def current_stock(self):
        """Get current stock across all warehouses."""
        return sum(storage.quantity_on_hand for storage in self.storage_details.all())


class Warehouse(BaseModel):
    """
    Warehouse/Location master.
    Based on iDempiere's M_Warehouse.
    """
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    
    # Address information
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='United States')
    
    # Flags
    is_in_transit = models.BooleanField(default=False, help_text="In-transit warehouse")
    is_quarantine = models.BooleanField(default=False, help_text="Quarantine warehouse")
    
    class Meta:
        unique_together = ['organization', 'code']
        ordering = ['organization', 'name']
        
    def __str__(self):
        return f"{self.organization.name} - {self.name}"


class StorageDetail(BaseModel):
    """
    Product storage details per warehouse.
    Based on iDempiere's M_Storage.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='storage_details')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    
    # Quantities
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_reserved = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dates
    date_last_inventory = models.DateField(null=True, blank=True)
    
    class Meta:
        unique_together = ['product', 'warehouse']
        ordering = ['product', 'warehouse']
        
    def __str__(self):
        return f"{self.product.manufacturer_part_number or self.product.name} @ {self.warehouse.name}"
    
    @property
    def quantity_available(self):
        """Available quantity (on hand - reserved)."""
        return self.quantity_on_hand - self.quantity_reserved


class PriceList(BaseModel):
    """
    Price list master.
    Based on iDempiere's M_PriceList.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT)
    
    # Flags
    is_sales_price_list = models.BooleanField(default=True)
    is_purchase_price_list = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    
    # Validity
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['organization', 'name']
        
    def __str__(self):
        return f"{self.organization.name} - {self.name}"


class PriceListVersion(BaseModel):
    """
    Price list version for time-based pricing.
    Based on iDempiere's M_PriceList_Version.
    """
    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name='versions')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Validity
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['price_list', '-valid_from']
        
    def __str__(self):
        return f"{self.price_list.name} - {self.name}"


class ProductPrice(BaseModel):
    """
    Product pricing by price list version.
    Based on iDempiere's M_ProductPrice.
    """
    price_list_version = models.ForeignKey(PriceListVersion, on_delete=models.CASCADE, related_name='product_prices')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    
    # Prices
    list_price = MoneyField(max_digits=15, decimal_places=2, default_currency='USD')
    standard_price = MoneyField(max_digits=15, decimal_places=2, default_currency='USD')
    limit_price = MoneyField(max_digits=15, decimal_places=2, default_currency='USD', default=0)
    
    class Meta:
        unique_together = ['price_list_version', 'product']
        ordering = ['price_list_version', 'product']
        
    def __str__(self):
        return f"{self.product.manufacturer_part_number or self.product.name} - {self.list_price}"