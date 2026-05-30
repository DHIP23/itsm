# ── dashboard/urls.py ────────────────────────────────────────────
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('',       views.dashboard,          name='index'),
    path('data/',  views.dashboard_data_api, name='api_data'),
]
