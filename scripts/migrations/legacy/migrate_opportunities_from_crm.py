#!/usr/bin/env python3
"""
Opportunities Migration Script from Remote CRM

This script migrates opportunities from the remote CRM MySQL database
to the Django ERP system, filtering for sales_stage containing 'Proces'.
"""

import os
import sys
import django
import pymysql
import re
from decimal import Decimal
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'modern_erp.settings')
django.setup()

from django.db import transaction
from core.models import BusinessPartner, Organization, Currency, User, Opportunity

def get_connection():
    """Get connection to remote CRM database"""
    if not hasattr(get_connection, 'connection'):
        get_connection.connection = None

    try:
        if get_connection.connection and get_connection.connection.open:
            get_connection.connection.ping(reconnect=False)  # Ping the server without automatic reconnection
            print("get_connection: Connection is already established and open, nothing to do")
        else:
            raise pymysql.MySQLError("Connection is closed or not established.")
    except (AttributeError, pymysql.MySQLError, TypeError) as e:
        print("get_connection: Connection check appears offline, creating new connection:", e)
        get_connection.connection = pymysql.connect(
            host='crm.malla-group.com',
            port=3306,
            user='crm_user',
            password='NgYgbZtE7ssljyf6gMC3oiCLZ0nbOlfN',
            db='crm',
            charset='utf8'
        )
        print("get_connection: New connection established")

    return get_connection.connection

def extract_opportunity_number(opp_code_c):
    """Extract opportunity number from opp_code_c field"""
    if not opp_code_c:
        return None
    
    # Look for patterns like "Q #123054" or similar
    match = re.search(r'#(\d+)', opp_code_c)
    if match:
        return match.group(1)
    
    # If no # pattern, try to extract any number sequence
    match = re.search(r'(\d+)', opp_code_c)
    if match:
        return match.group(1)
    
    return None

def map_sales_stage_to_opportunity_stage(sales_stage):
    """Map CRM sales stage to Django opportunity stage"""
    if not sales_stage:
        return 'prospecting'
    
    sales_stage_lower = sales_stage.lower()
    
    if 'proces' in sales_stage_lower:  # Updated to match 'Proces'
        return 'proposal'  # Processing likely means actively working on proposal
    elif 'prospect' in sales_stage_lower:
        return 'prospecting'
    elif 'qualif' in sales_stage_lower:
        return 'qualification'
    elif 'proposal' in sales_stage_lower or 'quote' in sales_stage_lower:
        return 'proposal'
    elif 'negotiat' in sales_stage_lower:
        return 'negotiation'
    elif 'closed' in sales_stage_lower and 'won' in sales_stage_lower:
        return 'closed_won'
    elif 'closed' in sales_stage_lower and 'lost' in sales_stage_lower:
        return 'closed_lost'
    elif 'hold' in sales_stage_lower:
        return 'on_hold'
    else:
        return 'prospecting'  # Default

def get_or_create_default_data():
    """Get or create default data needed for opportunities"""
    # Get default organization
    default_org = Organization.objects.filter(is_active=True).first()
    if not default_org:
        print("ERROR: No active organization found. Please create one first.")
        sys.exit(1)
    
    # Get default currency (USD)
    default_currency = Currency.objects.filter(iso_code='USD').first()
    if not default_currency:
        print("ERROR: USD currency not found. Please create it first.")
        sys.exit(1)
    
    # Get default user for created_by
    default_user = User.objects.filter(is_active=True).first()
    if not default_user:
        print("ERROR: No active user found. Please create one first.")
        sys.exit(1)
    
    # Get or create default "Unknown" business partner for opportunities
    default_bp, created = BusinessPartner.objects.get_or_create(
        search_key='UNKNOWN_OPPORTUNITY',
        defaults={
            'code': 'UNKNOWN',
            'name': 'Unknown Customer (From CRM)',
            'partner_type': 'customer',
            'is_customer': True,
        }
    )
    if created:
        print("Created default 'Unknown' business partner for opportunities")
    
    return default_org, default_currency, default_user, default_bp

def safe_date_conversion(date_value):
    """Safely convert date/datetime to date object"""
    if date_value is None:
        return None
    if hasattr(date_value, 'date'):
        # It's a datetime object, extract date
        return date_value.date()
    else:
        # It's already a date object
        return date_value

def truncate_opportunities():
    """Truncate all existing opportunities"""
    print("Truncating existing opportunities...")
    count = Opportunity.objects.count()
    if count > 0:
        Opportunity.objects.all().delete()
        print(f"Deleted {count} existing opportunities")
    else:
        print("No existing opportunities to delete")

def migrate_opportunities():
    """Migrate opportunities from CRM database"""
    print("Starting opportunity migration from CRM...")
    
    # Truncate existing opportunities first
    truncate_opportunities()
    
    # Get default data
    default_org, default_currency, default_user, default_bp = get_or_create_default_data()
    
    # Connect to CRM database
    crm_conn = get_connection()
    cursor = crm_conn.cursor()
    
    # Updated query to match your requirements
    query = """
        SELECT
            id,
            oc.opp_code_c,
            name,
            date_entered,
            date_modified,
            modified_user_id,
            created_by,
            description,
            deleted,
            assigned_user_id,
            opportunity_type,
            campaign_id,
            lead_source,
            amount,
            amount_usdollar,
            currency_id,
            date_closed,
            next_step,
            sales_stage,
            probability
        FROM
            crm.opportunities
            LEFT JOIN opportunities_cstm oc ON oc.id_c = opportunities.id
        WHERE
            sales_stage LIKE '%Proces%'
            AND deleted = 0
        ORDER BY
            id
    """
    
    cursor.execute(query)
    opportunities = cursor.fetchall()
    
    print(f"Found {len(opportunities)} opportunities with 'Proces' in sales_stage")
    
    migrated_count = 0
    error_count = 0
    
    for opp_data in opportunities:
        try:
            with transaction.atomic():
                (crm_id, opp_code_c, name, date_entered, date_modified, modified_user_id, 
                 created_by, description, deleted, assigned_user_id, opportunity_type,
                 campaign_id, lead_source, amount, amount_usdollar, currency_id,
                 date_closed, next_step, sales_stage, probability) = opp_data
                
                # Check if already migrated
                existing = Opportunity.objects.filter(legacy_id=str(crm_id)).first()
                if existing:
                    print(f"Opportunity {crm_id} already exists, skipping...")
                    continue
                
                # Extract opportunity number from opp_code_c
                opportunity_number = extract_opportunity_number(opp_code_c)
                
                # Map sales stage
                django_stage = map_sales_stage_to_opportunity_stage(sales_stage)
                
                # Format opportunity number in Q #XXXXXX format
                formatted_opp_number = None
                if opportunity_number:
                    formatted_opp_number = f"Q #{opportunity_number}"
                
                # Create simplified opportunity (no business partner or other removed fields)
                description_with_notes = description or ''
                if description_with_notes:
                    description_with_notes += '\n\n'
                description_with_notes += f"Migrated from CRM. Original stage: {sales_stage}. Next step: {next_step or 'N/A'}. Opportunity code: {opp_code_c or 'N/A'}"
                if amount_usdollar:
                    description_with_notes += f"\nOriginal estimated value: ${amount_usdollar}"
                if lead_source:
                    description_with_notes += f"\nSource: {lead_source}"
                if probability:
                    description_with_notes += f"\nProbability: {probability}%"
                
                # Determine if opportunity is active based on stage
                is_active = django_stage not in ['closed_won', 'closed_lost', 'closed'] if django_stage else True
                
                opportunity = Opportunity.objects.create(
                    opportunity_number=formatted_opp_number,  # Use extracted number from CRM
                    name=name or f"CRM Opportunity {crm_id}",
                    description=description_with_notes,
                    is_active=is_active,  # Active unless closed
                    legacy_id=str(crm_id),
                    created_by=default_user,
                    updated_by=default_user
                )
                
                migrated_count += 1
                opp_number_display = f" (#{opportunity_number})" if opportunity_number else ""
                print(f"Migrated opportunity {crm_id}{opp_number_display}: {opportunity.opportunity_number} - {name}")
                
        except Exception as e:
            error_count += 1
            print(f"ERROR migrating opportunity {crm_id}: {str(e)}")
            continue
    
    cursor.close()
    crm_conn.close()
    
    print(f"\nMigration completed!")
    print(f"Successfully migrated: {migrated_count} opportunities")
    print(f"Errors: {error_count}")
    
    return migrated_count, error_count

if __name__ == "__main__":
    try:
        migrated, errors = migrate_opportunities()
        if errors > 0:
            sys.exit(1)
    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        sys.exit(1) 