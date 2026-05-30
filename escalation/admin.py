from django.contrib import admin
from .models import EscalationRule, EscalationEvent


@admin.register(EscalationRule)
class EscalationRuleAdmin(admin.ModelAdmin):
    list_display  = ['name', 'trigger', 'priority', 'target', 'notify_via', 'is_active']
    list_filter   = ['trigger', 'is_active', 'notify_via']
    search_fields = ['name']
    list_editable = ['is_active']


@admin.register(EscalationEvent)
class EscalationEventAdmin(admin.ModelAdmin):
    list_display    = ['ticket', 'trigger', 'notified', 'sent_at', 'email_sent']
    list_filter     = ['trigger', 'email_sent']
    readonly_fields = ['ticket', 'rule', 'trigger', 'notified', 'message', 'sent_at', 'email_sent']
    date_hierarchy  = 'sent_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
