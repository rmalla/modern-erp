"""
Django admin configuration for core models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count
from . import models


# Custom filters for document counts
class HasSalesOrdersFilter(admin.SimpleListFilter):
    title = 'has sales orders'
    parameter_name = 'has_sales_orders'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has sales orders (> 0)'),
            ('no', 'No sales orders (= 0)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.annotate(sales_count=Count('salesorder')).filter(sales_count__gt=0)
        if self.value() == 'no':
            return queryset.annotate(sales_count=Count('salesorder')).filter(sales_count=0)


class HasPurchaseOrdersFilter(admin.SimpleListFilter):
    title = 'has purchase orders'
    parameter_name = 'has_purchase_orders'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has purchase orders (> 0)'),
            ('no', 'No purchase orders (= 0)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.annotate(po_count=Count('purchaseorder')).filter(po_count__gt=0)
        if self.value() == 'no':
            return queryset.annotate(po_count=Count('purchaseorder')).filter(po_count=0)


class HasInvoicesFilter(admin.SimpleListFilter):
    title = 'has invoices'
    parameter_name = 'has_invoices'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has invoices (> 0)'),
            ('no', 'No invoices (= 0)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.annotate(inv_count=Count('invoice')).filter(inv_count__gt=0)
        if self.value() == 'no':
            return queryset.annotate(inv_count=Count('invoice')).filter(inv_count=0)


class HasVendorBillsFilter(admin.SimpleListFilter):
    title = 'has vendor bills'
    parameter_name = 'has_vendor_bills'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has vendor bills (> 0)'),
            ('no', 'No vendor bills (= 0)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.annotate(vb_count=Count('vendorbill')).filter(vb_count__gt=0)
        if self.value() == 'no':
            return queryset.annotate(vb_count=Count('vendorbill')).filter(vb_count=0)


class HasReceiptsFilter(admin.SimpleListFilter):
    title = 'has receipts'
    parameter_name = 'has_receipts'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has receipts (> 0)'),
            ('no', 'No receipts (= 0)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.annotate(receipt_count=Count('receipt')).filter(receipt_count__gt=0)
        if self.value() == 'no':
            return queryset.annotate(receipt_count=Count('receipt')).filter(receipt_count=0)


class HasAnyDocumentsFilter(admin.SimpleListFilter):
    title = 'has any documents'
    parameter_name = 'has_any_documents'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has any documents (> 0)'),
            ('no', 'No documents at all (= 0)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.annotate(
                total_docs=Count('salesorder') + Count('purchaseorder') + Count('invoice') + Count('vendorbill') + Count('receipt')
            ).filter(total_docs__gt=0)
        if self.value() == 'no':
            return queryset.annotate(
                total_docs=Count('salesorder') + Count('purchaseorder') + Count('invoice') + Count('vendorbill') + Count('receipt')
            ).filter(total_docs=0)


@admin.register(models.User)
class UserAdmin(BaseUserAdmin):
    """Extended User admin with ERP fields."""
    fieldsets = BaseUserAdmin.fieldsets + (
        ('ERP Information', {
            'fields': ('employee_id', 'department', 'phone', 'mobile', 'title', 'is_system_admin')
        }),
    )
    list_display = BaseUserAdmin.list_display + ('department', 'title', 'is_system_admin')
    list_filter = BaseUserAdmin.list_filter + ('department', 'is_system_admin')


@admin.register(models.Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'parent', 'default_currency', 'is_active')
    list_filter = ('parent', 'default_currency', 'is_active')
    search_fields = ('code', 'name', 'tax_id')
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'parent')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Financial', {
            'fields': ('tax_id', 'state_tax_id', 'default_currency', 'fiscal_year_end')
        }),
        ('System', {
            'fields': ('is_active', 'created_by', 'updated_by')
        })
    )
    readonly_fields = ('created', 'updated', 'created_by', 'updated_by')


@admin.register(models.Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'organization', 'manager', 'is_active')
    list_filter = ('organization', 'is_active')
    search_fields = ('code', 'name')


class ContactInline(admin.TabularInline):
    model = models.Contact
    extra = 0  # No empty fields
    fields = ('contact_link', 'title_display', 'email_display', 'phone_display')
    readonly_fields = ('contact_link', 'title_display', 'email_display', 'phone_display')
    can_delete = True
    show_change_link = False  # We'll use our custom link
    verbose_name = "Contact"
    verbose_name_plural = "Contacts"
    template = 'admin/core/contact_inline.html'  # Custom template
    
    def has_add_permission(self, request, obj=None):
        """Disable adding through inline - use the add button instead"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable changing through inline - use the edit link instead"""
        return False
    
    def contact_link(self, obj):
        """Display contact name as link to edit page"""
        if obj.pk:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:core_contact_change', args=[obj.pk])
            return format_html('<a href="{}" target="_blank"><strong>{}</strong></a>', url, obj.name)
        return obj.name
    contact_link.short_description = 'Name'
    
    def title_display(self, obj):
        """Display title"""
        return obj.title or '-'
    title_display.short_description = 'Title'
    
    def email_display(self, obj):
        """Display email"""
        return obj.email or '-'
    email_display.short_description = 'Email'
    
    def phone_display(self, obj):
        """Display phone"""
        return obj.phone or '-'
    phone_display.short_description = 'Phone'
    
    def flags_display(self, obj):
        """Display contact flags as badges"""
        from django.utils.html import format_html
        flags = []
        if obj.is_sales_lead:
            flags.append('<span class="contact-flag sales">Sales</span>')
        if obj.is_bill_to:
            flags.append('<span class="contact-flag billing">Bill To</span>')
        if obj.is_ship_to:
            flags.append('<span class="contact-flag shipping">Ship To</span>')
        return format_html(' '.join(flags)) if flags else '-'
    flags_display.short_description = 'Roles'
    
    class Media:
        css = {
            'all': ('admin/css/custom_inline.css',)
        }


class BusinessPartnerLocationInline(admin.TabularInline):
    model = models.BusinessPartnerLocation
    extra = 0  # No empty fields
    fields = ('location_link', 'address_display', 'city_state_display', 'type_flags_display')
    readonly_fields = ('location_link', 'address_display', 'city_state_display', 'type_flags_display')
    can_delete = True
    show_change_link = False  # We'll use our custom link
    verbose_name = "Location"
    verbose_name_plural = "Business Partner Locations"
    template = 'admin/core/location_inline.html'  # Custom template
    
    def has_add_permission(self, request, obj=None):
        """Disable adding through inline - use the add button instead"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable changing through inline - use the edit link instead"""
        return False
    
    def location_link(self, obj):
        """Display location name as link to edit page"""
        if obj.pk:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:core_businesspartnerlocation_change', args=[obj.pk])
            return format_html('<a href="{}" target="_blank"><strong>{}</strong></a>', url, obj.name)
        return obj.name
    location_link.short_description = 'Name'
    
    def address_display(self, obj):
        """Display primary address"""
        return obj.address1 or '-'
    address_display.short_description = 'Address'
    
    def city_state_display(self, obj):
        """Display city, state, postal code"""
        parts = []
        if obj.city:
            parts.append(obj.city)
        if obj.state:
            parts.append(obj.state)
        if obj.postal_code:
            parts.append(obj.postal_code)
        return ', '.join(parts) if parts else '-'
    city_state_display.short_description = 'City, State, ZIP'
    
    def type_flags_display(self, obj):
        """Display location type flags as badges"""
        from django.utils.html import format_html
        flags = []
        if obj.is_bill_to:
            flags.append('<span class="location-flag billing">Bill To</span>')
        if obj.is_ship_to:
            flags.append('<span class="location-flag shipping">Ship To</span>')
        return format_html(' '.join(flags)) if flags else '-'
    type_flags_display.short_description = 'Types'
    
    class Media:
        css = {
            'all': ('admin/css/custom_inline.css',)
        }


# Document inlines for Business Partner
class SalesOrderInline(admin.TabularInline):
    model = None  # Will be set dynamically
    extra = 0
    fields = ('document_link', 'date_ordered', 'doc_status', 'grand_total_display', 'contact_display')
    readonly_fields = ('document_link', 'date_ordered', 'doc_status', 'grand_total_display', 'contact_display')
    can_delete = False
    show_change_link = False
    verbose_name = "Sales Order"
    verbose_name_plural = "Sales Orders"
    template = 'admin/core/document_inline.html'
    
    def __init__(self, *args, **kwargs):
        # Import here to avoid circular imports
        from sales.models import SalesOrder
        self.model = SalesOrder
        super().__init__(*args, **kwargs)
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        """Only show sales orders with optimized queries"""
        qs = super().get_queryset(request)
        return qs.select_related('contact').order_by('-date_ordered')
    
    def document_link(self, obj):
        if obj.pk:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:sales_salesorder_change', args=[obj.pk])
            return format_html('<a href="{}" target="_blank"><strong>{}</strong></a>', url, obj.document_no)
        return obj.document_no
    document_link.short_description = 'Document #'
    
    def grand_total_display(self, obj):
        return f"{obj.grand_total}" if obj.grand_total else '-'
    grand_total_display.short_description = 'Total'
    
    def contact_display(self, obj):
        return obj.contact.name if obj.contact else '-'
    contact_display.short_description = 'Contact'


class PurchaseOrderInline(admin.TabularInline):
    model = None  # Will be set dynamically
    fk_name = 'business_partner'  # Specify which FK to use (main vendor, not ship_to_customer)
    extra = 0
    fields = ('document_link', 'date_ordered', 'doc_status', 'grand_total_display', 'contact_display')
    readonly_fields = ('document_link', 'date_ordered', 'doc_status', 'grand_total_display', 'contact_display')
    can_delete = False
    show_change_link = False
    verbose_name = "Purchase Order"
    verbose_name_plural = "Purchase Orders"
    template = 'admin/core/document_inline.html'
    
    def __init__(self, *args, **kwargs):
        # Import here to avoid circular imports
        from purchasing.models import PurchaseOrder
        self.model = PurchaseOrder
        super().__init__(*args, **kwargs)
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        """Only show purchase orders with optimized queries"""
        qs = super().get_queryset(request)
        return qs.select_related('contact').order_by('-date_ordered')
    
    def document_link(self, obj):
        if obj.pk:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:purchasing_purchaseorder_change', args=[obj.pk])
            return format_html('<a href="{}" target="_blank"><strong>{}</strong></a>', url, obj.document_no)
        return obj.document_no
    document_link.short_description = 'Document #'
    
    def grand_total_display(self, obj):
        return f"{obj.grand_total}" if obj.grand_total else '-'
    grand_total_display.short_description = 'Total'
    
    def contact_display(self, obj):
        return obj.contact.name if obj.contact else '-'
    contact_display.short_description = 'Contact'


class InvoiceInline(admin.TabularInline):
    model = None  # Will be set dynamically
    extra = 0
    fields = ('document_link', 'date_invoiced', 'doc_status', 'grand_total_display', 'open_amount_display', 'contact_display')
    readonly_fields = ('document_link', 'date_invoiced', 'doc_status', 'grand_total_display', 'open_amount_display', 'contact_display')
    can_delete = False
    show_change_link = False
    verbose_name = "Invoice"
    verbose_name_plural = "Invoices"
    template = 'admin/core/document_inline.html'
    
    def __init__(self, *args, **kwargs):
        # Import here to avoid circular imports
        from sales.models import Invoice
        self.model = Invoice
        super().__init__(*args, **kwargs)
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        """Only show invoices with optimized queries"""
        qs = super().get_queryset(request)
        return qs.select_related('contact').order_by('-date_invoiced')
    
    def document_link(self, obj):
        if obj.pk:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:sales_invoice_change', args=[obj.pk])
            return format_html('<a href="{}" target="_blank"><strong>{}</strong></a>', url, obj.document_no)
        return obj.document_no
    document_link.short_description = 'Document #'
    
    def grand_total_display(self, obj):
        return f"{obj.grand_total}" if obj.grand_total else '-'
    grand_total_display.short_description = 'Total'
    
    def open_amount_display(self, obj):
        return f"{obj.open_amount}" if obj.open_amount else '-'
    open_amount_display.short_description = 'Balance'
    
    def contact_display(self, obj):
        return obj.contact.name if obj.contact else '-'
    contact_display.short_description = 'Contact'


class VendorBillInline(admin.TabularInline):
    model = None  # Will be set dynamically
    extra = 0
    fields = ('document_link', 'date_invoiced', 'doc_status', 'grand_total_display', 'open_amount_display')
    readonly_fields = ('document_link', 'date_invoiced', 'doc_status', 'grand_total_display', 'open_amount_display')
    can_delete = False
    show_change_link = False
    verbose_name = "Vendor Bill"
    verbose_name_plural = "Vendor Bills"
    template = 'admin/core/document_inline.html'
    
    def __init__(self, *args, **kwargs):
        # Import here to avoid circular imports
        from purchasing.models import VendorBill
        self.model = VendorBill
        super().__init__(*args, **kwargs)
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        """Only show vendor bills with optimized queries"""
        qs = super().get_queryset(request)
        return qs.order_by('-date_invoiced')  # VendorBill has no contact field
    
    def document_link(self, obj):
        if obj.pk:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:purchasing_vendorbill_change', args=[obj.pk])
            return format_html('<a href="{}" target="_blank"><strong>{}</strong></a>', url, obj.document_no)
        return obj.document_no
    document_link.short_description = 'Document #'
    
    def grand_total_display(self, obj):
        return f"{obj.grand_total}" if obj.grand_total else '-'
    grand_total_display.short_description = 'Total'
    
    def open_amount_display(self, obj):
        return f"{obj.open_amount}" if obj.open_amount else '-'
    open_amount_display.short_description = 'Balance'
    
    def contact_display(self, obj):
        return '-'  # VendorBill model has no contact field
    contact_display.short_description = 'Contact'


class ReceiptInline(admin.TabularInline):
    model = None  # Will be set dynamically
    extra = 0
    fields = ('document_link', 'movement_date', 'doc_status', 'warehouse_display')
    readonly_fields = ('document_link', 'movement_date', 'doc_status', 'warehouse_display')
    can_delete = False
    show_change_link = False
    verbose_name = "Receipt"
    verbose_name_plural = "Receipts"
    template = 'admin/core/document_inline.html'
    
    def __init__(self, *args, **kwargs):
        # Import here to avoid circular imports
        from purchasing.models import Receipt
        self.model = Receipt
        super().__init__(*args, **kwargs)
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        """Only show receipts with optimized queries"""
        qs = super().get_queryset(request)
        return qs.select_related('warehouse').order_by('-movement_date')  # Receipt has no contact field
    
    def document_link(self, obj):
        if obj.pk:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:purchasing_receipt_change', args=[obj.pk])
            return format_html('<a href="{}" target="_blank"><strong>{}</strong></a>', url, obj.document_no)
        return obj.document_no
    document_link.short_description = 'Document #'
    
    def contact_display(self, obj):
        return '-'  # Receipt model has no contact field
    contact_display.short_description = 'Contact'
    
    def warehouse_display(self, obj):
        return obj.warehouse.name if obj.warehouse else '-'
    warehouse_display.short_description = 'Warehouse'
    
    class Media:
        css = {
            'all': ('admin/css/custom_inline.css',)
        }


@admin.register(models.BusinessPartner)
class BusinessPartnerAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'partner_type', 'email', 'phone', 'contact_count', 'location_count', 'sales_order_count', 'purchase_order_count', 'invoice_count', 'vendor_bill_count', 'receipt_count', 'is_orphan', 'is_active')
    list_filter = (
        'partner_type', 'is_customer', 'is_vendor', 'is_tax_exempt', 'is_orphan', 'is_active',
        HasSalesOrdersFilter, HasPurchaseOrdersFilter, HasInvoicesFilter, 
        HasVendorBillsFilter, HasReceiptsFilter, HasAnyDocumentsFilter
    )
    search_fields = ('code', 'name', 'email', 'tax_id')
    inlines = [ContactInline, BusinessPartnerLocationInline, SalesOrderInline, PurchaseOrderInline, InvoiceInline, VendorBillInline, ReceiptInline]
    
    def get_inline_instances(self, request, obj=None):
        """Only show relevant document inlines based on business partner type"""
        inline_instances = []
        
        # Always show contact and location inlines
        for inline_class in [ContactInline, BusinessPartnerLocationInline]:
            inline_instances.append(inline_class(self.model, self.admin_site))
        
        if obj:
            # Show sales-related documents for customers
            if obj.is_customer:
                for inline_class in [SalesOrderInline, InvoiceInline]:
                    inline_instances.append(inline_class(self.model, self.admin_site))
            
            # Show purchase-related documents for vendors
            if obj.is_vendor:
                for inline_class in [PurchaseOrderInline, VendorBillInline, ReceiptInline]:
                    inline_instances.append(inline_class(self.model, self.admin_site))
        else:
            # When adding new business partner, show all inlines
            for inline_class in [SalesOrderInline, PurchaseOrderInline, InvoiceInline, VendorBillInline, ReceiptInline]:
                inline_instances.append(inline_class(self.model, self.admin_site))
        
        return inline_instances
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'name2', 'partner_type')
        }),
        ('Contact Information', {
            'fields': ('country', 'phone', 'email', 'website')
        }),
        ('Financial', {
            'fields': ('credit_limit', 'payment_terms', 'tax_id', 'is_tax_exempt', 'is_1099_vendor')
        }),
        ('Flags', {
            'fields': ('is_customer', 'is_vendor', 'is_employee', 'is_prospect')
        }),
        ('Data Quality', {
            'fields': ('is_orphan',),
            'description': 'Business partners marked as orphan have no locations or related documents and are candidates for deletion'
        }),
    )
    readonly_fields = ('code', 'is_customer', 'is_vendor', 'is_employee', 'is_prospect')
    
    def contact_count(self, obj):
        """Display number of contacts for this business partner"""
        return obj.contacts.count()
    contact_count.short_description = 'Contacts'
    
    def location_count(self, obj):
        """Display number of locations for this business partner"""
        return obj.locations.count()
    location_count.short_description = 'Locations'
    
    def sales_order_count(self, obj):
        """Display number of sales orders for this business partner"""
        if hasattr(obj, 'sales_order_count'):
            return obj.sales_order_count
        return obj.salesorder_set.count()
    sales_order_count.short_description = 'Sales Orders'
    
    def purchase_order_count(self, obj):
        """Display number of purchase orders for this business partner"""
        if hasattr(obj, 'purchase_order_count'):
            return obj.purchase_order_count
        return obj.purchaseorder_set.count()
    purchase_order_count.short_description = 'Purchase Orders'
    
    def invoice_count(self, obj):
        """Display number of invoices for this business partner"""
        if hasattr(obj, 'invoice_count'):
            return obj.invoice_count
        return obj.invoice_set.count()
    invoice_count.short_description = 'Invoices'
    
    def vendor_bill_count(self, obj):
        """Display number of vendor bills for this business partner"""
        if hasattr(obj, 'vendor_bill_count'):
            return obj.vendor_bill_count
        return obj.vendorbill_set.count()
    vendor_bill_count.short_description = 'Vendor Bills'
    
    def receipt_count(self, obj):
        """Display number of receipts for this business partner"""
        if hasattr(obj, 'receipt_count'):
            return obj.receipt_count
        return obj.receipt_set.count()
    receipt_count.short_description = 'Receipts'
    
    def get_queryset(self, request):
        """Optimize queries with document counts"""
        queryset = super().get_queryset(request)
        
        # Prefetch related objects and add document counts
        return queryset.prefetch_related(
            'contacts', 'locations'
        ).annotate(
            sales_order_count=Count('salesorder', distinct=True),
            purchase_order_count=Count('purchaseorder', distinct=True),
            invoice_count=Count('invoice', distinct=True),
            vendor_bill_count=Count('vendorbill', distinct=True),
            receipt_count=Count('receipt', distinct=True)
        )


@admin.register(models.Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('iso_code', 'name', 'symbol', 'precision', 'is_base_currency', 'is_active')
    list_filter = ('is_base_currency', 'is_active')
    search_fields = ('iso_code', 'name')


@admin.register(models.UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'precision', 'is_active')
    search_fields = ('code', 'name')


@admin.register(models.NumberSequence)
class NumberSequenceAdmin(admin.ModelAdmin):
    list_display = ('name', 'prefix', 'current_next', 'increment', 'restart_sequence_every', 'is_active')
    list_filter = ('restart_sequence_every', 'is_active')
    search_fields = ('name', 'prefix')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Format', {
            'fields': ('prefix', 'suffix', 'padding')
        }),
        ('Sequence', {
            'fields': ('current_next', 'increment', 'restart_sequence_every')
        }),
    )


@admin.register(models.Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ('opportunity_number', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('opportunity_number', 'name', 'description')
    
    fieldsets = (
        ('Opportunity Information', {
            'fields': ('opportunity_number', 'name', 'description', 'is_active')
        }),
    )
    
    readonly_fields = ('opportunity_number',)  # Auto-generated


@admin.register(models.PaymentTerms)
class PaymentTermsAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'net_days', 'discount_days', 'discount_percent', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description')
        }),
        ('Payment Conditions', {
            'fields': ('net_days', 'discount_days', 'discount_percent')
        }),
    )


@admin.register(models.Incoterms)
class IncotermsAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description')
        }),
        ('Responsibilities', {
            'fields': ('seller_responsibility', 'buyer_responsibility')
        }),
    )


@admin.register(models.Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'business_partner', 'email', 'phone', 'title', 'is_active')
    list_filter = ('business_partner', 'is_active')
    search_fields = ('name', 'first_name', 'last_name', 'email', 'phone', 'business_partner__name')
    raw_id_fields = ('business_partner', 'supervisor')  # Use search widgets instead of dropdowns
    list_select_related = ('business_partner',)  # Optimize list view queries
    fieldsets = (
        ('Basic Information', {
            'fields': ('first_name', 'last_name', 'title')
        }),
        ('Business Partner', {
            'fields': ('business_partner', 'supervisor')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone')
        }),
        ('Additional Information', {
            'fields': ('description', 'comments')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries by selecting related objects"""
        return super().get_queryset(request).select_related('business_partner', 'supervisor')
    
    def get_changeform_initial_data(self, request):
        """Pre-fill business_partner when adding from business partner page"""
        initial = super().get_changeform_initial_data(request)
        
        # Check if business_partner parameter is in the URL
        business_partner_id = request.GET.get('business_partner')
        if business_partner_id:
            try:
                business_partner = models.BusinessPartner.objects.get(pk=business_partner_id)
                initial['business_partner'] = business_partner
            except models.BusinessPartner.DoesNotExist:
                pass
        
        return initial


@admin.register(models.BusinessPartnerLocation)
class BusinessPartnerLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'business_partner', 'city', 'state', 'country', 'is_bill_to', 'is_ship_to')
    list_filter = ('business_partner', 'is_bill_to', 'is_ship_to', 'country', 'state')
    search_fields = ('name', 'business_partner__name', 'address1', 'city', 'postal_code')
    raw_id_fields = ('business_partner',)  # Use search widget for business partner
    list_select_related = ('business_partner',)  # Optimize list view queries
    fieldsets = (
        ('Basic Information', {
            'fields': ('business_partner', 'name')
        }),
        ('Address', {
            'fields': ('address1', 'address2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Contact Information', {
            'fields': ('phone',)
        }),
        ('Location Types', {
            'fields': ('is_bill_to', 'is_ship_to')
        }),
        ('Additional Information', {
            'fields': ('comments',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries by selecting related objects"""
        return super().get_queryset(request).select_related('business_partner')
    
    def get_changeform_initial_data(self, request):
        """Pre-fill business_partner when adding from business partner page"""
        initial = super().get_changeform_initial_data(request)
        
        # Check if business_partner parameter is in the URL
        business_partner_id = request.GET.get('business_partner')
        if business_partner_id:
            try:
                business_partner = models.BusinessPartner.objects.get(pk=business_partner_id)
                initial['business_partner'] = business_partner
            except models.BusinessPartner.DoesNotExist:
                pass
        
        return initial


# =============================================================================
# WORKFLOW ADMIN
# =============================================================================

class WorkflowStateInline(admin.TabularInline):
    model = models.WorkflowState
    extra = 0
    fields = ('name', 'display_name', 'order', 'color_code', 'is_final', 'requires_approval')
    ordering = ['order']


class WorkflowTransitionInline(admin.TabularInline):
    model = models.WorkflowTransition
    extra = 0
    fields = ('name', 'from_state', 'to_state', 'button_color', 'required_permission', 'requires_approval')


@admin.register(models.WorkflowDefinition)
class WorkflowDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'document_type', 'requires_approval', 'approval_threshold_amount', 'initial_state')
    list_filter = ('requires_approval', 'document_type')
    search_fields = ('name', 'document_type')
    inlines = [WorkflowStateInline, WorkflowTransitionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'document_type', 'initial_state')
        }),
        ('Approval Settings', {
            'fields': ('requires_approval', 'approval_threshold_amount', 'approval_permission')
        }),
        ('Permissions', {
            'fields': ('reactivation_permission',)
        }),
    )


@admin.register(models.WorkflowState)
class WorkflowStateAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'display_name', 'name', 'order', 'is_final', 'requires_approval')
    list_filter = ('workflow', 'is_final', 'requires_approval')
    search_fields = ('name', 'display_name', 'workflow__name')
    ordering = ['workflow', 'order']


@admin.register(models.WorkflowTransition)
class WorkflowTransitionAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'name', 'from_state', 'to_state', 'button_color', 'requires_approval')
    list_filter = ('workflow', 'button_color', 'requires_approval')
    search_fields = ('name', 'workflow__name')


@admin.register(models.DocumentWorkflow)
class DocumentWorkflowAdmin(admin.ModelAdmin):
    list_display = ('content_object', 'current_state', 'workflow_definition', 'created_by', 'created')
    list_filter = ('workflow_definition', 'current_state', 'created')
    search_fields = ('object_id',)
    readonly_fields = ('content_type', 'object_id', 'content_object')
    
    def has_add_permission(self, request):
        # Don't allow manual creation - these are auto-created
        return False


@admin.register(models.WorkflowApproval)
class WorkflowApprovalAdmin(admin.ModelAdmin):
    list_display = ('document_workflow', 'requested_by', 'status', 'approver', 'requested_at', 'responded_at')
    list_filter = ('status', 'requested_at', 'responded_at')
    search_fields = ('requested_by__username', 'approver__username', 'comments')
    readonly_fields = ('requested_at', 'responded_at')
    
    fieldsets = (
        ('Request Information', {
            'fields': ('document_workflow', 'requested_by', 'requested_at', 'amount_at_request')
        }),
        ('Response Information', {
            'fields': ('approver', 'responded_at', 'status', 'comments')
        }),
    )


@admin.register(models.UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'permission_code', 'is_active', 'approval_limit', 'granted_by', 'granted_at')
    list_filter = ('permission_code', 'is_active', 'granted_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'permission_code')
    
    fieldsets = (
        ('Permission Details', {
            'fields': ('user', 'permission_code', 'is_active')
        }),
        ('Limits', {
            'fields': ('approval_limit',)
        }),
        ('Audit Trail', {
            'fields': ('granted_by', 'granted_at'),
            'classes': ('collapse',)
        }),
    )