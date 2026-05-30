from django.contrib import admin
from .models import Ticket, TicketComment, TicketAttachment, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'parent', 'is_active']
    list_filter   = ['is_active']
    search_fields = ['name']


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display    = ['reference', 'title', 'type', 'status', 'priority',
                       'requester', 'assignee', 'created_at']
    list_filter     = ['type', 'status', 'priority', 'source']
    search_fields   = ['reference', 'title', 'description']
    readonly_fields = ['reference', 'created_at', 'updated_at', 'resolved_at', 'closed_at']
    date_hierarchy  = 'created_at'
    ordering        = ['-created_at']
    raw_id_fields   = ['requester', 'assignee']

    fieldsets = (
        ('Identification', {
            'fields': ('reference', 'type', 'title', 'description', 'tags')
        }),
        ('Classification', {
            'fields': ('status', 'priority', 'category', 'source')
        }),
        ('Acteurs', {
            'fields': ('requester', 'assignee')
        }),
        ('Résolution', {
            'fields': ('resolution_note',)
        }),
        ('Horodatages', {
            'fields': ('created_at', 'updated_at', 'resolved_at', 'closed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display  = ['ticket', 'author', 'visibility', 'created_at']
    list_filter   = ['visibility']
    raw_id_fields = ['ticket', 'author']


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display  = ['filename', 'ticket', 'uploaded_by', 'created_at']
    raw_id_fields = ['ticket', 'uploaded_by']
