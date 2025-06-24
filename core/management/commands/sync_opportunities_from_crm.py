"""
Django management command for syncing opportunities from remote CRM system.

Usage:
    python manage.py sync_opportunities_from_crm
    python manage.py sync_opportunities_from_crm --dry-run
    python manage.py sync_opportunities_from_crm --limit 100
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import datetime
import pymysql
from core.models import Opportunity, BusinessPartner, User

User = get_user_model()


class Command(BaseCommand):
    help = 'Sync opportunities from remote CRM MySQL database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without making changes',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of opportunities to process',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reimport of existing opportunities',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting CRM opportunity sync...'))
        
        # Configuration
        dry_run = options['dry_run']
        limit = options['limit']
        force = options['force']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        try:
            # Connect to remote CRM database
            crm_conn = pymysql.connect(
                host='malla-group.com',
                port=3306,
                user='mariadb_reader',
                password='8c20c653fd7646279b9a41c6c58b8e32',
                database='crm_malla_group_com',
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = crm_conn.cursor()
            
            # Query for opportunities
            query = """
                SELECT 
                    id as crm_id,
                    opportunity_number,
                    name,
                    description,
                    sales_stage,
                    probability,
                    amount_usdollar,
                    lead_source,
                    next_step,
                    opp_code_c,
                    date_entered,
                    date_closed,
                    date_modified
                FROM opportunities 
                WHERE deleted = 0
                ORDER BY date_modified DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            opportunities = cursor.fetchall()
            
            self.stdout.write(f'Found {len(opportunities)} opportunities in CRM')
            
            # Get default user for created_by/updated_by
            try:
                default_user = User.objects.get(username='admin')
            except User.DoesNotExist:
                default_user = User.objects.filter(is_superuser=True).first()
                if not default_user:
                    raise CommandError('No admin user found. Please create a superuser first.')
            
            # Process opportunities
            migrated_count = 0
            updated_count = 0
            skipped_count = 0
            error_count = 0
            
            for opp_data in opportunities:
                try:
                    crm_id = opp_data['crm_id']
                    opportunity_number = opp_data['opportunity_number']
                    name = opp_data['name']
                    description = opp_data['description']
                    sales_stage = opp_data['sales_stage']
                    probability = opp_data['probability']
                    amount_usdollar = opp_data['amount_usdollar']
                    lead_source = opp_data['lead_source']
                    next_step = opp_data['next_step']
                    opp_code_c = opp_data['opp_code_c']
                    date_entered = opp_data['date_entered']
                    date_closed = opp_data['date_closed']
                    
                    # Format opportunity number in Q #XXXXXX format
                    formatted_opp_number = None
                    if opportunity_number:
                        formatted_opp_number = f"Q #{opportunity_number}"
                    
                    # Create detailed description with all CRM data
                    detailed_description = description or ''
                    if detailed_description:
                        detailed_description += '\n\n'
                    detailed_description += f"Migrated from CRM. Original stage: {sales_stage}. Next step: {next_step or 'N/A'}. Opportunity code: {opp_code_c or 'N/A'}"
                    if amount_usdollar:
                        detailed_description += f"\nOriginal estimated value: ${amount_usdollar}"
                    if lead_source:
                        detailed_description += f"\nSource: {lead_source}"
                    if probability:
                        detailed_description += f"\nProbability: {probability}%"
                    
                    # Determine if opportunity is active based on stage
                    is_active = sales_stage not in ['closed_won', 'closed_lost', 'closed'] if sales_stage else True
                    
                    # Check if opportunity already exists
                    existing_opp = None
                    if formatted_opp_number:
                        existing_opp = Opportunity.objects.filter(
                            opportunity_number=formatted_opp_number
                        ).first()
                    
                    if not existing_opp:
                        existing_opp = Opportunity.objects.filter(
                            legacy_id=str(crm_id)
                        ).first()
                    
                    if existing_opp:
                        if force:
                            if not dry_run:
                                # Update existing opportunity
                                existing_opp.name = name or f"CRM Opportunity {crm_id}"
                                existing_opp.description = detailed_description
                                existing_opp.is_active = is_active
                                existing_opp.updated_by = default_user
                                existing_opp.save()
                            updated_count += 1
                            self.stdout.write(f'Updated: {existing_opp.opportunity_number} - {name}')
                        else:
                            skipped_count += 1
                            continue
                    else:
                        if not dry_run:
                            # Create new opportunity
                            opportunity = Opportunity.objects.create(
                                opportunity_number=formatted_opp_number,
                                name=name or f"CRM Opportunity {crm_id}",
                                description=detailed_description,
                                is_active=is_active,
                                legacy_id=str(crm_id),
                                created_by=default_user,
                                updated_by=default_user
                            )
                        migrated_count += 1
                        opp_number_display = f" (#{opportunity_number})" if opportunity_number else ""
                        self.stdout.write(f'Migrated: Q #{opportunity_number if opportunity_number else "NEW"} - {name}')
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'ERROR processing opportunity {crm_id}: {str(e)}')
                    )
                    continue
            
            cursor.close()
            crm_conn.close()
            
            # Summary
            self.stdout.write(self.style.SUCCESS('\n=== SYNC SUMMARY ==='))
            self.stdout.write(f'New opportunities: {migrated_count}')
            self.stdout.write(f'Updated opportunities: {updated_count}')
            self.stdout.write(f'Skipped opportunities: {skipped_count}')
            self.stdout.write(f'Errors: {error_count}')
            
            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN - No actual changes were made'))
            else:
                self.stdout.write(self.style.SUCCESS('Sync completed successfully!'))
                
        except Exception as e:
            raise CommandError(f'Failed to sync opportunities: {str(e)}')

    def safe_date_conversion(self, date_value):
        """Safely convert various date formats to date object."""
        if not date_value:
            return None
        
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, '%Y-%m-%d').date()
            except ValueError:
                try:
                    return datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S').date()
                except ValueError:
                    return None
        
        if hasattr(date_value, 'date'):
            return date_value.date()
        
        return date_value