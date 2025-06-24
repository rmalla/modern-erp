"""
URL patterns for core workflow dashboard and management views.
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Workflow Dashboard
    path('workflow/dashboard/', views.workflow_dashboard, name='workflow_dashboard'),
    path('workflow/history/', views.workflow_history, name='workflow_history'),
    path('workflow/approval/<uuid:approval_id>/', views.approval_detail, name='approval_detail'),
    
    # API endpoints
    path('api/workflow/stats/', views.workflow_stats_api, name='workflow_stats_api'),
]