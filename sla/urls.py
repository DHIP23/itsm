from django.urls import path
from . import views

app_name = 'sla'

urlpatterns = [
    path('', views.sla_dashboard, name='dashboard'),
]
