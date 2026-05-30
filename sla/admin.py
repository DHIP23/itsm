from django.contrib import admin
from .models import SLAPolicy, SLATracker


@admin.register(SLAPolicy)
class SLAPolicyAdmin(admin.ModelAdmin):
    list_display  = ['priority', 'response_time', 'resolution_time',
                     'business_hours', 'is_active']
    list_editable = ['response_time', 'resolution_time', 'business_hours', 'is_active']
    ordering      = ['priority']


@admin.register(SLATracker)
class SLATrackerAdmin(admin.ModelAdmin):
    list_display    = ['ticket', 'policy', 'response_due', 'resolution_due',
                       'response_breached', 'resolution_breached', 'total_paused_minutes']
    list_filter     = ['response_breached', 'resolution_breached']
    readonly_fields = ['ticket', 'created_at', 'updated_at']
    search_fields   = ['ticket__reference']
