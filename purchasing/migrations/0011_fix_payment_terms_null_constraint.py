# Generated manually to fix payment_terms null constraint
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('purchasing', '0010_add_purchasing_performance_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE purchasing_purchaseorder ALTER COLUMN payment_terms_id DROP NOT NULL;",
            reverse_sql="ALTER TABLE purchasing_purchaseorder ALTER COLUMN payment_terms_id SET NOT NULL;"
        ),
    ]