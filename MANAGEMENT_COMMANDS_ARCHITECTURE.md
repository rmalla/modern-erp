# Management Commands Architecture

## Overview

This document defines the enterprise-grade organization structure for Django management commands in the Modern ERP system. Management commands provide a standardized, discoverable, and maintainable way to execute administrative tasks.

## Architecture Principles

### 1. **App-Based Organization**
- Each Django app contains its own management commands
- Commands are logically grouped by the domain they operate on
- Clear separation of concerns between different business areas

### 2. **Standardized Command Structure**
```
app_name/
  management/
    __init__.py
    commands/
      __init__.py
      command_name.py
      command_category/
        __init__.py
        specific_command.py
```

### 3. **Command Categories**

#### **Data Quality Commands** (`data_quality/`)
- Data validation and cleanup operations
- Orphan record identification and management
- Data integrity checks
- Duplicate detection and resolution

#### **Migration Commands** (`migration/`)
- Legacy data migration utilities
- Data transformation scripts
- One-time migration operations

#### **Maintenance Commands** (`maintenance/`)
- Regular system maintenance tasks
- Cache management
- Performance optimization utilities
- System health checks

#### **Report Commands** (`reports/`)
- Data analysis and reporting
- Business intelligence utilities
- Export and import operations

## Directory Structure

```
core/
  management/
    __init__.py
    commands/
      __init__.py
      data_quality/
        __init__.py
        mark_orphaned_business_partners.py
        cleanup_duplicate_records.py
        validate_data_integrity.py
      migration/
        __init__.py
        sync_opportunities_from_crm.py
        migrate_legacy_contacts.py
      maintenance/
        __init__.py
        clear_expired_cache.py
        optimize_database.py
      reports/
        __init__.py
        business_partner_analysis.py
        data_quality_report.py

sales/
  management/
    commands/
      data_quality/
        validate_order_integrity.py
        cleanup_orphaned_orders.py
      reports/
        sales_performance_report.py

purchasing/
  management/
    commands/
      data_quality/
        validate_purchase_orders.py
      reports/
        vendor_analysis.py

inventory/
  management/
    commands/
      data_quality/
        cleanup_orphaned_products.py
      maintenance/
        update_inventory_counts.py
```

## Command Naming Conventions

### Pattern: `<verb>_<noun>_<modifier>`

- **mark_orphaned_business_partners** - Mark business partners as orphaned
- **cleanup_duplicate_records** - Clean up duplicate database records
- **validate_data_integrity** - Validate system data integrity
- **sync_opportunities_from_crm** - Sync opportunities from CRM system
- **generate_sales_report** - Generate sales performance report

## Command Implementation Standards

### 1. **Base Command Structure**
```python
from django.core.management.base import BaseCommand
from django.db import transaction

class Command(BaseCommand):
    help = 'Clear description of what this command does'
    
    def add_arguments(self, parser):
        # Define command line arguments
        pass
    
    def handle(self, *args, **options):
        # Main command logic
        pass
```

### 2. **Required Features**
- **Help text**: Clear description of command purpose
- **Argument parsing**: Proper handling of command line arguments
- **Dry run mode**: Safe preview mode for destructive operations
- **Progress reporting**: Status updates for long-running operations
- **Error handling**: Graceful handling of errors with proper logging
- **Transaction safety**: Use database transactions for data modifications

### 3. **Standard Arguments**
- `--dry-run`: Preview changes without executing
- `--verbose`: Increase output verbosity
- `--quiet`: Suppress non-error output
- `--force`: Skip confirmation prompts (use with caution)

## Usage Examples

### Execute Commands
```bash
# Data quality commands
python manage.py mark_orphaned_business_partners
python manage.py mark_orphaned_business_partners --mark
python manage.py cleanup_duplicate_records --dry-run

# Migration commands
python manage.py sync_opportunities_from_crm --limit 100
python manage.py migrate_legacy_contacts --force

# Maintenance commands
python manage.py clear_expired_cache
python manage.py optimize_database --vacuum

# Report commands
python manage.py business_partner_analysis --export csv
python manage.py sales_performance_report --month 2025-06
```

### List Available Commands
```bash
# List all management commands
python manage.py help

# List commands by category
python manage.py help | grep data_quality
python manage.py help | grep migration
```

## Documentation Requirements

### 1. **Command Documentation**
Each command must include:
- Purpose and use cases
- Required vs optional arguments
- Usage examples
- Prerequisites and dependencies
- Potential risks and warnings

### 2. **Category README Files**
Each command category should have a README.md explaining:
- Category purpose and scope
- List of available commands
- Common usage patterns
- Best practices

## Security and Safety

### 1. **Dangerous Operations**
Commands that modify or delete data must:
- Require explicit confirmation
- Support dry-run mode
- Log all changes
- Use database transactions
- Provide rollback instructions where applicable

### 2. **Access Control**
- Production commands should require specific permissions
- Sensitive operations should be logged with user attribution
- Critical commands should require multi-factor authentication

## Monitoring and Logging

### 1. **Command Execution Logging**
- Log command start/end times
- Record user who executed the command
- Track success/failure status
- Log any errors or warnings

### 2. **Performance Monitoring**
- Track command execution time
- Monitor resource usage
- Alert on long-running operations

## Migration Path

### Phase 1: Create Structure
1. Create management command directories in each app
2. Add __init__.py files for proper Python packaging
3. Create category subdirectories

### Phase 2: Convert Existing Scripts
1. Convert standalone scripts to management commands
2. Add proper argument parsing and help text
3. Implement dry-run modes and safety features

### Phase 3: Documentation and Standards
1. Document all commands and categories
2. Create usage examples and best practices
3. Implement logging and monitoring

### Phase 4: Clean Up
1. Remove standalone scripts from project root
2. Update documentation and procedures
3. Train team on new command structure