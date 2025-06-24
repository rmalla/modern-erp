# Scripts Directory

This directory contains organized scripts for the Modern ERP system.

## Directory Structure

### `/setup/`
**Purpose**: One-time system initialization scripts
**When to use**: During initial system setup or major configuration changes

- `setup_basic_data.py` - Creates core master data (organizations, currencies, UOMs)
- `setup_invoice_workflow.py` - Configures invoice approval workflows

**Usage**:
```bash
# Run during initial system setup
python scripts/setup/setup_basic_data.py
python scripts/setup/setup_invoice_workflow.py
```

### `/migrations/legacy/`
**Purpose**: Historical data migration scripts from legacy systems
**When to use**: One-time data import from iDempiere or other legacy systems

#### iDempiere Migration Scripts:
- `migrate_contacts_and_data.py` - Complete data migration with contacts/addresses
- `migrate_idempiere_data.py` - Core business document migration
- `migrate_invoice_lines_only.py` - Specific invoice line data repair
- `migrate_invoices_only.py` - Sales invoice migration only
- `migrate_purchase_orders_only.py` - Purchase order migration only
- `migrate_real_products.py` - Product/manufacturer data migration
- `migrate_sales_orders_only.py` - Sales order migration only
- `recreate_products.py` - Product data reconstruction from order history

#### CRM Migration Scripts:
- `migrate_opportunities_from_crm.py` - Original CRM opportunity import script

**Note**: These are archived legacy scripts. For regular CRM sync, use the Django management command:
```bash
python manage.py sync_opportunities_from_crm
```

## Regular Operations

### CRM Opportunity Sync
For regular opportunity synchronization from the CRM system, use the Django management command instead of the legacy script:

```bash
# Regular sync (recommended)
python manage.py sync_opportunities_from_crm

# Dry run to see what would be imported
python manage.py sync_opportunities_from_crm --dry-run

# Limit number of records
python manage.py sync_opportunities_from_crm --limit 100

# Force update existing opportunities
python manage.py sync_opportunities_from_crm --force
```

## Archive Policy

### Setup Scripts
- Keep active until system is fully deployed
- Archive after successful production deployment
- Document any custom changes made during setup

### Migration Scripts
- Archive after successful data migration
- Keep for reference and rollback scenarios
- Remove after 6 months if no issues found

## Best Practices

1. **Always backup** before running any script
2. **Test on staging** environment first
3. **Use dry-run options** when available
4. **Monitor logs** for errors during execution
5. **Document any customizations** made to scripts