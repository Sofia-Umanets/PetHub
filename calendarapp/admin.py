from django.contrib import admin
from .models import Event, ReminderSettings

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'pet', 'event_type', 'date', 'is_done')
    list_filter = ('event_type', 'is_done', 'date')
    search_fields = ('title', 'note')


@admin.register(ReminderSettings)
class ReminderSettingsAdmin(admin.ModelAdmin):
    list_display = ('event', 'remind_at', 'repeat', 'remind_date', 'last_reminded')

