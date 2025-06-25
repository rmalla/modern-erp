# Data Quality Management Commands

This directory contains Django management commands for maintaining data quality in the Core application.

## Available Commands

### mark_orphaned_business_partners
Identifies and marks business partners that have no locations and no related documents as orphaned for cleanup review.

**Purpose**: Help identify business partners that were created during data migration but have no actual business activity (no locations, no sales orders, no invoices, no purchase orders, no vendor bills).

**Usage:**
```bash
# Preview what would be marked (safe dry run)
python manage.py mark_orphaned_business_partners

# Actually mark the orphaned business partners
python manage.py mark_orphaned_business_partners --mark

# Remove all orphan flags (reset)
python manage.py mark_orphaned_business_partners --unmark

# Quiet mode (minimal output)
python manage.py mark_orphaned_business_partners --mark --quiet
```

**Safety Features:**
- Dry run mode by default (requires explicit --mark flag)
- Database transactions for data integrity
- Reversible operation with --unmark flag
- Detailed analysis and reporting

**Admin Integration:**
After marking orphans, use the Django Admin interface:
1. Go to Core > Business Partners
2. Filter by "Is orphan: Yes"
3. Review and bulk delete unwanted records

## Best Practices

### Before Running Commands
1. **Backup**: Always backup your database before running data modification commands
2. **Test**: Run commands in dry-run mode first to preview changes
3. **Review**: Carefully review the list of affected records

### Command Execution
1. **Start with dry run**: Always run without flags first to see what would be affected
2. **Use quiet mode**: For scheduled/automated execution, use --quiet flag
3. **Monitor logs**: Check Django logs for any errors or warnings

### Data Safety
1. **Transactions**: All data modifications use database transactions
2. **Reversibility**: Most operations can be reversed (e.g., --unmark flag)
3. **Validation**: Commands validate data before making changes

## Common Workflows

### Cleaning Up Business Partner Data
```bash
# 1. Analyze what would be marked as orphaned
python manage.py mark_orphaned_business_partners

# 2. Mark the orphaned records
python manage.py mark_orphaned_business_partners --mark

# 3. Review in Django Admin (filter by "Is orphan: Yes")
# 4. Delete unwanted records using admin bulk actions

# 5. If needed, reset all orphan flags
python manage.py mark_orphaned_business_partners --unmark
```

### Scheduled Maintenance
```bash
# For automated/scheduled execution
python manage.py mark_orphaned_business_partners --mark --quiet
```

## Troubleshooting

### Command Not Found
If you get "Unknown command" error:
1. Ensure you're in the project directory
2. Activate the virtual environment: `source venv/bin/activate`
3. Check that `__init__.py` files exist in the management command directories

### Permission Errors
Ensure the user running the command has:
- Read/write access to the database
- Proper Django permissions for the Business Partner model

### Performance Issues
For large datasets:
- Commands use efficient database queries with annotations
- Progress is shown for long-running operations
- Consider running during off-peak hours

## Development Guidelines

When adding new data quality commands:

1. **Follow naming convention**: `verb_noun_modifier` (e.g., `validate_contact_integrity`)
2. **Include help text**: Clear description of what the command does
3. **Add dry-run mode**: Always support preview mode for destructive operations
4. **Use transactions**: Wrap data modifications in database transactions
5. **Provide feedback**: Show progress and results to the user
6. **Document thoroughly**: Include docstrings and usage examples