"""
Transaction synchronization utilities for sales orders.
Handles generation of transaction codes and syncing with remote payment system.
"""

import string
import secrets
import psycopg2
from psycopg2.extras import RealDictCursor
from django.conf import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Try to import remote database configuration
try:
    from .remote_db_config import REMOTE_DB_CONFIG
except ImportError:
    # Fallback configuration
    REMOTE_DB_CONFIG = {
        'host': 'malla-group.com',
        'port': 5432,
        'database': 'django_malla_group_next',
        'user': 'postgres',
        'password': None,  # Will need to be configured
    }


def generate_transaction_code(length=32):
    """
    Generate a secure random transaction code.
    
    Args:
        length (int): Length of the transaction code (default: 32)
    
    Returns:
        str: Random alphanumeric transaction code
    """
    # Use uppercase letters and digits for the transaction code
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def create_remote_transaction(sales_order):
    """
    Create a transaction record in the remote payment database.
    
    Args:
        sales_order: SalesOrder instance
    
    Returns:
        dict: Result with success status and transaction_id or error message
    """
    try:
        # Generate transaction code if not already present
        if not sales_order.transaction_id:
            sales_order.transaction_id = generate_transaction_code()
            sales_order.save(update_fields=['transaction_id'])
        
        # Prepare data for remote database
        transaction_data = {
            'transaction_id': sales_order.transaction_id,
            'customer_name': sales_order.business_partner.name,
            'customer_email': sales_order.contact.email if sales_order.contact else '',
            'customer_phone': sales_order.contact.phone if sales_order.contact else '',
            'customer_address': sales_order.ship_to_location.address1 if sales_order.ship_to_location else '',
            'customer_city': sales_order.ship_to_location.city if sales_order.ship_to_location else '',
            'customer_state': sales_order.ship_to_location.state if sales_order.ship_to_location else '',
            'customer_postal_code': sales_order.ship_to_location.postal_code if sales_order.ship_to_location else '',
            'customer_country': sales_order.ship_to_location.country if sales_order.ship_to_location else '',
            'sales_order_number': sales_order.document_no,
            'invoice_number': '',  # Will be filled when invoice is created
            'po_number': sales_order.customer_po_reference or '',
            'amount': float(sales_order.grand_total.amount),
            'currency': sales_order.currency.iso_code,
            'description': f'Sales Order {sales_order.document_no}',
            'payment_status': 'pending',
            'salesorder_date': sales_order.date_ordered,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
        }
        
        # Connect to remote database via SSH tunnel
        # Note: In production, you might want to use SSH tunneling or VPN
        # For now, we'll use direct connection with proper firewall rules
        
        conn = psycopg2.connect(**REMOTE_DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Insert transaction record
        insert_query = """
            INSERT INTO backend_transaction (
                transaction_id, customer_name, customer_email, customer_phone,
                customer_address, customer_city, customer_state, customer_postal_code,
                customer_country, sales_order_number, invoice_number, po_number,
                amount, currency, description, payment_status, salesorder_date,
                created_at, updated_at
            ) VALUES (
                %(transaction_id)s, %(customer_name)s, %(customer_email)s, %(customer_phone)s,
                %(customer_address)s, %(customer_city)s, %(customer_state)s, %(customer_postal_code)s,
                %(customer_country)s, %(sales_order_number)s, %(invoice_number)s, %(po_number)s,
                %(amount)s, %(currency)s, %(description)s, %(payment_status)s, %(salesorder_date)s,
                %(created_at)s, %(updated_at)s
            )
            ON CONFLICT (transaction_id) DO UPDATE SET
                updated_at = EXCLUDED.updated_at,
                sales_order_number = EXCLUDED.sales_order_number,
                amount = EXCLUDED.amount;
        """
        
        cursor.execute(insert_query, transaction_data)
        conn.commit()
        
        logger.info(f"Successfully created remote transaction {sales_order.transaction_id} for SO {sales_order.document_no}")
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'transaction_id': sales_order.transaction_id,
            'payment_url': f"https://www.malla-group.com/toolbox/paypal-payment-gateway?transaction={sales_order.transaction_id}",
            'message': 'Transaction created successfully'
        }
        
    except psycopg2.Error as e:
        logger.error(f"Database error creating remote transaction: {str(e)}")
        return {
            'success': False,
            'error': f"Database error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Error creating remote transaction: {str(e)}")
        return {
            'success': False,
            'error': f"Error: {str(e)}"
        }


def update_remote_transaction_invoice(sales_order, invoice_number):
    """
    Update remote transaction with invoice number when invoice is created.
    
    Args:
        sales_order: SalesOrder instance
        invoice_number: Invoice document number
    
    Returns:
        dict: Result with success status
    """
    if not sales_order.transaction_id:
        return {
            'success': False,
            'error': 'No transaction_id found for this sales order'
        }
    
    try:
        conn = psycopg2.connect(**REMOTE_DB_CONFIG)
        cursor = conn.cursor()
        
        update_query = """
            UPDATE backend_transaction 
            SET invoice_number = %s, updated_at = %s
            WHERE transaction_id = %s
        """
        
        cursor.execute(update_query, (invoice_number, datetime.now(), sales_order.transaction_id))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': 'Invoice number updated successfully'
        }
        
    except Exception as e:
        logger.error(f"Error updating remote transaction invoice: {str(e)}")
        return {
            'success': False,
            'error': f"Error: {str(e)}"
        }


def check_transaction_exists(transaction_id):
    """
    Check if a transaction ID already exists in the remote database.
    
    Args:
        transaction_id: Transaction ID to check
    
    Returns:
        bool: True if exists, False otherwise
    """
    try:
        conn = psycopg2.connect(**REMOTE_DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) FROM backend_transaction WHERE transaction_id = %s",
            (transaction_id,)
        )
        
        count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return count > 0
        
    except Exception as e:
        logger.error(f"Error checking transaction existence: {str(e)}")
        return False