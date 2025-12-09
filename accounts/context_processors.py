
from .models import UserNotification

def notification_count(request):
    if request.user.is_authenticated:
        count = UserNotification.objects.filter(user=request.user, is_read=False).count()
        return {'notification_count': count}
    return {}



def notification_context(request):
    if request.user.is_authenticated:
        notifs = UserNotification.objects.filter(user=request.user).order_by('-created_at')
        return {
            'notifications': notifs,
        }
    return {}