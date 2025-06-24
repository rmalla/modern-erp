# Archive Directory

This directory contains historical files and backups that are no longer actively used but preserved for reference.

## Current Files

- `modern-erp-backup.tar.gz` - System backup (⚠️ Only 45 bytes - likely corrupted)

## Purpose

This directory serves as a storage location for:
- Historical backup files
- Deprecated configuration files
- Legacy documentation
- Obsolete scripts that may have historical value

## File Review

### Backup Files
- **Issue**: Current backup file appears corrupted (45 bytes)
- **Recommendation**: Replace with proper system backup
- **Action**: Implement automated backup strategy

### Cleanup Schedule
- Review archive contents quarterly
- Remove files older than 2 years unless required for compliance
- Compress large historical files

## Backup Strategy Recommendations

Instead of manual backup files, implement:

1. **Automated Database Backups**
   ```bash
   pg_dump -h 138.197.99.201 -U django_user modern_erp > backup_$(date +%Y%m%d).sql
   ```

2. **Application Code Backups**
   ```bash
   tar -czf app_backup_$(date +%Y%m%d).tar.gz --exclude=venv --exclude=staticfiles .
   ```

3. **Scheduled Backups**
   - Daily database dumps
   - Weekly application backups  
   - Monthly static file archives

4. **Backup Rotation**
   - Keep daily backups for 7 days
   - Keep weekly backups for 4 weeks
   - Keep monthly backups for 12 months

## Security Note

- Ensure backup files don't contain unencrypted sensitive data
- Store production backups in secure, off-site locations
- Test backup restoration procedures regularly