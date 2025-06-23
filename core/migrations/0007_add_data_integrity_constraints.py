# Generated manually for data integrity improvements
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_documentworkflow_workflowdefinition_workflowstate_and_more'),
    ]

    operations = [
        # Add check constraint to ensure probability is between 0 and 100
        migrations.RunSQL(
            "ALTER TABLE core_opportunity ADD CONSTRAINT chk_opportunity_probability_range "
            "CHECK (probability >= 0 AND probability <= 100);",
            reverse_sql="ALTER TABLE core_opportunity DROP CONSTRAINT IF EXISTS chk_opportunity_probability_range;"
        ),
        
        # Update payment terms with 0 net_days to 1 to maintain business logic
        migrations.RunSQL(
            "UPDATE core_paymentterms SET net_days = 1 WHERE net_days = 0;",
            reverse_sql="-- No reverse needed for data update"
        ),
        
        # Add check constraint to ensure net_days is positive
        migrations.RunSQL(
            "ALTER TABLE core_paymentterms ADD CONSTRAINT chk_payment_terms_net_days_positive "
            "CHECK (net_days > 0);",
            reverse_sql="ALTER TABLE core_paymentterms DROP CONSTRAINT IF EXISTS chk_payment_terms_net_days_positive;"
        ),
        
        # Add check constraint to ensure discount_days is non-negative and less than net_days
        migrations.RunSQL(
            "ALTER TABLE core_paymentterms ADD CONSTRAINT chk_payment_terms_discount_valid "
            "CHECK (discount_days >= 0 AND discount_days <= net_days);",
            reverse_sql="ALTER TABLE core_paymentterms DROP CONSTRAINT IF EXISTS chk_payment_terms_discount_valid;"
        ),
        
        # Add check constraint to ensure discount_percent is between 0 and 100
        migrations.RunSQL(
            "ALTER TABLE core_paymentterms ADD CONSTRAINT chk_payment_terms_discount_percent_range "
            "CHECK (discount_percent >= 0 AND discount_percent <= 100);",
            reverse_sql="ALTER TABLE core_paymentterms DROP CONSTRAINT IF EXISTS chk_payment_terms_discount_percent_range;"
        ),
        
        # Add check constraint to ensure UOM precision is non-negative
        migrations.RunSQL(
            "ALTER TABLE core_unitofmeasure ADD CONSTRAINT chk_uom_precision_non_negative "
            "CHECK (precision >= 0);",
            reverse_sql="ALTER TABLE core_unitofmeasure DROP CONSTRAINT IF EXISTS chk_uom_precision_non_negative;"
        ),
        
        # Add check constraint to ensure currency precision is non-negative
        migrations.RunSQL(
            "ALTER TABLE core_currency ADD CONSTRAINT chk_currency_precision_non_negative "
            "CHECK (precision >= 0);",
            reverse_sql="ALTER TABLE core_currency DROP CONSTRAINT IF EXISTS chk_currency_precision_non_negative;"
        ),
        
        # Add check constraint to ensure number sequence increment is positive
        migrations.RunSQL(
            "ALTER TABLE core_numbersequence ADD CONSTRAINT chk_number_sequence_increment_positive "
            "CHECK (increment > 0);",
            reverse_sql="ALTER TABLE core_numbersequence DROP CONSTRAINT IF EXISTS chk_number_sequence_increment_positive;"
        ),
        
        # Add check constraint to ensure padding is non-negative
        migrations.RunSQL(
            "ALTER TABLE core_numbersequence ADD CONSTRAINT chk_number_sequence_padding_non_negative "
            "CHECK (padding >= 0);",
            reverse_sql="ALTER TABLE core_numbersequence DROP CONSTRAINT IF EXISTS chk_number_sequence_padding_non_negative;"
        ),
        
        # Add check constraint to ensure at least one address type is selected for BusinessPartnerLocation
        migrations.RunSQL(
            "ALTER TABLE core_businesspartnerlocation ADD CONSTRAINT chk_bpl_at_least_one_address_type "
            "CHECK (is_bill_to = true OR is_ship_to = true OR is_pay_from = true OR is_remit_to = true);",
            reverse_sql="ALTER TABLE core_businesspartnerlocation DROP CONSTRAINT IF EXISTS chk_bpl_at_least_one_address_type;"
        ),
        
        # Add check constraint to ensure approval threshold amount is positive when set
        migrations.RunSQL(
            "ALTER TABLE core_workflowdefinition ADD CONSTRAINT chk_workflow_approval_threshold_positive "
            "CHECK (approval_threshold_amount IS NULL OR approval_threshold_amount > 0);",
            reverse_sql="ALTER TABLE core_workflowdefinition DROP CONSTRAINT IF EXISTS chk_workflow_approval_threshold_positive;"
        ),
        
        # Add check constraint to ensure workflow state order is non-negative
        migrations.RunSQL(
            "ALTER TABLE core_workflowstate ADD CONSTRAINT chk_workflow_state_order_non_negative "
            "CHECK (\"order\" >= 0);",
            reverse_sql="ALTER TABLE core_workflowstate DROP CONSTRAINT IF EXISTS chk_workflow_state_order_non_negative;"
        ),
        
        # Add check constraint to ensure approval limit is positive when set
        migrations.RunSQL(
            "ALTER TABLE core_userpermission ADD CONSTRAINT chk_user_permission_approval_limit_positive "
            "CHECK (approval_limit IS NULL OR approval_limit > 0);",
            reverse_sql="ALTER TABLE core_userpermission DROP CONSTRAINT IF EXISTS chk_user_permission_approval_limit_positive;"
        ),
    ]