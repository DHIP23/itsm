from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informations DSI', {'fields': ('role', 'department', 'phone', 'avatar')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Informations DSI', {'fields': ('role', 'department', 'phone')}),
    )
    list_display  = ['username', 'email', 'get_full_name', 'role', 'department', 'is_active']
    list_filter   = ['role', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'department']
    ordering      = ['last_name', 'first_name']
