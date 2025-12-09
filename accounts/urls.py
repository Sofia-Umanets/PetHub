from django.urls import path
from .views import SignupPageView, profile, invite_owner, accept_invite, mark_notification_read, edit_profile
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('signup/', SignupPageView.as_view(), name='signup'),
    path('profile/', profile, name='profile'),
    path('profile/edit/', edit_profile, name='edit_profile'),
    path('invite/<uuid:pet_id>/', invite_owner, name='invite_owner'),
    path('accept/<uuid:token>/', accept_invite, name='accept_invite'),
    path('notifications/read/<int:notification_id>/', mark_notification_read, name='mark_notification_read'),

]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)