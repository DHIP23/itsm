# ── tickets/urls.py ──────────────────────────────────────────────
from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('',                         views.ticket_list,          name='list'),
    path('create/',                  views.ticket_create,        name='create'),
    path('<int:pk>/',                views.ticket_detail,        name='detail'),
    path('<int:pk>/status/',         views.ticket_update_status, name='update_status'),
    path('<int:pk>/assign/',         views.ticket_assign,        name='assign'),
    path('<int:pk>/comment/',        views.add_comment,          name='add_comment'),
]
