# Management Commands Quick Reference Guide

## Overview

Modern ERP now uses **Django Management Commands** for all administrative scripts. This provides a standardized, discoverable, and maintainable approach to system operations.

## Key Benefits

### ✅ **Enterprise Features**
- **Discoverable**: All commands appear in `python manage.py help`
- **Consistent**: Standardized argument parsing and help text
- **Safe**: Built-in dry-run modes and transaction safety
- **Auditable**: Proper logging and error handling
- **Documented**: Comprehensive help and usage examples

### ✅ **Developer Experience**
- **IDE Integration**: Commands work with Django-aware IDEs
- **Testing**: Can be unit tested like any Django code
- **Debugging**: Full Django context and debugging capabilities
- **Deployment**: Easy to integrate with CI/CD pipelines

## Current Commands

### Data Quality Commands

#### `mark_orphaned_business_partners`
**Purpose**: Mark business partners with no locations or related documents for cleanup review

**Usage:**
```bash
# Safe preview (dry run)
python manage.py mark_orphaned_business_partners

# Actually mark orphaned records
python manage.py mark_orphaned_business_partners --mark

# Reset all orphan flags
python manage.py mark_orphaned_business_partners --unmark

# Quiet mode for automation
python manage.py mark_orphaned_business_partners --mark --quiet
```

**Admin Integration**: Filter by "Is orphan: Yes" in Business Partners admin

### Migration Commands

#### `sync_opportunities_from_crm`
**Purpose**: Sync opportunities from remote CRM system

**Location**: `core/management/commands/migration/`

**Usage:**
```bash
# Sync with preview
python manage.py sync_opportunities_from_crm --dry-run

# Sync limited number
python manage.py sync_opportunities_from_crm --limit 100

# Force update existing
python manage.py sync_opportunities_from_crm --force
```

## Command Discovery

### List All Commands
```bash
python manage.py help
```

### Get Help for Specific Command
```bash
python manage.py help mark_orphaned_business_partners
python manage.py mark_orphaned_business_partners --help
```

### Search for Commands
```bash
python manage.py help | grep orphan
python manage.py help | grep data
python manage.py help | grep sync
```

## Best Practices

### For Users

#### 1. **Always Start with Dry Run**
```bash
# ✅ Good - Safe preview first
python manage.py mark_orphaned_business_partners
python manage.py mark_orphaned_business_partners --mark

# ❌ Risky - Direct execution
python manage.py mark_orphaned_business_partners --mark
```

#### 2. **Use Help Documentation**
```bash
# Get detailed help
python manage.py mark_orphaned_business_partners --help

# Understand what command does
python manage.py help mark_orphaned_business_partners
```

#### 3. **Backup Before Destructive Operations**
```bash
# Always backup before major changes
pg_dump modern_erp > backup_before_cleanup.sql
python manage.py mark_orphaned_business_partners --mark
```

### For Developers

#### 1. **Follow Naming Conventions**
- **Pattern**: `verb_noun_modifier`
- **Examples**: `mark_orphaned_business_partners`, `sync_opportunities_from_crm`
- **Avoid**: Generic names like `cleanup`, `fix_data`

#### 2. **Include Required Features**
```python
class Command(BaseCommand):
    help = 'Clear description of command purpose'
    
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--quiet', action='store_true')
    
    def handle(self, *args, **options):
        with transaction.atomic():
            # Command logic here
            pass
```

#### 3. **Safety Features**
- **Dry run mode**: Preview changes without executing
- **Database transactions**: Ensure data integrity
- **Proper error handling**: Graceful failure with clear messages
- **Progress reporting**: Show status for long operations

## Directory Structure

```
core/
  management/
    commands/
      mark_orphaned_business_partners.py    # Data quality
      migration/
        sync_opportunities_from_crm.py      # CRM sync
        
sales/
  management/
    commands/
      # Future sales-specific commands
      
purchasing/
  management/
    commands/
      # Future purchasing-specific commands
```

## Migration from Old Scripts

### ✅ **Completed**
- `mark_orphaned_business_partners.py` → Django management command
- `sync_opportunities_from_crm.py` → Moved to migration category
- Removed standalone scripts from project root

### 📋 **Future Improvements**
- Add more data quality commands for other models
- Create maintenance commands for system upkeep
- Develop reporting commands for business intelligence

## Common Workflows

### Business Partner Cleanup
```bash
# 1. Preview orphaned records
python manage.py mark_orphaned_business_partners

# 2. Mark them for review
python manage.py mark_orphaned_business_partners --mark

# 3. Review in Django Admin
#    → Business Partners → Filter: "Is orphan: Yes"

# 4. Delete unwanted records using admin bulk actions

# 5. Reset flags if needed
python manage.py mark_orphaned_business_partners --unmark
```

### Scheduled Operations
```bash
# For automated/scheduled execution
python manage.py mark_orphaned_business_partners --mark --quiet
python manage.py sync_opportunities_from_crm --limit 50 --quiet
```

## Troubleshooting

### Command Not Found
```bash
# Ensure you're in the right directory and virtual environment
cd /opt/modern-erp/modern-erp
source venv/bin/activate
python manage.py help
```

### Permission Issues
```bash
# Ensure proper database permissions
# Check Django settings for database configuration
```

### Performance Issues
```bash
# Use quiet mode for large operations
python manage.py command_name --quiet

# Consider running during off-peak hours
# Monitor database performance during execution
```

## Security Considerations

### Production Use
- **Backup first**: Always backup before destructive operations
- **Test staging**: Run commands on staging environment first
- **Monitor logs**: Check application and database logs
- **Limit scope**: Use filters and limits where available

### Access Control
- Commands require Django database access
- Consider implementing command-specific permissions
- Log command execution for audit trails

## Future Enhancements

### Planned Features
- **Category organization**: Subdirectory support for command categories
- **Progress bars**: Visual progress indicators for long operations
- **Rollback commands**: Automatic rollback capabilities
- **Scheduling integration**: Integration with task schedulers
- **Notification system**: Email/Slack notifications for command completion

### Development Roadmap
1. **Phase 1**: Convert remaining legacy scripts
2. **Phase 2**: Add comprehensive test coverage
3. **Phase 3**: Implement advanced safety features
4. **Phase 4**: Create command scheduling system