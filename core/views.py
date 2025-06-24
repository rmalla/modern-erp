"""
Core views for Modern ERP system.
Provides central workflow dashboard and approval history views.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType

from .models import (
    DocumentWorkflow, WorkflowApproval, WorkflowDefinition,
    WorkflowState, User
)


@staff_member_required
def workflow_dashboard(request):
    """
    Central workflow dashboard showing all approval activity
    across all document types with statistics and history.
    """
    
    # Get workflow statistics
    total_pending = WorkflowApproval.objects.filter(status='pending').count()
    total_approved_today = WorkflowApproval.objects.filter(
        status='approved',
        responded_at__date=timezone.now().date()
    ).count()
    total_rejected_today = WorkflowApproval.objects.filter(
        status='rejected', 
        responded_at__date=timezone.now().date()
    ).count()
    
    # Get pending approvals by document type
    pending_by_type = {}
    pending_approvals = WorkflowApproval.objects.filter(
        status='pending'
    ).select_related(
        'document_workflow__workflow_definition',
        'document_workflow__content_type',
        'requested_by'
    ).order_by('-requested_at')[:20]
    
    # Group pending approvals by document type
    for approval in pending_approvals:
        doc_type = approval.document_workflow.workflow_definition.document_type
        if doc_type not in pending_by_type:
            pending_by_type[doc_type] = []
        pending_by_type[doc_type].append(approval)
    
    # Get recent approval activity (last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    recent_activity = WorkflowApproval.objects.filter(
        requested_at__gte=week_ago
    ).select_related(
        'document_workflow__workflow_definition',
        'document_workflow__content_type',
        'requested_by',
        'approver'
    ).order_by('-requested_at')[:50]
    
    # Get workflow definitions for summary
    workflow_definitions = WorkflowDefinition.objects.all().annotate(
        pending_count=Count(
            'documentworkflow__approvals',
            filter=Q(documentworkflow__approvals__status='pending')
        ),
        total_documents=Count('documentworkflow', distinct=True)
    )
    
    # Get top approvers (last 30 days)
    month_ago = timezone.now() - timedelta(days=30)
    top_approvers = User.objects.filter(
        approvals_given__responded_at__gte=month_ago,
        approvals_given__status='approved'
    ).annotate(
        approval_count=Count('approvals_given')
    ).order_by('-approval_count')[:10]
    
    # Get user's pending approvals if they have approval permissions
    user_pending = []
    if request.user.is_superuser or request.user.workflow_permissions.filter(
        permission_code__in=['approve_sales_orders', 'approve_purchase_orders'],
        is_active=True
    ).exists():
        user_pending = WorkflowApproval.objects.filter(
            status='pending'
        ).select_related(
            'document_workflow__workflow_definition',
            'document_workflow__content_type',
            'requested_by'
        ).order_by('-requested_at')
    
    context = {
        'total_pending': total_pending,
        'total_approved_today': total_approved_today,
        'total_rejected_today': total_rejected_today,
        'pending_by_type': pending_by_type,
        'recent_activity': recent_activity,
        'workflow_definitions': workflow_definitions,
        'top_approvers': top_approvers,
        'user_pending': user_pending,
        'page_title': 'Workflow Dashboard',
        'show_stats': True,
    }
    
    return render(request, 'core/workflow_dashboard.html', context)


@staff_member_required 
def workflow_history(request):
    """
    Complete workflow history with filtering and search capabilities.
    """
    
    # Get filter parameters
    document_type = request.GET.get('document_type', '')
    status = request.GET.get('status', '')
    approver_id = request.GET.get('approver', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    # Build base queryset
    approvals = WorkflowApproval.objects.select_related(
        'document_workflow__workflow_definition',
        'document_workflow__content_type', 
        'requested_by',
        'approver'
    ).order_by('-requested_at')
    
    # Apply filters
    if document_type:
        approvals = approvals.filter(
            document_workflow__workflow_definition__document_type=document_type
        )
    
    if status:
        approvals = approvals.filter(status=status)
        
    if approver_id:
        approvals = approvals.filter(approver_id=approver_id)
        
    if date_from:
        approvals = approvals.filter(requested_at__date__gte=date_from)
        
    if date_to:
        approvals = approvals.filter(requested_at__date__lte=date_to)
        
    if search:
        approvals = approvals.filter(
            Q(requested_by__first_name__icontains=search) |
            Q(requested_by__last_name__icontains=search) |
            Q(approver__first_name__icontains=search) |
            Q(approver__last_name__icontains=search) |
            Q(comments__icontains=search)
        )
    
    # Get filter options
    document_types = WorkflowDefinition.objects.values_list(
        'document_type', 'name'
    ).distinct()
    
    approvers = User.objects.filter(
        approvals_given__isnull=False
    ).distinct().order_by('first_name', 'last_name')
    
    # Pagination (show 50 per page)
    from django.core.paginator import Paginator
    paginator = Paginator(approvals, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'document_types': document_types,
        'approvers': approvers,
        'current_filters': {
            'document_type': document_type,
            'status': status,
            'approver': approver_id,
            'date_from': date_from,
            'date_to': date_to,
            'search': search,
        },
        'status_choices': WorkflowApproval.APPROVAL_STATUS_CHOICES,
        'page_title': 'Workflow History',
    }
    
    return render(request, 'core/workflow_history.html', context)


@staff_member_required
def approval_detail(request, approval_id):
    """
    Detailed view of a specific approval with full context.
    """
    
    approval = get_object_or_404(
        WorkflowApproval.objects.select_related(
            'document_workflow__workflow_definition',
            'document_workflow__content_type',
            'requested_by',
            'approver'
        ),
        id=approval_id
    )
    
    # Get the actual document object
    document_object = approval.document_workflow.content_object
    
    # Get all approvals for this document
    all_approvals = WorkflowApproval.objects.filter(
        document_workflow=approval.document_workflow
    ).select_related('requested_by', 'approver').order_by('-requested_at')
    
    context = {
        'approval': approval,
        'document_object': document_object,
        'all_approvals': all_approvals,
        'page_title': f'Approval Details - {approval.document_workflow.content_object}',
    }
    
    return render(request, 'core/approval_detail.html', context)


@staff_member_required
def workflow_stats_api(request):
    """
    API endpoint for workflow statistics (for AJAX updates).
    """
    
    # Calculate statistics
    total_pending = WorkflowApproval.objects.filter(status='pending').count()
    
    pending_by_type = WorkflowApproval.objects.filter(
        status='pending'
    ).values(
        'document_workflow__workflow_definition__document_type',
        'document_workflow__workflow_definition__name'
    ).annotate(
        count=Count('id')
    )
    
    # Recent approval activity (last 24 hours)
    yesterday = timezone.now() - timedelta(hours=24)
    recent_approvals = WorkflowApproval.objects.filter(
        responded_at__gte=yesterday,
        status='approved'
    ).count()
    
    recent_rejections = WorkflowApproval.objects.filter(
        responded_at__gte=yesterday,
        status='rejected'
    ).count()
    
    # Average approval time (last 30 days)
    month_ago = timezone.now() - timedelta(days=30)
    avg_approval_time = WorkflowApproval.objects.filter(
        status='approved',
        responded_at__gte=month_ago,
        responded_at__isnull=False,
        requested_at__isnull=False
    ).extra(
        select={'approval_time': 'responded_at - requested_at'}
    ).aggregate(
        avg_time=Avg('approval_time')
    )['avg_time']
    
    # Convert timedelta to hours if available
    avg_hours = None
    if avg_approval_time:
        avg_hours = round(avg_approval_time.total_seconds() / 3600, 1)
    
    return JsonResponse({
        'total_pending': total_pending,
        'pending_by_type': list(pending_by_type),
        'recent_approvals': recent_approvals,
        'recent_rejections': recent_rejections,
        'avg_approval_hours': avg_hours,
        'last_updated': timezone.now().isoformat()
    })