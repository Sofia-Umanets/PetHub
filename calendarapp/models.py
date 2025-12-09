from django.utils import timezone
import uuid
from django.db import models
from pets.models import Pet

EVENT_TYPES = [
    ('walk', 'Прогулка'),
    ('vet', 'Ветеринар'),
    ('grooming', 'Груминг'),
    ('vaccine', 'Прививка'),
    ('pill', 'Приём таблетки'),
    ('birthday', 'День рождения'),
]

class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=200)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    is_done = models.BooleanField(default=False)
    done_year = models.IntegerField(null=True, blank=True)
    note = models.TextField(blank=True)
    is_yearly = models.BooleanField(default=False, verbose_name="Ежегодное событие")
    original_event = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_events'
    )
    is_event_passed = models.BooleanField(default=False, verbose_name="Событие прошло")

    def save(self, *args, **kwargs):
        if self.is_yearly:
            if self.date < timezone.now().date():
                self.date = timezone.now().replace(month=self.date.month, day=self.date.day)
                self.is_event_passed = True
        super().save(*args, **kwargs)


    class Meta:
        unique_together = ('pet', 'title', 'date')

    def __str__(self):
        return f"{self.title} ({self.event_type}) — {self.date}"


class ReminderSettings(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='reminder')
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, default=None)

    remind_at = models.TimeField(null=True, blank=True)
    repeat = models.BooleanField(default=False)
    repeat_days = models.JSONField(default=list, blank=True)
    repeat_every = models.PositiveIntegerField(default=1)
    remind_date = models.DateField(null=True, blank=True)
    last_reminded = models.DateField(null=True, blank=True)

    def get_repeat_days(self):
        return [int(x) for x in (self.repeat_days or [])]

    def __str__(self):
        return f"Напоминание для {self.event}"