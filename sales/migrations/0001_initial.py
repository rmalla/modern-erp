# Generated by Django 4.2.11 on 2025-06-16 16:40

from decimal import Decimal
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import djmoney.models.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('purchasing', '0001_initial'),
        ('inventory', '0001_initial'),
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounting', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SalesOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('document_no', models.CharField(max_length=50, unique=True)),
                ('description', models.TextField(blank=True)),
                ('doc_status', models.CharField(choices=[('drafted', 'Drafted'), ('in_progress', 'In Progress'), ('waiting_payment', 'Waiting Payment'), ('waiting_pickup', 'Waiting Pickup'), ('complete', 'Complete'), ('closed', 'Closed'), ('reversed', 'Reversed'), ('voided', 'Voided')], default='drafted', max_length=20)),
                ('date_ordered', models.DateField()),
                ('date_promised', models.DateField(blank=True, null=True)),
                ('date_delivered', models.DateField(blank=True, null=True)),
                ('bill_to_address', models.TextField(blank=True)),
                ('ship_to_address', models.TextField(blank=True)),
                ('payment_terms', models.CharField(default='Net 30', max_length=100)),
                ('total_lines_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('total_lines', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('grand_total_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('grand_total', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('delivery_via', models.CharField(blank=True, max_length=100)),
                ('delivery_rule', models.CharField(default='Availability', max_length=50)),
                ('freight_cost_rule', models.CharField(default='Freight Included', max_length=50)),
                ('is_printed', models.BooleanField(default=False)),
                ('is_delivered', models.BooleanField(default=False)),
                ('is_invoiced', models.BooleanField(default=False)),
                ('is_drop_ship', models.BooleanField(default=False)),
                ('business_partner', models.ForeignKey(limit_choices_to={'is_customer': True}, on_delete=django.db.models.deletion.PROTECT, to='core.businesspartner')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.currency')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.organization')),
                ('price_list', models.ForeignKey(limit_choices_to={'is_sales_price_list': True}, on_delete=django.db.models.deletion.PROTECT, to='inventory.pricelist')),
                ('sales_rep', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='updated_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='inventory.warehouse')),
            ],
            options={
                'ordering': ['-date_ordered', 'document_no'],
            },
        ),
        migrations.CreateModel(
            name='SalesOrderLine',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('line_no', models.IntegerField()),
                ('description', models.TextField(blank=True)),
                ('quantity_ordered', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ('quantity_delivered', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('quantity_invoiced', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('quantity_reserved', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('price_entered_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('price_entered', djmoney.models.fields.MoneyField(decimal_places=2, max_digits=15)),
                ('price_actual_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('price_actual', djmoney.models.fields.MoneyField(decimal_places=2, max_digits=15)),
                ('price_list_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('price_list', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('discount', models.DecimalField(decimal_places=4, default=0, help_text='Percentage discount', max_digits=7)),
                ('line_net_amount_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('line_net_amount', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('tax_amount_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('tax_amount', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('date_promised', models.DateField(blank=True, null=True)),
                ('date_delivered', models.DateField(blank=True, null=True)),
                ('charge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='purchasing.charge')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='sales.salesorder')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='inventory.product')),
                ('tax', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounting.tax')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='updated_%(class)s', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['order', 'line_no'],
                'unique_together': {('order', 'line_no')},
            },
        ),
        migrations.CreateModel(
            name='Shipment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('document_no', models.CharField(max_length=50, unique=True)),
                ('description', models.TextField(blank=True)),
                ('doc_status', models.CharField(choices=[('drafted', 'Drafted'), ('in_progress', 'In Progress'), ('complete', 'Complete'), ('closed', 'Closed'), ('reversed', 'Reversed'), ('voided', 'Voided')], default='drafted', max_length=20)),
                ('movement_type', models.CharField(choices=[('customer_shipment', 'Customer Shipment'), ('customer_return', 'Customer Return'), ('vendor_receipt', 'Vendor Receipt'), ('vendor_return', 'Vendor Return')], default='customer_shipment', max_length=20)),
                ('movement_date', models.DateField()),
                ('date_received', models.DateField(blank=True, null=True)),
                ('delivery_via', models.CharField(blank=True, max_length=100)),
                ('tracking_no', models.CharField(blank=True, max_length=100)),
                ('freight_amount_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('freight_amount', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('is_printed', models.BooleanField(default=False)),
                ('is_in_transit', models.BooleanField(default=False)),
                ('business_partner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.businesspartner')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.organization')),
                ('sales_order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.salesorder')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='updated_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='inventory.warehouse')),
            ],
            options={
                'ordering': ['-movement_date', 'document_no'],
            },
        ),
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('document_no', models.CharField(max_length=50, unique=True)),
                ('description', models.TextField(blank=True)),
                ('doc_status', models.CharField(choices=[('drafted', 'Drafted'), ('in_progress', 'In Progress'), ('complete', 'Complete'), ('closed', 'Closed'), ('reversed', 'Reversed'), ('paid', 'Paid'), ('voided', 'Voided')], default='drafted', max_length=20)),
                ('invoice_type', models.CharField(choices=[('standard', 'Standard Invoice'), ('credit_memo', 'Credit Memo'), ('debit_memo', 'Debit Memo'), ('proforma', 'Pro Forma')], default='standard', max_length=20)),
                ('date_invoiced', models.DateField()),
                ('date_accounting', models.DateField()),
                ('due_date', models.DateField()),
                ('bill_to_address', models.TextField(blank=True)),
                ('payment_terms', models.CharField(default='Net 30', max_length=100)),
                ('total_lines_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('total_lines', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('tax_amount_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('tax_amount', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('grand_total_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('grand_total', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('paid_amount_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('paid_amount', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('open_amount_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('open_amount', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('is_printed', models.BooleanField(default=False)),
                ('is_paid', models.BooleanField(default=False)),
                ('is_posted', models.BooleanField(default=False)),
                ('business_partner', models.ForeignKey(limit_choices_to={'is_customer': True}, on_delete=django.db.models.deletion.PROTECT, to='core.businesspartner')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.currency')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.organization')),
                ('price_list', models.ForeignKey(limit_choices_to={'is_sales_price_list': True}, on_delete=django.db.models.deletion.PROTECT, to='inventory.pricelist')),
                ('sales_order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.salesorder')),
                ('sales_rep', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='updated_%(class)s', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date_invoiced', 'document_no'],
            },
        ),
        migrations.CreateModel(
            name='ShipmentLine',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('line_no', models.IntegerField()),
                ('description', models.TextField(blank=True)),
                ('movement_quantity', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ('quantity_entered', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('order_line', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.salesorderline')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='inventory.product')),
                ('shipment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='sales.shipment')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='updated_%(class)s', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['shipment', 'line_no'],
                'unique_together': {('shipment', 'line_no')},
            },
        ),
        migrations.CreateModel(
            name='InvoiceLine',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('line_no', models.IntegerField()),
                ('description', models.TextField(blank=True)),
                ('quantity_invoiced', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ('price_entered_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('price_entered', djmoney.models.fields.MoneyField(decimal_places=2, max_digits=15)),
                ('price_actual_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('price_actual', djmoney.models.fields.MoneyField(decimal_places=2, max_digits=15)),
                ('discount', models.DecimalField(decimal_places=4, default=0, help_text='Percentage discount', max_digits=7)),
                ('line_net_amount_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('line_net_amount', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('tax_amount_currency', djmoney.models.fields.CurrencyField(choices=[('GBP', 'British Pound'), ('CAD', 'Canadian Dollar'), ('EUR', 'Euro'), ('USD', 'US Dollar')], default='USD', editable=False, max_length=3)),
                ('tax_amount', djmoney.models.fields.MoneyField(decimal_places=2, default=Decimal('0'), max_digits=15)),
                ('charge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='purchasing.charge')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_%(class)s', to=settings.AUTH_USER_MODEL)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='sales.invoice')),
                ('order_line', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sales.salesorderline')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='inventory.product')),
                ('tax', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounting.tax')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='updated_%(class)s', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['invoice', 'line_no'],
                'unique_together': {('invoice', 'line_no')},
            },
        ),
    ]
