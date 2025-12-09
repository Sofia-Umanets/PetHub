from django.urls import path
from .views import pet_delete, pets_list, pet_add, pet_detail, pet_edit, remove_owner

app_name = 'pets'

urlpatterns = [
    path('', pets_list, name='list'),
    path('add/', pet_add, name='add'),
    path('<uuid:pet_id>/', pet_detail, name='detail'),
    path('<uuid:pet_id>/edit/', pet_edit, name='edit'),
    path('<uuid:pet_id>/delete/', pet_delete, name='delete'),
    path('<uuid:pet_id>/remove-owner/<uuid:owner_id>/', remove_owner, name='remove_owner'),
]
