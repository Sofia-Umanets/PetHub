import logging
from datetime import date, datetime, timedelta

from celery import shared_task
from django.utils import timezone

from .models import ReminderSettings
from accounts.models import UserNotification

logger = logging.getLogger(__name__)

@shared_task
def send_reminders():
    now_dt = timezone.now()
    today = now_dt.date()
    now_time = now_dt.time()
    weekday = today.weekday()

    reminders = ReminderSettings.objects.select_related('event', 'pet').filter(
        event__is_done=False,
    )

    logger.info(f"[REMINDER] Найдено {len(reminders)} напоминаний")

    count = 0
    for r in reminders:
        logger.info(f"[REMINDER] Напоминание для события {r.event.title}")

        if not r.remind_at:
            logger.info(f"  Пропускаем напоминание для события {r.event.title} (нет времени напоминания)")
            continue

        event = r.event

        # Для ежегодных событий проверяем только месяц и день события
        if event.is_yearly:
            if event.date.month != today.month or event.date.day != today.day:
                logger.info(f"  Пропускаем напоминание для события {r.event.title} (не совпадает месяц/день)")
                continue
        # Для остальных напоминаний проверяем дату или день недели
        elif not r.repeat and (not r.remind_date or r.remind_date != today):
            logger.info(f"  Пропускаем напоминание для события {r.event.title} (не повторяется или не совпадает дата напоминания)")
            continue
        elif r.repeat and weekday not in r.get_repeat_days():
            logger.info(f"  Пропускаем напоминание для события {r.event.title} (не повторяется или не совпадает день недели)")
            continue

        # Проверка, находится ли текущее время в 3-минутном окне от запланированного времени напоминания
        target_dt = timezone.make_aware(datetime.combine(today, r.remind_at))

        if not (timedelta(minutes=-3) <= (now_dt - target_dt) <= timedelta(minutes=3)):
            logger.info(f"  Пропускаем напоминание для события {r.event.title} (вне 3-минутного окна)")
            continue

        # Проверка, чтобы не напоминать несколько раз в один день
        if r.last_reminded == today:
            logger.info(f"  Пропускаем напоминание для события {r.event.title} (уже напоминано сегодня)")
            continue

        # Создание уведомления
        for user in r.pet.owners.all():
            msg = f"{r.pet.name}: {event.title} — сегодня в {r.remind_at.strftime('%H:%M')}"
            UserNotification.objects.create(user=user, message=msg)
            logger.info(f"[NOTIFY] В БД для {user.username}: {msg}")

        # Обновляем поле last_reminded
        r.last_reminded = today
        r.save()
        count += 1

    logger.info(f"[REMINDER] Всего отправлено: {count}")

from django_redis import get_redis_connection

from django.db import connection
import logging

logger = logging.getLogger(__name__)

@shared_task(name='calendarapp.tasks.create_next_year_yearly_events')
def create_next_year_yearly_events():
    logger.info("Задача create_next_year_yearly_events запущена")

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT create_next_year_yearly_events();")
        logger.info("Функция create_next_year_yearly_events выполнена успешно")
    except Exception as e:
        logger.error(f"Ошибка в задаче create_next_year_yearly_events: {e}")