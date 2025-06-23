# Generated manually for accounting data integrity improvements
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0003_account_legacy_id_accounttype_legacy_id_and_more'),
    ]

    operations = [
        # Add check constraint to ensure fiscal year dates are logical
        migrations.RunSQL(
            "ALTER TABLE accounting_fiscalyear ADD CONSTRAINT chk_fiscal_year_date_range "
            "CHECK (end_date > start_date);",
            reverse_sql="ALTER TABLE accounting_fiscalyear DROP CONSTRAINT IF EXISTS chk_fiscal_year_date_range;"
        ),
        
        # Add check constraint to ensure period dates are logical
        migrations.RunSQL(
            "ALTER TABLE accounting_period ADD CONSTRAINT chk_period_date_range "
            "CHECK (end_date > start_date);",
            reverse_sql="ALTER TABLE accounting_period DROP CONSTRAINT IF EXISTS chk_period_date_range;"
        ),
        
        # Add check constraint to ensure tax rates are between 0 and 100
        migrations.RunSQL(
            "ALTER TABLE accounting_tax ADD CONSTRAINT chk_tax_rate_range "
            "CHECK (rate >= 0 AND rate <= 100);",
            reverse_sql="ALTER TABLE accounting_tax DROP CONSTRAINT IF EXISTS chk_tax_rate_range;"
        ),
        
        # Add check constraint to ensure journal line amounts are non-negative
        migrations.RunSQL(
            "ALTER TABLE accounting_journalline ADD CONSTRAINT chk_journal_line_amounts_non_negative "
            "CHECK (debit_amount >= 0 AND credit_amount >= 0);",
            reverse_sql="ALTER TABLE accounting_journalline DROP CONSTRAINT IF EXISTS chk_journal_line_amounts_non_negative;"
        ),
        
        # Add check constraint to ensure journal line has either debit OR credit, not both
        migrations.RunSQL(
            "ALTER TABLE accounting_journalline ADD CONSTRAINT chk_journal_line_debit_or_credit "
            "CHECK ((debit_amount = 0) OR (credit_amount = 0));",
            reverse_sql="ALTER TABLE accounting_journalline DROP CONSTRAINT IF EXISTS chk_journal_line_debit_or_credit;"
        ),
        
        # Add check constraint to ensure journal line has at least one amount > 0
        migrations.RunSQL(
            "ALTER TABLE accounting_journalline ADD CONSTRAINT chk_journal_line_amount_not_zero "
            "CHECK (debit_amount > 0 OR credit_amount > 0);",
            reverse_sql="ALTER TABLE accounting_journalline DROP CONSTRAINT IF EXISTS chk_journal_line_amount_not_zero;"
        ),
        
        # Add check constraint to ensure exchange rate is positive
        migrations.RunSQL(
            "ALTER TABLE accounting_journal ADD CONSTRAINT chk_journal_exchange_rate_positive "
            "CHECK (exchange_rate > 0);",
            reverse_sql="ALTER TABLE accounting_journal DROP CONSTRAINT IF EXISTS chk_journal_exchange_rate_positive;"
        ),
        
        # Add check constraint to ensure account hierarchy is logical (parent cannot be self)
        migrations.RunSQL(
            "ALTER TABLE accounting_account ADD CONSTRAINT chk_account_parent_not_self "
            "CHECK (parent_id IS NULL OR parent_id != id);",
            reverse_sql="ALTER TABLE accounting_account DROP CONSTRAINT IF EXISTS chk_account_parent_not_self;"
        ),
        
        # Add check constraint to ensure currency rate is positive in journal lines
        migrations.RunSQL(
            "ALTER TABLE accounting_journalline ADD CONSTRAINT chk_journal_line_currency_rate_positive "
            "CHECK (currency_rate > 0);",
            reverse_sql="ALTER TABLE accounting_journalline DROP CONSTRAINT IF EXISTS chk_journal_line_currency_rate_positive;"
        ),
        
        # Add check constraint to ensure journal is balanced when posted
        migrations.RunSQL(
            "ALTER TABLE accounting_journal ADD CONSTRAINT chk_journal_balanced_when_posted "
            "CHECK (NOT is_posted OR ABS(total_debit - total_credit) < 0.01);",
            reverse_sql="ALTER TABLE accounting_journal DROP CONSTRAINT IF EXISTS chk_journal_balanced_when_posted;"
        ),
    ]