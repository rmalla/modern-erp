# Modern ERP System - Complete Overview

## System Purpose & Business Workflow

The Modern ERP system is designed to handle a specific business workflow:

1. **Customer Orders** → Issue **SALES ORDER**
2. **Sales Order** → Create **PURCHASE ORDER(S)** to vendor(s) 
3. **When ready to ship** → Generate **SALES INVOICE + PACKING LIST** (combined document)
4. **Optional**: Generate **PACKING LABELS** from the same document

### Key Business Requirements
- **Multi-vendor purchasing**: One Sales Order can generate multiple Purchase Orders to different vendors
- **Multiple shipments**: Support partial shipments per order
- **Friendly, practical, and informational** system design
- **Elegant, scalable, and auditable** database structure

## Technical Architecture

### Platform
- **Framework**: Django 4.2.11 with Python 3.12
- **Database**: PostgreSQL 16
- **Server**: Ubuntu Linux (Digital Ocean)
- **Web Server**: Gunicorn behind Nginx
- **Domain**: https://erp.r17a.com

### Database Configuration
- **Host**: 138.197.99.201:5432
- **Database**: modern_erp
- **User**: django_user
- **Password**: django_pass
- **Remote Access**: Configured for external SQL clients

### Auto-Startup
- **Service**: modern-erp.service (systemd)
- **Status**: Enabled for automatic startup after reboot
- **Command**: `systemctl status modern-erp`

## Core Applications & Models

### 1. Core App (`/core/`)
**Base infrastructure and shared models**

- **BaseModel**: Abstract base with UUID primary keys, audit trails (created/updated timestamps and users), legacy_id for migration tracking
- **Organization**: Multi-tenant support
- **BusinessPartner**: Customers and vendors with flags (is_customer, is_vendor)
- **User**: Django user extension
- **Currency**: Multi-currency support (default: USD)
- **UnitOfMeasure**: Product measurement units

### 2. Sales App (`/sales/`)
**Customer order management**

#### SalesOrder Model
- Document workflow: drafted → in_progress → waiting_payment → waiting_pickup → complete → closed
- Customer PO reference tracking
- Multi-address support (bill_to, ship_to)
- Pricing: price_list, currency, payment_terms
- Delivery: warehouse, delivery_via, delivery_rule
- Status properties: delivery_status, purchase_status
- Totals: total_lines, grand_total

#### SalesOrderLine Model
- Product or charge-based line items
- Quantities: ordered, delivered, invoiced, reserved, to_purchase, on_purchase_order
- Pricing: price_entered, price_actual, discount, line_net_amount
- Tax handling
- Date tracking: promised, delivered

#### Invoice & InvoiceLine Models
- Standard invoicing with multiple types (standard, credit_memo, debit_memo, proforma)
- Links to sales orders
- Payment tracking: paid_amount, open_amount
- Posting flags for accounting integration

#### Shipment & ShipmentLine Models
- Delivery document management
- Movement types: customer_shipment, customer_return
- Tracking numbers and freight costs
- Quantity tracking: movement_quantity, quantity_entered

### 3. Purchasing App (`/purchasing/`)
**Vendor order management**

#### PurchaseOrder & PurchaseOrderLine Models
- Vendor purchase orders with source tracking to sales orders
- Source fields: source_sales_order, source_sales_order_line
- Vendor product mapping: vendor_product_no
- Quantity tracking: ordered, received, invoiced

#### VendorBill & VendorBillLine Models
- Vendor invoice processing
- Links to purchase orders
- Accounting integration

#### Receipt & ReceiptLine Models
- Vendor receipt processing
- Movement tracking from vendors

### 4. Inventory App (`/inventory/`)
**Product and stock management**

#### Product Model
- Comprehensive product master with categories
- Vendor relationships: primary_vendor, vendor_product_code, lead_time_days
- Pricing: list_price, standard_cost
- Flags: is_purchased, is_sold, is_active
- Stock tracking capabilities

#### Warehouse Model
- Multiple warehouse support
- Location-based inventory

#### PriceList Model
- Sales and purchase price list management
- Multi-currency pricing support

### 5. Accounting App (`/accounting/`)
**Financial management**

- **Tax**: Tax code and rate management
- **Account**: Chart of accounts
- **JournalEntry**: General ledger integration (placeholder for future)

## Business Logic & Utilities

### Sales Order Manager (`/sales/utils.py`)
**Comprehensive business logic for multi-vendor purchase order generation**

#### Key Functions:
- `analyze_purchase_requirements()`: Analyzes what needs to be purchased, grouped by vendor
- `generate_purchase_orders()`: Creates multiple POs automatically from SO requirements
- `get_status_summary()`: Comprehensive status tracking
- `create_customer_order_from_data()`: Order intake from external sources

#### Multi-Vendor Logic:
```python
# Example: One SO line may need items from multiple vendors
# SO Line: 100 units of Product X
# Vendor A: 60 units (primary vendor)
# Vendor B: 40 units (secondary vendor)
# Result: 2 separate POs generated automatically
```

## Views & Workflow

### Sales Views (`/sales/views.py`)
1. **Dashboard**: Status overview of all sales orders
2. **Order Intake**: Customer order entry form
3. **Purchase Order Generation**: Multi-vendor PO creation from SO
4. **Shipping & Invoicing**: Combined invoice/packing list generation

### URL Patterns (`/sales/urls.py`)
- `/dashboard/`: Main sales overview
- `/intake/`: New order entry
- `/generate-pos/<uuid>/`: PO generation for specific SO
- `/ship-invoice/<uuid>/`: Combined shipping/invoicing

## Data Migration

### Migration from iDempiere
**Complete data migration accomplished from legacy iDempiere system**

#### Migrated Entities:
- **340 Business Partners** (customers and vendors)
- **172 Sales Orders** with 355 order lines
- **141 Purchase Orders** with corresponding lines
- **77 Invoices** (sales and vendor bills)
- **56 Shipments** with movement tracking
- **210 Products** with categories and pricing

#### Migration Script: `/migrate_idempiere_data.py`
- Handles legacy ID mapping for data integrity
- Maintains audit trails and relationships
- Creates placeholder products for missing items
- Maps document statuses between systems

## Admin Interface

### Django Admin Configuration
- **Sales Orders**: Simplified admin with essential fields only
- **Inline editing**: Sales order lines, invoice lines, shipment lines
- **List filters**: Status, organization, dates, amounts
- **Search**: Document numbers, customer names, descriptions

### Access Issues Resolved
- **Previous 500 errors**: Fixed by simplifying admin configuration
- **Field mismatches**: Corrected migration script field mappings
- **PostgreSQL cursor errors**: Resolved through admin optimization

## Development & Deployment

### Project Structure
```
/opt/modern-erp/modern-erp/
├── manage.py
├── modern_erp/          # Main project settings
├── core/                # Base models and utilities
├── sales/               # Sales order management
├── purchasing/          # Purchase order management
├── inventory/           # Product and warehouse management
├── accounting/          # Financial management
├── venv/                # Python virtual environment
├── static/              # Static files
├── templates/           # HTML templates
└── migrate_idempiere_data.py  # Data migration script
```

### Key Commands
```bash
# Activate virtual environment
source venv/bin/activate

# Run Django commands
python manage.py shell
python manage.py migrate
python manage.py collectstatic

# Service management
systemctl status modern-erp
systemctl restart modern-erp

# Check logs
journalctl -u modern-erp -f
```

## Current System Status

### Data Counts (as of last migration):
- Sales Orders: 172
- Sales Order Lines: 355
- Business Partners: 340
- Purchase Orders: 141
- Products: 210

### Completed Features:
✅ Multi-vendor purchase order generation from sales orders
✅ Vendor mapping to products for auto-PO creation
✅ Partial shipment tracking
✅ Sales order dashboard with status tracking
✅ Customer order intake forms
✅ Complete data migration from iDempiere
✅ Admin interface optimization

### Pending Features:
🔄 Combined Invoice + Packing List view implementation
🔄 Packing label generation
🔄 Enhanced reporting capabilities

## Troubleshooting

### Common Issues:
1. **500 Errors in Admin**: Usually due to field mismatches or complex queries
2. **Migration Issues**: Check field names match model definitions
3. **Service Won't Start**: Check virtual environment and dependencies
4. **Database Connection**: Verify PostgreSQL service and credentials

### Log Locations:
- **Django Service**: `journalctl -u modern-erp`
- **Nginx**: `/var/log/nginx/`
- **PostgreSQL**: `/var/log/postgresql/`

## Security & Access

### Database Security:
- Remote access configured for development/admin
- User permissions properly scoped
- Connection encryption enabled

### Web Security:
- HTTPS configuration via Nginx
- Django security middleware enabled
- CSRF protection active

## Next Steps for Development

1. **Complete Invoice/Packing List Combined View**
2. **Implement Packing Label Generation**
3. **Add Advanced Reporting Dashboard**
4. **Enhance Multi-warehouse Support**
5. **Implement Advanced Inventory Tracking**
6. **Add Email Notifications for Order Status**
7. **Create API endpoints for external integrations**

---

**Last Updated**: June 16, 2025
**System Version**: Django 4.2.11 on Ubuntu Linux
**Database**: PostgreSQL 16 with 786 total migrated records