# Generated manually for accounting performance indexes
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0004_add_accounting_data_integrity_constraints'),
    ]

    operations = [
        # Journal performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_journal_accounting_date ON accounting_journal (accounting_date, is_posted);",
            reverse_sql="DROP INDEX IF EXISTS idx_journal_accounting_date;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_journal_period_date ON accounting_journal (period_id, accounting_date);",
            reverse_sql="DROP INDEX IF EXISTS idx_journal_period_date;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_journal_type_date ON accounting_journal (journal_type, accounting_date);",
            reverse_sql="DROP INDEX IF EXISTS idx_journal_type_date;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_journal_source_document ON accounting_journal (source_document_type, source_document_id) WHERE source_document_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_journal_source_document;"
        ),
        
        # Journal Line performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_journal_line_account ON accounting_journalline (account_id, journal_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_journal_line_account;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_journal_line_amounts ON accounting_journalline (account_id, debit_amount, credit_amount);",
            reverse_sql="DROP INDEX IF EXISTS idx_journal_line_amounts;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_journal_line_business_partner ON accounting_journalline (business_partner_id) WHERE business_partner_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_journal_line_business_partner;"
        ),
        
        # Account performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_account_type_active ON accounting_account (account_type_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS idx_account_type_active;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_account_parent_hierarchy ON accounting_account (parent_id, code) WHERE parent_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_account_parent_hierarchy;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_account_chart_code ON accounting_account (chart_of_accounts_id, code);",
            reverse_sql="DROP INDEX IF EXISTS idx_account_chart_code;"
        ),
        
        # Period performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_period_fiscal_year_dates ON accounting_period (fiscal_year_id, start_date, end_date);",
            reverse_sql="DROP INDEX IF EXISTS idx_period_fiscal_year_dates;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_period_open_status ON accounting_period (is_open, fiscal_year_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_period_open_status;"
        ),
        
        # Tax performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_tax_category_rate ON accounting_tax (tax_category_id, rate);",
            reverse_sql="DROP INDEX IF EXISTS idx_tax_category_rate;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_tax_validity_dates ON accounting_tax (valid_from, valid_to);",
            reverse_sql="DROP INDEX IF EXISTS idx_tax_validity_dates;"
        ),
    ]