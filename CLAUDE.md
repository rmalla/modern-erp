# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Overview

Modern ERP is a production Django-based enterprise resource planning system built on proven iDempiere patterns with modern technologies. The system features sophisticated approval workflows, comprehensive contact management, professional PDF generation, and enterprise-grade caching.

**Current Status**: Production system running at https://erp.r17a.com with 786+ migrated records from iDempiere, complete workflow system, and unified approval dashboard.

## Commands

### Virtual Environment & Basic Setup
```bash
# Navigate to project directory
cd /opt/modern-erp/modern-erp

# Activate virtual environment (Python 3.12)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Development Server
```bash
# Run development server
python manage.py runserver 0.0.0.0:8000

# Access at: https://erp.r17a.com
# Admin panel: https://erp.r17a.com/admin/
# Default credentials: admin/admin123
```

### Django Management Commands
```bash
# Database migrations
python manage.py migrate
python manage.py makemigrations
python manage.py showmigrations

# Create superuser
python manage.py createsuperuser

# Run tests
python manage.py test

# Validate Django project
python manage.py check

# Django shell with enhanced features
python manage.py shell_plus

# Collect static files
python manage.py collectstatic --noinput

# Database shell
python manage.py dbshell
```

### Service Management (Production)
```bash
# Service control
systemctl status modern-erp
systemctl restart modern-erp
systemctl stop modern-erp
systemctl start modern-erp

# View logs
journalctl -u modern-erp -f
journalctl -u modern-erp --since "1 hour ago"
```

### Database Operations
```bash
# PostgreSQL connection
# Host: 138.197.99.201:5432
# Database: modern_erp
# User: django_user
# Password: django_pass

# Direct database access
psql -h 138.197.99.201 -U django_user -d modern_erp

# Django database shell
python manage.py dbshell

# Data export/import
python manage.py dumpdata [app_name] > data.json
python manage.py loaddata data.json
```

### Redis Cache Management
```bash
# Test Redis connection
redis-cli ping

# Monitor Redis activity
redis-cli monitor

# Clear specific cache databases
redis-cli -n 1  # Default cache
redis-cli -n 2  # Sessions
redis-cli -n 3  # Static data

# Clear all caches (use with caution)
redis-cli flushall
```

### Workflow and Approval Management
```bash
# Access central workflow dashboard
# URL: https://erp.r17a.com/core/workflow/dashboard/

# View approval history across all document types
# URL: https://erp.r17a.com/core/workflow/history/

# Set up new document type workflows (shell_plus example)
python manage.py shell_plus -c "
from core.models import WorkflowDefinition, WorkflowState, WorkflowTransition
# Create workflow definition for new document type
# Follow patterns from setup_po_workflow.py examples
"

# Cache management for workflow performance
redis-cli -n 1 keys "workflow:*"  # View workflow cache keys
redis-cli -n 1 del "dashboard_*"  # Clear dashboard cache
```

### PDF Generation and Documents
```bash
# PDF endpoints for business documents
# Sales Order: /sales/order/{id}/pdf/
# Purchase Order: /purchasing/purchase-order/{id}/pdf/
# Invoice: /sales/invoice/{id}/pdf/

# Test PDF generation
curl -o test.pdf "https://erp.r17a.com/sales/order/{order_id}/pdf/"
```

### CRM Opportunity Sync (Regular Operation)
```bash
# Regular sync from CRM system
python manage.py sync_opportunities_from_crm

# Dry run to preview changes
python manage.py sync_opportunities_from_crm --dry-run

# Limit number of records processed
python manage.py sync_opportunities_from_crm --limit 100

# Force update existing opportunities
python manage.py sync_opportunities_from_crm --force
```

## File Organization

The project follows a clean, organized structure separating active code from one-time scripts:

### Directory Structure
```
/opt/modern-erp/modern-erp/
├── README.md, CLAUDE.md, ARCHITECTURE.md    # Core documentation
├── manage.py, requirements.txt               # Django core files
├── modern_erp/, core/, sales/, etc.         # Django applications
├── static/, staticfiles/, templates/        # Web assets
├── venv/                                     # Python environment
│
├── scripts/                                  # Organized scripts
│   ├── setup/                               # One-time setup scripts
│   │   ├── setup_basic_data.py
│   │   └── setup_invoice_workflow.py
│   └── migrations/legacy/                   # Historical migration scripts
│       ├── migrate_idempiere_data.py
│       ├── migrate_opportunities_from_crm.py
│       └── [other migration scripts]
│
├── docs/                                     # Documentation archive
│   └── analysis/                            # Technical analysis reports
│       ├── ARCHITECTURE_ANALYSIS_REPORT.md
│       └── database_analysis_report.md
│
├── config/                                   # Configuration files
│   └── ssh_config_fix.txt
│
└── archive/                                  # Historical files/backups
    └── modern-erp-backup.tar.gz
```

### Script Usage Guidelines
- **Active Operations**: Use Django management commands (e.g., `sync_opportunities_from_crm`)
- **One-time Setup**: Scripts in `scripts/setup/` for initial system configuration
- **Legacy Migration**: Scripts in `scripts/migrations/legacy/` for historical data import
- **Documentation**: Active docs in root, analysis reports in `docs/analysis/`

## Architecture Overview

### Technology Stack
- **Backend**: Django 4.2.11 with Django REST Framework
- **Database**: PostgreSQL 12+ with psycopg2
- **Authentication**: JWT (djangorestframework-simplejwt) + Session auth
- **Caching**: Redis via django-redis
- **API Documentation**: drf-spectacular (OpenAPI/Swagger)
- **Background Tasks**: Celery with Redis broker
- **Static Files**: WhiteNoise for production serving
- **Money Handling**: django-money for proper currency support

### Core Applications

1. **`core/`** - Foundation models and business logic
   - Extended Django User model with organization support
   - Business Partners (unified customer/vendor/employee model)
   - Workflow engine with configurable states and transitions
   - Multi-organization and department hierarchy
   - Currencies, units of measure, and contact management

2. **`accounting/`** - Financial management (US GAAP compliant)
   - Chart of Accounts with account types and hierarchies
   - Double-entry bookkeeping with journal entries
   - Tax management with rate configurations
   - Fiscal years and accounting periods
   - Financial reporting structures

3. **`inventory/`** - Product and warehouse management
   - Product catalog with categories and attributes
   - Multi-warehouse support with locations
   - Price lists with version control
   - Stock management and movements

4. **`sales/`** - Sales process management
   - Sales orders with line items and pricing
   - Customer invoicing with payment tracking
   - Opportunity and lead management
   - Remote transaction synchronization
   - Document workflow integration

5. **`purchasing/`** - Procurement management
   - Purchase orders with approval workflows
   - Vendor management and evaluation
   - Receipt processing and matching

### Key Architecture Patterns

1. **Base Model Pattern**: All models inherit from `BaseModel` providing:
   - UUID primary keys for distributed systems
   - Automatic audit fields (created, updated, created_by, updated_by)
   - Soft delete support with is_active flag
   - Organization-level data isolation

2. **Multi-Organization Design**: 
   - Every business entity has an organization foreign key
   - Automatic filtering based on user's organization
   - Support for cross-organization reporting with permissions

3. **Enterprise Workflow Engine**:
   - Universal document workflow system using Django GenericForeignKey
   - 6-model architecture: WorkflowDefinition, WorkflowState, WorkflowTransition, DocumentWorkflow, WorkflowApproval, UserPermission
   - Threshold-based approval routing ($1K sales orders, $5K purchase orders)
   - Progressive field locking based on workflow state
   - Complete approval audit trail with amount snapshots
   - Central approval dashboard across all document types

4. **API Design**:
   - RESTful APIs with consistent naming conventions
   - Automatic OpenAPI documentation generation
   - JWT authentication with session fallback
   - Pagination, filtering, and sorting support
   - Nested serializers for related data

5. **Custom Fields Support**:
   - JSON fields on core models for extensibility
   - No database migrations needed for custom attributes
   - Admin interface support for custom field editing

### Security Considerations
- JWT tokens with proper expiration
- CORS configuration for API access
- Django's built-in CSRF and XSS protection
- SQL injection prevention via ORM
- Row-level security through organization filtering
- Environment-based sensitive configuration

### Performance Optimizations
- Strategic database indexing on foreign keys and lookup fields
- Redis caching for frequently accessed data
- Select_related and prefetch_related for N+1 query prevention
- Database connection pooling
- Static file serving via WhiteNoise with compression

### Admin Interface Customizations
- Enhanced Django admin with inline editing
- Custom CSS for improved UX (2-column responsive layout)
- List filters and search configurations
- Bulk actions for common operations
- Export functionality via django-import-export

### Integration Points
- Remote transaction synchronization in sales module
- Legacy system migration scripts (iDempiere compatible)
- REST API endpoints for external system integration
- Event-driven architecture preparation for webhooks
- Background task processing via Celery

## Recent System Enhancements

### Unified Product Inline System
The system now features a unified template system for product selection across all document types:

- **Base Template**: `/templates/admin/core/product_inline_base.html` - Reusable template for any document type
- **Modal Product Search**: Advanced search with filters (name, manufacturer, part number, date range)
- **Product Creation**: Create new products directly from selection modal with manufacturer autocomplete
- **Template Variables**: Configurable via `document_type`, `app_name`, `admin_url_name` context variables
- **AJAX Endpoints**: Standardized patterns for `ajax_search_products`, `ajax_get_manufacturers`, `ajax_add_order_line`

**Implementation Pattern**:
```django
{# In document-specific template #}
{% with document_type="sales_order" app_name="sales" admin_url_name="admin:sales_salesorderline_change" %}
    {% include "admin/core/product_inline_base.html" %}
{% endwith %}
```

### Purchase Order Enhancements
- **Smart Defaults**: Automatic population of organization, currency, warehouse, price list, and date
- **Model-Level Defaults**: Functions like `get_default_organization()`, `get_today_date()`
- **Admin Defaults**: `get_changeform_initial_data()` method ensures defaults appear in forms

### Sales/Invoice Totals Calculation
- **Auto-Calculation**: `calculate_totals()` method on SalesOrder and Invoice models
- **Line Item Aggregation**: Automatically sums line amounts when stored totals are missing
- **PDF Integration**: Fallback calculation in PDF generation for legacy data

### Advanced Admin Customizations
- **Readonly Display Fields**: Custom display methods for inline forms (`product_display`, `quantity_display`, etc.)
- **Workflow-Aware Permissions**: Dynamic field locking based on document workflow state
- **Custom Templates**: Document-specific admin templates with enhanced UX

### Field Name Corrections
- **BaseModel Fields**: Uses `created`/`updated` (not `created_at`/`updated_at`)
- **Address Fields**: Removed deprecated `address3` references from `full_address` and `full_address_with_name` methods
- **Consistent Naming**: Standardized field names across all search and display functionality

## Development Patterns

### Adding New Document Types to Unified Product Selection
1. Create template: `/templates/admin/[app]/[model]line_inline.html`
2. Include base template with proper context variables
3. Add AJAX views: `ajax_search_products`, `ajax_get_manufacturers`, `ajax_add_order_line`  
4. Update admin inline class to use custom template and display methods
5. Add URL patterns for AJAX endpoints

### Model Field Access Patterns
- **Date Fields**: Use `model.created` and `model.updated` (BaseModel pattern)
- **Address Display**: Use `full_address` or `full_address_with_name` methods
- **Money Fields**: django-money handles currency and amount attributes automatically
- **Foreign Key Defaults**: Use callable functions for dynamic defaults