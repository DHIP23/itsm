from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('tickets/', include('tickets.urls', namespace='tickets')),
    path('sla/', include('sla.urls', namespace='sla')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('audit/', include('audit.urls', namespace='audit')),
    path('', lambda request: redirect('dashboard:index'), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATIC_ROOT
    )
admin.site.site_header = 'DSI ITSM — Administration'
admin.site.site_title  = 'DSI ITSM'
admin.site.index_title = 'Gestion du portail ITSM'
