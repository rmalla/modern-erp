# Generated manually for strategic performance indexes
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_add_data_integrity_constraints'),
    ]

    operations = [
        # Business Partner performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_bp_type_active ON core_businesspartner (partner_type, is_active);",
            reverse_sql="DROP INDEX IF EXISTS idx_bp_type_active;"
        ),
        
# Removed search_key index as field was removed in migration 0010
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_bp_name_search ON core_businesspartner USING gin(to_tsvector('english', name));",
            reverse_sql="DROP INDEX IF EXISTS idx_bp_name_search;"
        ),
        
        # Opportunity performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_opportunity_stage_date ON core_opportunity (stage, date_opened);",
            reverse_sql="DROP INDEX IF EXISTS idx_opportunity_stage_date;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_opportunity_business_partner ON core_opportunity (business_partner_id, stage);",
            reverse_sql="DROP INDEX IF EXISTS idx_opportunity_business_partner;"
        ),
        
        # Contact performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_contact_bp_active ON core_contact (business_partner_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS idx_contact_bp_active;"
        ),
        
        # Business Partner Location indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_bpl_type_flags ON core_businesspartnerlocation (business_partner_id, is_bill_to, is_ship_to);",
            reverse_sql="DROP INDEX IF EXISTS idx_bpl_type_flags;"
        ),
        
        # User permissions performance
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_user_permission_active ON core_userpermission (user_id, permission_code, is_active);",
            reverse_sql="DROP INDEX IF EXISTS idx_user_permission_active;"
        ),
        
        # Workflow performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_workflow_state_order ON core_workflowstate (workflow_id, \"order\");",
            reverse_sql="DROP INDEX IF EXISTS idx_workflow_state_order;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_document_workflow_content ON core_documentworkflow (content_type_id, object_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_document_workflow_content;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_workflow_approval_status ON core_workflowapproval (document_workflow_id, status, requested_at);",
            reverse_sql="DROP INDEX IF EXISTS idx_workflow_approval_status;"
        ),
    ]