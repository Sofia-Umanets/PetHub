from django.urls import path
from . import views

app_name = 'calendarapp'

urlpatterns = [
    path('<uuid:pet_id>/add/', views.add_event, name='add'),
    path('done/<uuid:event_id>/', views.mark_done, name='done'),
    path('edit/<uuid:event_id>/', views.edit_event, name='edit'),
    path('delete/<uuid:event_id>/', views.delete_event, name='delete'),

]