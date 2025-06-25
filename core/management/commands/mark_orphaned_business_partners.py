"""
Django Management Command: Mark Orphaned Business Partners

This command identifies business partners that have no locations and no related documents,
then marks them with is_orphan=True for easy filtering and review in the admin interface.

Usage:
    python manage.py mark_orphaned_business_partners           # Dry run (show what would be marked)
    python manage.py mark_orphaned_business_partners --mark    # Actually mark the orphaned BPs
    python manage.py mark_orphaned_business_partners --unmark  # Remove all orphan flags (reset)

Safety Features:
    - Dry run mode by default
    - Requires explicit --mark flag for actual changes
    - Database transactions for safety
    - Detailed reporting of changes
    - Reversible with --unmark option
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q
from core.models import BusinessPartner
from sales.models import SalesOrder, Invoice
from purchasing.models import PurchaseOrder, VendorBill


class Command(BaseCommand):
    help = 'Mark business partners with no locations or related documents as orphaned for cleanup review'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mark',
            action='store_true',
            help='Actually mark orphaned business partners (default is dry run)',
        )
        parser.add_argument(
            '--unmark',
            action='store_true',
            help='Remove all orphan flags (reset all to False)',
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress detailed output, show only summary',
        )

    def handle(self, *args, **options):
        """Main command handler"""
        
        if options['unmark']:
            self.unmark_all_orphans(options['quiet'])
            return

        # Main orphan marking logic
        self.mark_orphaned_business_partners(
            dry_run=not options['mark'],
            quiet=options['quiet']
        )

    def identify_orphaned_business_partners(self):
        """Identify business partners with no locations and no related documents"""
        
        orphaned_bp = BusinessPartner.objects.annotate(
            location_count=Count('locations')
        ).filter(
            location_count=0
        ).exclude(
            Q(salesorder__isnull=False) |
            Q(invoice__isnull=False) |
            Q(purchaseorder__isnull=False) |
            Q(vendorbill__isnull=False)
        )
        
        return orphaned_bp

    def analyze_orphaned_patterns(self, orphaned_bp):
        """Analyze patterns in orphaned business partners"""
        
        # Analyze by legacy ID pattern
        uuid_legacy = orphaned_bp.filter(
            legacy_id__regex=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        )
        numeric_legacy = orphaned_bp.filter(legacy_id__regex=r'^[0-9]+$')
        
        # Analyze by product-like names
        product_like = orphaned_bp.filter(name__regex=r'^[A-Z]+\s*-\s*[A-Z0-9/]+')
        
        # Find exact duplicates within orphaned
        duplicates = orphaned_bp.values('name').annotate(count=Count('name')).filter(count__gt=1)
        duplicate_count = sum(dup['count'] - 1 for dup in duplicates)  # Total extra copies
        
        return {
            'total': orphaned_bp.count(),
            'uuid_legacy': uuid_legacy.count(),
            'numeric_legacy': numeric_legacy.count(),
            'product_like': product_like.count(),
            'duplicate_count': duplicate_count
        }

    def mark_orphaned_business_partners(self, dry_run=True, quiet=False):
        """
        Mark orphaned business partners with is_orphan=True
        
        Args:
            dry_run (bool): If True, only show what would be marked without actually marking
            quiet (bool): If True, suppress detailed output
        """
        
        if not quiet:
            self.stdout.write(
                self.style.HTTP_INFO('=== MARK ORPHANED BUSINESS PARTNERS ===')
            )
            mode_text = 'DRY RUN' if dry_run else 'LIVE MARKING'
            self.stdout.write(f"Mode: {self.style.WARNING(mode_text)}")
            self.stdout.write('')
        
        # Identify orphaned business partners
        orphaned_bp = self.identify_orphaned_business_partners()
        
        if orphaned_bp.count() == 0:
            self.stdout.write(
                self.style.SUCCESS("No orphaned business partners found.")
            )
            return
        
        # Analyze patterns
        patterns = self.analyze_orphaned_patterns(orphaned_bp)
        
        if not quiet:
            self.stdout.write("Analysis Results:")
            self.stdout.write(f"  - Total orphaned: {patterns['total']}")
            self.stdout.write(f"  - UUID legacy IDs (likely from CRM): {patterns['uuid_legacy']}")
            self.stdout.write(f"  - Numeric legacy IDs (likely from iDempiere): {patterns['numeric_legacy']}")
            self.stdout.write(f"  - Product-like names: {patterns['product_like']}")
            self.stdout.write(f"  - Exact duplicates (extra copies): {patterns['duplicate_count']}")
            self.stdout.write('')
        
        # Check how many are already marked
        already_marked = orphaned_bp.filter(is_orphan=True).count()
        to_mark = orphaned_bp.filter(is_orphan=False).count()
        
        if not quiet:
            self.stdout.write("Current Status:")
            self.stdout.write(f"  - Already marked as orphan: {already_marked}")
            self.stdout.write(f"  - Will be marked as orphan: {to_mark}")
            self.stdout.write('')
            
            # Show sample of what will be marked
            if to_mark > 0:
                self.stdout.write("Sample of business partners to mark as orphaned:")
                sample_bp = orphaned_bp.filter(is_orphan=False)[:10]
                for bp in sample_bp:
                    legacy_type = "UUID" if bp.legacy_id and len(bp.legacy_id) > 10 and '-' in bp.legacy_id else "Numeric"
                    self.stdout.write(f"  {bp.name} | Legacy: {bp.legacy_id} ({legacy_type})")
                
                if to_mark > 10:
                    self.stdout.write(f"  ... and {to_mark - 10} more")
                self.stdout.write('')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN: No actual marking performed.")
            )
            self.stdout.write(f"Would mark {to_mark} business partners as orphaned.")
            self.stdout.write('')
            self.stdout.write("To perform actual marking, run:")
            self.stdout.write(
                self.style.SUCCESS("python manage.py mark_orphaned_business_partners --mark")
            )
        else:
            # Perform actual marking
            if not quiet:
                self.stdout.write(
                    self.style.HTTP_REDIRECT("PERFORMING ACTUAL MARKING...")
                )
            
            with transaction.atomic():
                marked_count = 0
                for bp in orphaned_bp.filter(is_orphan=False):
                    if not quiet and marked_count < 10:  # Show first 10 for feedback
                        self.stdout.write(f"Marking as orphan: {bp.name}")
                    bp.is_orphan = True
                    bp.save()
                    marked_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully marked {marked_count} business partners as orphaned.")
                )
        
        if not quiet:
            self.stdout.write('')
            self.stdout.write(self.style.HTTP_INFO('=== NEXT STEPS ==='))
            self.stdout.write("1. Go to Django Admin: Business Partners")
            self.stdout.write("2. Use the 'Is orphan' filter to view orphaned records")
            self.stdout.write("3. Review the list and delete unwanted records")
            self.stdout.write("4. Use the filter to quickly identify and manage orphaned data")

    def unmark_all_orphans(self, quiet=False):
        """Remove orphan flags from all business partners"""
        
        if not quiet:
            self.stdout.write(
                self.style.HTTP_INFO('=== REMOVE ALL ORPHAN FLAGS ===')
            )
        
        orphaned_count = BusinessPartner.objects.filter(is_orphan=True).count()
        
        if orphaned_count == 0:
            self.stdout.write(
                self.style.SUCCESS("No business partners are currently marked as orphaned.")
            )
            return
        
        if not quiet:
            self.stdout.write(f"Found {orphaned_count} business partners currently marked as orphaned.")
            self.stdout.write("This will reset ALL orphan flags to False.")
        
        with transaction.atomic():
            updated = BusinessPartner.objects.filter(is_orphan=True).update(is_orphan=False)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully reset orphan flags for {updated} business partners.")
            )