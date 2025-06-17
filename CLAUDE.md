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
- **BusinessPartner**: Customers and vendors with flags (is_customer, is_vendor) - separated from manufacturers for clean transactional vs attributional data separation
- **Contact**: Contact persons associated with business partners - enables proper contact management per customer/vendor
- **BusinessPartnerLocation**: Address management system - multiple addresses per business partner with address types
- **User**: Django user extension
- **Currency**: Multi-currency support (default: USD)
- **UnitOfMeasure**: Product measurement units
- **PaymentTerms**: Master data for payment terms with net days, discount days, and discount percentages
- **Incoterms**: International commercial terms with codes, names, and descriptions
- **Opportunity**: Central document hub linking all transactions (sales orders, purchase orders, invoices, shipments)

### 2. Sales App (`/sales/`)
**Customer order management**

#### SalesOrder Model
- Document workflow: drafted → in_progress → waiting_payment → waiting_pickup → complete → closed
- **Opportunity tracking**: Links to central opportunity for project management
- **Payment terms**: Dropdown selection from PaymentTerms model
- **Incoterms**: Dropdown selection with location field (e.g., "EXW Miami Port")
- **Contact Management**: 
  - `internal_user`: Our company contact handling the order
  - `contact`: Customer contact for this order (filtered by business partner)
- **Address Management**: Multiple address support with business partner filtering
  - `business_partner_location`: Primary address
  - `bill_to_location`: Billing address  
  - `ship_to_location`: Shipping address
  - All addresses filtered by selected business partner after save
- Customer PO reference tracking
- Pricing: price_list, currency
- Delivery: warehouse, delivery_via, delivery_rule
- Status properties: delivery_status, purchase_status
- Totals: total_lines, grand_total
- **Admin Layout**: 2-column layout with Contact Information and Address Information sections

#### SalesOrderLine Model
- Product or charge-based line items
- Quantities: ordered, delivered, invoiced, reserved, to_purchase, on_purchase_order
- Pricing: price_entered, price_actual, discount, line_net_amount
- Tax handling
- Date tracking: promised, delivered

#### Invoice & InvoiceLine Models
- Standard invoicing with multiple types (standard, credit_memo, debit_memo, proforma)
- Links to sales orders
- **Contact Management**: Same dual-contact system as Sales Orders (internal_user + customer contact)
- Payment tracking: paid_amount, open_amount
- Posting flags for accounting integration

#### Shipment & ShipmentLine Models
- Delivery document management
- Movement types: customer_shipment, customer_return
- **Contact Management**: Same dual-contact system as Sales Orders (internal_user + customer contact)
- **Address Management**: Business partner filtered address selection
- Tracking numbers and freight costs
- Quantity tracking: movement_quantity, quantity_entered

### 3. Purchasing App (`/purchasing/`)
**Vendor order management**

#### PurchaseOrder & PurchaseOrderLine Models
- Vendor purchase orders with source tracking to sales orders
- **Contact Management**: 
  - `internal_user`: Our company contact handling the purchase order
  - `contact`: Vendor contact for this purchase order (filtered by business partner)
- **Address Management**: Vendor address filtering for bill_to and ship_to locations
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

#### Manufacturer Model
- **Clean separation**: Manufacturer as placeholder for product attribution (not transactional)
- Fields: code, name, brand_name, description
- Used for product manufacturer identification only

#### Product Model (Completely Redesigned)
- **Streamlined design**: Removed unnecessary flags and categories for cleaner data model
- **Key fields prioritized**: Manufacturer and manufacturer part number as primary identifiers
- **Admin organization**:
  - Product ID: Read-only identifier at top
  - Manufacturer: Manufacturer selection and part number grouped together
  - Basic Information: Name, short description (text box), long description, product type, UOM
  - Physical Properties: Weight, volume
  - Pricing: "Price" (was list_price), "Cost" (was standard_cost)
  - Accounting: Tax category, asset/expense/revenue accounts
- **Removed fields**: code (replaced by manufacturer_part_number), product_category, is_purchased, is_sold, is_stocked, is_bill_of_materials, is_verification_required, is_dropshipped, min_stock_level, shelf_life_days, max_stock_level
- **Enhanced descriptions**: Both short_description (TextField) and description for flexibility
- **Search optimization**: All admin search fields updated to use manufacturer_part_number instead of removed code field

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

## Contact and Address Management System

### Architecture Overview
**Comprehensive contact and address management system implemented across all document types**

#### Key Components:
1. **Contact Model**: Person-level contacts associated with business partners
2. **BusinessPartnerLocation Model**: Address management with multiple addresses per business partner
3. **Document Integration**: All sales and purchasing documents support dual-contact system

#### Dual-Contact System:
**Every document (Sales Orders, Purchase Orders, Invoices, Shipments) includes:**
- **Internal User**: Our company contact handling the document
- **External Contact**: Customer/vendor contact for the document

#### Smart Filtering:
- **Contact Dropdown**: Automatically filtered by selected business partner after save
- **Address Dropdowns**: All address fields (bill_to, ship_to, etc.) filtered by business partner
- **Admin Workflow**: Save document with business partner → Edit again → See filtered options

#### Admin Interface:
- **Contact Information Section**: Internal user + external contact dropdowns
- **Address Information Section**: Business partner location, bill_to, ship_to addresses
- **Help Text**: Clear instructions for users on filtering behavior
- **Form Validation**: Prevents invalid contact/address combinations

#### Implementation Details:
- **DocumentContactForm**: Custom Django form class handling filtering logic
- **No JavaScript**: Simple server-side filtering after document save
- **Consistent Pattern**: Same implementation across Sales, Purchasing, and all document types
- **User-Friendly**: Clear messaging about save-first-to-filter workflow

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

### Global Admin Standardization
- **Global 2-column layout**: Implemented via `/templates/admin/base.html` for consistent styling across entire ERP system
- **Responsive design**: Ensures fields are properly aligned and visually appealing
- **Standardization**: Guarantees uniform user experience throughout all admin interfaces

### Django Admin Configuration
- **Sales Orders**: Key fields prioritized at top (business partner, opportunity, dates, payment terms, incoterms)
- **Products**: Streamlined with manufacturer and part number prominently displayed
- **Inline editing**: Sales order lines, invoice lines, shipment lines
- **List filters**: Status, organization, dates, amounts, manufacturers
- **Search optimization**: Updated to use manufacturer_part_number across all product references
- **Field organization**: Logical grouping with proper section headers

### Access Issues Resolved
- **500 errors fixed**: Multiple issues resolved including payment_terms field mismatches, product field errors, staticfiles manifest issues
- **Field alignment**: Corrected migration script field mappings and admin field references
- **PostgreSQL integration**: Resolved cursor errors and column mismatches
- **Search functionality**: Updated all product references from code to manufacturer_part_number

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
- **Products: 245** (with real data from iDempiere)
- **Manufacturers: 71** (real companies: York, Caterpillar, Siemens, Baldor, etc.)
- **Product Categories: 7** (Dropship, Standard, Non-Items, etc.)

### Completed Features:
✅ Multi-vendor purchase order generation from sales orders
✅ Vendor mapping to products for auto-PO creation
✅ Partial shipment tracking
✅ Sales order dashboard with status tracking
✅ Customer order intake forms
✅ Complete data migration from iDempiere
✅ **Opportunity-centric workflow**: Central document hub linking all transactions
✅ **Payment terms and incoterms**: Dropdown-based selection with proper data models
✅ **Clean data architecture**: Separated transactional (BusinessPartner) from attributional (Manufacturer) entities
✅ **Streamlined product model**: Removed unnecessary flags and categories, prioritized manufacturer and part number
✅ **Global admin standardization**: Consistent 2-column layout across entire system
✅ **Enhanced product descriptions**: Flexible short and long description fields
✅ **Database optimization**: Updated field types, labels, and search functionality
✅ **Admin interface refinement**: Logical field grouping and visual organization
✅ **Real product data migration**: Successfully imported 245 real products with actual names, part numbers, and 71 manufacturers from iDempiere
✅ **Complete product catalog**: Products now have real manufacturers (York, Caterpillar, Siemens, etc.) and actual part numbers
✅ **Pricing preservation**: Maintained all historical pricing data from sales and purchase orders
✅ **Contact and Address Management**: Complete dual-contact system with business partner filtered dropdowns
✅ **Document Contact Integration**: All documents (Sales, Purchase, Invoice, Shipment) support internal + external contacts
✅ **Smart Address Filtering**: Business partner filtered address selection across all document types
✅ **Admin Contact Sections**: Dedicated Contact Information and Address Information sections in admin

### Pending Features:
🔄 Combined Invoice + Packing List view implementation
🔄 Packing label generation
🔄 Enhanced reporting capabilities

## Troubleshooting

### Common Issues (Resolved):
1. **500 Errors in Admin**: 
   - ✅ **Fixed**: Payment terms field mismatch (payment_terms field migration)
   - ✅ **Fixed**: Product admin field errors (default_vendor→primary_vendor, vendor_product_no→vendor_product_code)
   - ✅ **Fixed**: Staticfiles manifest entry error for custom CSS
   - ✅ **Fixed**: Product code field references updated to manufacturer_part_number
2. **Migration Issues**: Check field names match model definitions
3. **Service Won't Start**: Check virtual environment and dependencies
4. **Database Connection**: Verify PostgreSQL service and credentials

### Recent Database Schema Updates:
- **Migrations Applied**: 7 inventory migrations including field removals, additions, and type changes
- **PaymentTerms & Incoterms**: Added to core models with proper foreign key relationships
- **Product Optimization**: Removed 9+ unnecessary fields, added short_description, updated field labels
- **Search Fields**: Updated across all admin interfaces to use manufacturer_part_number
- **Contact System**: Added Contact and BusinessPartnerLocation models with full document integration
- **Document Contact Fields**: Added internal_user fields to all document types (Sales, Purchase, Invoice, Shipment)
- **Address Management**: Enhanced all documents with business partner filtered address selection

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

## Key Technical Achievements

### Data Architecture Excellence
- **Clean separation of concerns**: Transactional entities (BusinessPartner for vendors/customers) vs attributional data (Manufacturer for product brands)
- **Opportunity-centric design**: Central document hub linking all business transactions for better project tracking
- **Streamlined models**: Removed unnecessary complexity while maintaining essential business functionality

### User Experience Optimization
- **Global standardization**: Consistent 2-column layout across all admin interfaces
- **Logical field organization**: Key information prioritized and grouped for better usability
- **Enhanced search capabilities**: Optimized search across all models with proper field references

### Database Performance & Maintainability
- **Field optimization**: Removed 9+ unnecessary Product fields reducing database bloat
- **Proper data types**: TextField for descriptions, proper verbose names for clarity
- **Foreign key relationships**: Properly structured with appropriate on_delete strategies
- **Migration strategy**: Clean, incremental migrations maintaining data integrity

---

**Last Updated**: June 17, 2025
**System Version**: Django 4.2.11 on Ubuntu Linux
**Database**: PostgreSQL 16 with 786 total migrated records
**Major Features**: Contact and Address Management system implemented across all document types
**Latest Enhancement**: Dual-contact system with business partner filtered dropdowns for contacts and addresses
**Architecture**: Clean separation of transactional vs attributional data models with comprehensive contact management