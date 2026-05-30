from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display    = ['timestamp', 'user', 'action', 'object_repr', 'ip_address']
    list_filter     = ['action']
    search_fields   = ['user__username', 'object_repr', 'object_id']
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    date_hierarchy  = 'timestamp'
    ordering        = ['-timestamp']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
