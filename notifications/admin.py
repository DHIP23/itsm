from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ['recipient', 'type', 'ticket', 'is_read', 'created_at']
    list_filter   = ['type', 'is_read']
    search_fields = ['recipient__username', 'message']
    date_hierarchy = 'created_at'
    readonly_fields = ['recipient', 'ticket', 'type', 'message', 'created_at']
