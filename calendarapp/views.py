from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages
from .models import Event, ReminderSettings, EVENT_TYPES
from pets.models import Pet
from datetime import date, datetime, time
from typing import Union
from django.utils import timezone
import logging


logger = logging.getLogger(__name__)

WEEKDAY_CHOICES = [
    ("0", "Пн"),
    ("1", "Вт"),
    ("2", "Ср"),
    ("3", "Чт"),
    ("4", "Пт"),
    ("5", "Сб"),
    ("6", "Вс"),
]

@login_required
def add_event(request, pet_id):
    pet = get_object_or_404(Pet, id=pet_id)

    if request.user not in pet.owners.all():
        messages.error(request, "У вас нет прав для добавления событий для этого питомца.")
        return redirect('pets:list')

    error = None
    initial = {} 
    warning_message = None 

    if request.method == 'POST':
        for field in ['title', 'event_type', 'date', 'time', 'duration', 'note',
                      'remind_at', 'repeat', 'repeat_days', 'repeat_every', 'remind_date']:
            initial[field] = request.POST.get(field, '')
        is_yearly = request.POST.get('is_yearly') == 'on'
        initial['is_yearly'] = is_yearly
        initial['repeat'] = request.POST.get('repeat') == 'on'
        initial['repeat_days'] = request.POST.getlist('repeat_days')

        title = request.POST.get('title', '').strip()
        event_type = request.POST.get('event_type')
        date_str = request.POST.get('date')
        time_str = request.POST.get('time') or None
        duration = request.POST.get('duration') or None
        note = request.POST.get('note', '')

        try:
            event_date = None
            if date_str:
                event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                error = "Дата события обязательна."

            event_time = datetime.strptime(time_str, '%H:%M').time() if time_str else None

            if not error: 
                current_year = timezone.now().year
                input_year = event_date.year

                if is_yearly:
                    if input_year >= current_year - 1:
                        start_year = input_year
                    else:
                        start_year = current_year - 1
                        warning_message = f"Событие создано как ежегодная серия, начинающаяся с {start_year} года, так как оригинальная дата слишком далеко в прошлом."
                        logger.warning(f"User attempted to create yearly event with date {event_date} for pet {pet_id}. Series started at {start_year}.")

                    if start_year != input_year and event_date.month == 2 and event_date.day == 29:
                        try:
                            date(start_year, 2, 29) 
                        except ValueError:
                            start_date = date(start_year, 2, 28)
                            logger.warning(f"Adjusting 29 Feb start date to 28 Feb for start_year {start_year} for event '{title}' pet {pet_id}.")
                        else:
                            start_date = date(start_year, event_date.month, event_date.day)
                    else:
                        start_date = date(start_year, event_date.month, event_date.day)

                    if Event.objects.filter(pet=pet, title=title, date=start_date).exists():
                        error = f"Событие с таким названием и датой ({start_date.strftime('%Y-%m-%d')}) уже существует. Не удалось создать ежегодную серию."
                    else:
                        years_to_create = [start_year, start_year + 1, start_year + 2] 

                        events_to_bulk_create = []
                        original_event_instance = None

                        with transaction.atomic(): 
                            for year in years_to_create:
                                try:
                                    series_date = date(year, event_date.month, event_date.day)
                                except ValueError:
                                    if event_date.month == 2 and event_date.day == 29:
                                        logger.info(f"Skipping 29 Feb for year {year} for event '{title}' (Pet: {pet.name}) as {year} is not a leap year.")
                                        continue
                                    else:
                                        raise 

                                if Event.objects.filter(pet=pet, title=title, date=series_date).exists():
                                    logger.warning(f"Skipping creation of duplicate event for '{title}' on {series_date} for pet {pet.name} during series creation.")
                                    continue 

                                if original_event_instance is None:
                                    original_event_instance = Event.objects.create( 
                                        pet=pet,
                                        title=title,
                                        event_type=event_type,
                                        date=series_date, 
                                        time=event_time,
                                        duration_minutes=duration if duration else None,
                                        note=note,
                                        is_yearly=True,
                                        is_done=False,
                                        original_event=None 
                                    )
                                else:
                                    events_to_bulk_create.append(Event(
                                        pet=pet,
                                        title=title,
                                        event_type=event_type,
                                        date=series_date,
                                        time=event_time,
                                        duration_minutes=duration if duration else None,
                                        note=note,
                                        is_yearly=True,
                                        is_done=False,
                                        original_event=original_event_instance 
                                    ))

                            if events_to_bulk_create:
                                Event.objects.bulk_create(events_to_bulk_create)

                        all_series_events = [original_event_instance] + events_to_bulk_create 

                        remind_at_str = request.POST.get('remind_at') or None
                        repeat = request.POST.get('repeat') == 'on'

                        if remind_at_str:
                            try:
                                remind_at_time = datetime.strptime(remind_at_str, '%H:%M').time()
                            except ValueError:
                                remind_at_time = None 
                                messages.error(request, "Некорректный формат времени для напоминания.") 

                            if remind_at_time: 
                                repeat_days = []
                                repeat_every = 1
                                remind_date_val = None

                                if repeat:
                                    repeat_days = request.POST.getlist('repeat_days')
                                    try:
                                        repeat_every = int(request.POST.get('repeat_every') or 1)
                                        if repeat_every <= 0: raise ValueError 
                                    except ValueError:
                                        repeat_every = 1
                                        messages.error(request, "Некорректное значение 'Повторять каждые'. Установлено значение по умолчанию 1.")
                                else:
                                    remind_date_str_val = request.POST.get('remind_date') or None
                                    if remind_date_str_val:
                                        try:
                                            remind_date_val = datetime.strptime(remind_date_str_val, '%Y-%m-%d').date()
                                        except ValueError:
                                            remind_date_val = None
                                            messages.error(request, "Некорректный формат даты для напоминания.")

                                for event_instance in all_series_events: 
                                    rs, created = ReminderSettings.objects.get_or_create(event=event_instance, defaults={'pet': pet})
                                    rs.remind_at = remind_at_time
                                    rs.repeat = repeat
                                    rs.repeat_days = repeat_days
                                    rs.repeat_every = repeat_every
                                    rs.remind_date = remind_date_val if not repeat else None 
                                    rs.save()
                                    if created:
                                        logger.info(f"Created reminder settings for event {event_instance.id}.")
                                    else:
                                        logger.info(f"Updated reminder settings for event {event_instance.id}.")

                        messages.success(request, f"Ежегодная серия событий '{title}' успешно добавлена.")
                        if warning_message: 
                            messages.warning(request, warning_message)
                        redirect_date = original_event_instance.date.strftime('%Y-%m-%d') if original_event_instance else date_str
                        return redirect(f'/pets/{pet_id}/?tab=calendar#{redirect_date}')

                else: 
                    if Event.objects.filter(pet=pet, title=title, date=event_date).exists():
                        error = "Событие с таким названием и датой уже существует."
                    else:
                        single_event = Event(
                            pet=pet,
                            title=title,
                            event_type=event_type,
                            date=event_date,
                            time=event_time,
                            duration_minutes=duration if duration else None,
                            note=note,
                            is_yearly=False,
                            is_done=False,
                            original_event=None 
                        )
                        single_event.save()

                        remind_at_str = request.POST.get('remind_at') or None
                        repeat = request.POST.get('repeat') == 'on'

                        if remind_at_str:
                            try:
                                remind_at_time = datetime.strptime(remind_at_str, '%H:%M').time()
                            except ValueError:
                                remind_at_time = None
                                messages.error(request, "Некорректный формат времени для напоминания.")

                            if remind_at_time:
                                repeat_days = []
                                repeat_every = 1
                                remind_date_val = None

                                if repeat:
                                    repeat_days = request.POST.getlist('repeat_days')
                                    try:
                                        repeat_every = int(request.POST.get('repeat_every') or 1)
                                        if repeat_every <= 0: raise ValueError
                                    except ValueError:
                                        repeat_every = 1
                                        messages.error(request, "Некорректное значение 'Повторять каждые'. Установлено значение по умолчанию 1.")
                                else:
                                    remind_date_str_val = request.POST.get('remind_date') or None
                                    if remind_date_str_val:
                                        try:
                                            remind_date_val = datetime.strptime(remind_date_str_val, '%Y-%m-%d').date()
                                        except ValueError:
                                            remind_date_val = None
                                            messages.error(request, "Некорректный формат даты для напоминания.")

                                rs, created = ReminderSettings.objects.get_or_create(event=single_event, defaults={'pet': pet})
                                rs.remind_at = remind_at_time
                                rs.repeat = repeat
                                rs.repeat_days = repeat_days
                                rs.repeat_every = repeat_every
                                rs.remind_date = remind_date_val if not repeat else None
                                rs.save()
                                if created: logger.info(f"Created reminder settings for event {single_event.id}.")
                                else: logger.info(f"Updated reminder settings for event {single_event.id}.")

                        messages.success(request, f"Событие '{title}' успешно добавлено.")
                        return redirect(f'/pets/{pet_id}/?tab=calendar#{event_date.strftime("%Y-%m-%d")}')

        except ValueError as e:
            error = f"Ошибка в формате даты или времени: {e}"
            logger.error(f"ValueError adding event for pet {pet_id}: {e}")
        except Exception as e:
            error = "Произошла ошибка при добавлении события."
            logger.error(f"Error adding event for pet {pet_id}: {e}", exc_info=True)


    context = {
        'pet': pet,
        'error': error,
        'warning_message': warning_message,
        'initial': initial,
        'event_type_choices': EVENT_TYPES,
        'weekday_choices': WEEKDAY_CHOICES,
    }


    return render(request, 'calendarapp/add_event.html', context)

from datetime import date


def safe_time_parse(value: str) -> Union[time, None]:
    if not value:
        return None
    try:
        if len(value) < 5:
            return None
        return datetime.strptime(value, '%H:%M').time()
    except ValueError:
        return None

def safe_date_parse(value: str) -> Union[date, None]:
    if not value:
        return None
    try:
        if len(value) < 10:
            return None
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


@login_required
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if request.user not in event.pet.owners.all():
        return redirect('pets:list')

    error = None
    pet_id = event.pet.id
    
    try:
        reminder = event.reminder
        has_reminder = True
    except ReminderSettings.DoesNotExist:
        reminder = None
        has_reminder = False

    is_birthday = event.event_type == 'birthday'
    
    initial_date = event.date.strftime('%Y-%m-%d') if event.date else ''
    initial_time = event.time.strftime('%H:%M') if event.time else ''

    remind_at_str = ''
    remind_date_str = ''
    repeat_days_selected = []
    repeat_every = 1
    repeat = False
    
    if has_reminder and reminder:
        repeat_days = getattr(reminder, 'repeat_days', [])
        repeat_days_selected = [str(day) for day in repeat_days]
        repeat_every = getattr(reminder, 'repeat_every', 1)
        repeat = getattr(reminder, 'repeat', False)
        
        if getattr(reminder, 'remind_at', None):
            remind_at_str = reminder.remind_at.strftime('%H:%M')
        else:
            remind_at_str = ''
            
        if getattr(reminder, 'remind_date', None) and not repeat:
            remind_date_str = reminder.remind_date.strftime('%Y-%m-%d')
        else:
            remind_date_str = ''
    else:
        repeat_days_selected = []
        repeat_every = 1
        repeat = False
        remind_at_str = ''
        remind_date_str = ''

    if request.method == 'POST':
        if is_birthday:
            time = request.POST.get('time') or None
            duration = request.POST.get('duration') or None
            note = request.POST.get('note', '')
            apply_to_all = request.POST.get('apply_to_all') == 'on'
            reminder_repeat = request.POST.get('repeat') == 'on'
            repeat_days = request.POST.getlist('repeat_days')
            repeat_every = int(request.POST.get('repeat_every') or 1)
            remind_at = safe_time_parse(request.POST.get('remind_at'))
            remind_date = safe_date_parse(request.POST.get('remind_date'))

            if apply_to_all:
                with transaction.atomic():
                    birthday_events = Event.objects.select_for_update().filter(
                        pet=event.pet, event_type='birthday', is_yearly=True
                    )

                    for ev in birthday_events:
                        ev.time = time
                        ev.duration_minutes = duration
                        ev.note = note
                        ev.save()

                        rs, created = ReminderSettings.objects.get_or_create(event=ev, defaults={'pet': event.pet})
                        rs.repeat = reminder_repeat
                        rs.repeat_days = repeat_days
                        rs.repeat_every = repeat_every
                        rs.remind_at = remind_at
                        if remind_date:
                            rs.remind_date = date(ev.date.year, remind_date.month, remind_date.day) if not reminder_repeat else None
                        else:
                            rs.remind_date = None
                        rs.save()

                    messages.success(request, 'Все события дня рождения обновлены.')

            else:
                event.time = request.POST.get('time') or None
                event.duration_minutes = request.POST.get('duration') or None
                event.note = request.POST.get('note', '')
                event.save()

                rs, created = ReminderSettings.objects.get_or_create(event=event, defaults={'pet': event.pet})
                rs.repeat = request.POST.get('repeat') == 'on'
                rs.repeat_days = request.POST.getlist('repeat_days')
                rs.repeat_every = int(request.POST.get('repeat_every') or 1)
                rs.remind_at = safe_time_parse(request.POST.get('remind_at'))
                if remind_date:
                    rs.remind_date = date(event.date.year, remind_date.month, remind_date.day) if not rs.repeat else None
                else:
                    rs.remind_date = None
                rs.save()

                messages.success(request, 'День рождения обновлен')

            return redirect(f'/pets/{pet_id}/?tab=calendar#{event.date}')

        else:
            title = request.POST.get('title', '').strip()
            event_type = request.POST.get('event_type')
            date_str = request.POST.get('date')
            time = request.POST.get('time') or None
            duration = request.POST.get('duration') or None
            note = request.POST.get('note', '')
            is_yearly = request.POST.get('is_yearly') == 'on'
            apply_to_all = request.POST.get('apply_to_all') == 'on'
            reminder_repeat = request.POST.get('repeat') == 'on'
            repeat_days = request.POST.getlist('repeat_days')
            repeat_every = int(request.POST.get('repeat_every') or 1)
            remind_at = safe_time_parse(request.POST.get('remind_at'))
            remind_date = safe_date_parse(request.POST.get('remind_date'))

            try:
                # Парсинг даты из формы
                user_supplied_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else event.date
            except ValueError:
                error = "Неверный формат даты"
                messages.error(request, error)
                return redirect('pets:detail', pet_id=pet_id)

            if is_yearly and user_supplied_date.month == 2 and user_supplied_date.day == 29:
                error = "29 февраля не может быть установлено для ежегодного события"
                messages.warning(request, error)
                return redirect(f'/pets/{pet_id}/?tab=calendar#{event.date}')

            # Получаем события для обновления
            if apply_to_all:
                if event.original_event:
                    # Если это не оригинал серии, получаем оригинал и все связанные события
                    main_event = event.original_event
                    events_in_series = list(main_event.recurring_events.all()) + [main_event]
                else:
                    # Если это оригинал серии, получаем его и все связанные события
                    events_in_series = list(event.recurring_events.all()) + [event]
            else:
                # Если не применять ко всем, обновляем только текущее событие
                events_in_series = [event]

            events_to_update = []
            reminders_to_update = []
            used_pairs = set()
            events_to_update = []
            reminders_to_update = []

            with transaction.atomic():
                for ev in events_in_series:
                    new_date = date(ev.date.year, user_supplied_date.month, user_supplied_date.day)

                    # Проверка дублирования
                    if Event.objects.filter(
                        pet=event.pet,
                        title=title,
                        date=new_date
                    ).exclude(id=ev.id).exists():
                        messages.warning(request, f'Дубликат: "{title}" на {new_date}')
                        continue

                    if (title, new_date) in used_pairs:
                        messages.warning(request, f'Дубликат: "{title}" → {new_date}')
                        continue

                    used_pairs.add((title, new_date))

                    # Обновляем само событие
                    ev.title = title
                    ev.event_type = event_type
                    ev.date = new_date
                    ev.time = time
                    ev.duration_minutes = duration
                    ev.note = note
                    ev.is_yearly = is_yearly
                    events_to_update.append(ev)

                    # Обновляем напоминание
                    rs, created = ReminderSettings.objects.get_or_create(event=ev, defaults={'pet': event.pet})
                    rs.repeat = reminder_repeat
                    rs.repeat_days = repeat_days
                    rs.repeat_every = repeat_every
                    rs.remind_at = remind_at
                    if remind_date:
                        rs.remind_date = date(ev.date.year, remind_date.month, remind_date.day) if not reminder_repeat else None
                    else:
                        rs.remind_date = None
                    reminders_to_update.append(rs)
            
                # Выполняем массовое обновление
                if events_to_update:
                    Event.objects.bulk_update(
                        events_to_update,
                        fields=[
                            'title', 'event_type', 'date', 'time', 
                            'duration_minutes', 'note', 'is_yearly'
                        ]
                    )
                if reminders_to_update:
                    ReminderSettings.objects.bulk_update(
                        reminders_to_update,
                        fields=[
                            'repeat', 'repeat_days', 'repeat_every',
                            'remind_at', 'remind_date'
                        ]
                    )

                messages.success(
                    request,
                    "Серия событий обновлена." if apply_to_all else "Событие обновлено."
                )

            return redirect(f'/pets/{pet_id}/?tab=calendar#{event.date}')

    # Подготовка данных формы
    form_data = {
        'title': event.title or '',
        'event_type': event.event_type or '',
        'date': initial_date,
        'time': initial_time,
        'duration': str(event.duration_minutes) if event.duration_minutes else '',
        'note': event.note or '',
        'is_yearly': 'on' if event.is_yearly else '',
        'apply_to_all': 'on' if request.POST.get('apply_to_all') else '',
        'remind_at': remind_at_str,
        'remind_date': remind_date_str,
        'repeat': 'on' if repeat else '',
        'repeat_every': str(repeat_every),
    }

    return render(request, 'calendarapp/edit_event.html', {
        'event': event,
        'form_data': form_data,
        'repeat_days_selected': repeat_days_selected,
        'error': error,
        'is_birthday': is_birthday,
        'event_type_choices': EVENT_TYPES,
        'reminder': reminder,
    })
                            

def create_next_year_event():
    current_year = datetime.now().year
    next_year = current_year + 1

    # Находим события, которые имеют статус is_yearly=True
    last_events = Event.objects.filter(
        is_yearly=True
    )

    for last_event in last_events:
        # Проверяем, если год события равен прошлому году или ранее
        if last_event.date.year == current_year - 1:
            # Создаем копию события на следующие годы
            new_date = last_event.date.replace(year=next_year + 1)
            Event.objects.get_or_create(
                pet=last_event.pet,
                title=last_event.title,
                date=new_date,
                defaults={
                    'event_type': last_event.event_type,
                    'time': last_event.time,
                    'duration_minutes': last_event.duration_minutes,
                    'note': last_event.note,
                    'is_yearly': True,
                    'is_done': False
                }
            )


@login_required
def mark_done(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    current_year = timezone.now().year

    # Отмечаем текущее событие как выполненное
    event.is_done = True
    event.done_year = current_year
    event.save()

    return redirect(f'/pets/{event.pet.id}/?tab=calendar#{event.date}')


@login_required
def delete_event(request, event_id):
    try:
        event = get_object_or_404(Event, pk=event_id)

        if request.user not in event.pet.owners.all():
            logger.warning(f"User {request.user} is not authorized to delete event {event_id}.")
            messages.error(request, "У вас нет прав для удаления этого события.")
            return redirect('pets:list')

        pet_id = event.pet.id

        #проверка для запрета удаления первого события ежегодной серии
        if event.is_yearly and event.recurring_events.exists() and event.original_event is None:
             # Если это первое событие в ежегодной серии и у него есть последующие копии
            if request.method == 'POST':
                delete_all = request.POST.get('delete_all') == 'on'

                if delete_all:
                    # Разрешаем удаление всей серии
                    Event.objects.filter(pet=event.pet, title=event.title, is_yearly=True).delete()
                    logger.info(f"Deleted all events with title {event.title} for pet {event.pet.name}")
                    messages.success(request, f"Удалена вся серия событий '{event.title}'.")
                else:
                    # Запрещаем удаление только этого события
                    logger.warning(f"Attempted to delete the first yearly event {event_id} individually.")
                    messages.error(request, f"Нельзя удалить только первое событие в ежегодной серии '{event.title}'. Удалите всю серию при необходимости.")
                    # Остаемся на странице удаления, показывая сообщение
                    return render(request, 'calendarapp/delete_event.html', {'event': event})

            return render(request, 'calendarapp/delete_event.html', {'event': event})


        if request.method == 'POST':
            delete_all = request.POST.get('delete_all') == 'on'

            if delete_all and event.is_yearly:
                # Если запрошено удаление всей серии (актуально для событий, которые не являются первыми,но принадлежат серии)
                Event.objects.filter(pet=event.pet, title=event.title, is_yearly=True).delete()
                logger.info(f"Deleted all events with title {event.title} for pet {event.pet.name}")
                messages.success(request, f"Удалена вся серия событий '{event.title}'.")
            else:
                # Удаляем только текущее событие (если это не первое событие ежегодной серии,
                # которое мы запретили выше, или если это не ежегодное событие)
                event.delete()
                logger.info(f"Deleted event {event_id} for pet {event.pet.name}")
                messages.success(request, f"Событие '{event.title}' успешно удалено.")

            # После успешного удаления, перенаправляем
            return redirect(f'/pets/{pet_id}/?tab=calendar#{event.date}')

        # Для GET-запроса, если событие не является первым dalam серии, просто показываем страницу удаления
        return render(request, 'calendarapp/delete_event.html', {'event': event})

    except Event.DoesNotExist:
        logger.error(f"Event with id {event_id} does not exist.")
        messages.error(request, "Событие не найдено.")
        return redirect('pets:list')
    except Exception as e:
        logger.error(f"Error deleting event {event_id}: {e}")
        return redirect(f'/pets/{pet_id}/?tab=calendar')