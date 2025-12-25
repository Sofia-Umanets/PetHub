from datetime import date
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
        from .views import EventService
        
        # Сохраняем исходную дату для проверки
        original_date = self.date
        
        # Обрабатываем корректировку для ежегодных событий
        if self.is_yearly:
            event_date = self.date
            if hasattr(event_date, 'date'):
                event_date = event_date.date()
            
            current_date = timezone.now().date()
            
            # Если дата в прошлом, корректируем ее на текущий/следующий год
            if event_date < current_date:
                # Определяем год для новой даты
                target_year = current_date.year
                
                # Если месяц и день - 29 февраля
                if event_date.month == 2 and event_date.day == 29:
                    # Проверяем, является ли текущий год високосным
                    try:
                        # Пробуем создать 29 февраля в текущем году
                        new_date = date(target_year, 2, 29)
                        # Если создалось успешно, год високосный
                        self.date = new_date
                    except ValueError:
                        # Если не високосный, используем 28 февраля
                        self.date = date(target_year, 2, 28)
                else:
                    # Для обычных дат используем безопасный метод
                    new_date = EventService.get_safe_date(
                        target_year, event_date.month, event_date.day
                    )
                    self.date = new_date
                
                self.is_event_passed = True
        
        # Для НЕ ежегодных событий также проверяем 29 февраля
        elif not self.is_yearly and self.date.month == 2 and self.date.day == 29:
            try:
                # Проверяем, валидна ли дата (високосный год)
                test_date = date(self.date.year, 2, 29)
                # Если не было исключения, дата валидна
            except ValueError:
                # Если год не високосный, корректируем на 28 февраля
                self.date = date(self.date.year, 2, 28)
        
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