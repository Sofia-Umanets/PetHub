from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from datetime import date, datetime, time
from typing import Optional, List, Tuple, NamedTuple, Union
from dataclasses import dataclass
import logging
from urllib.parse import quote


from .models import Event, ReminderSettings, EVENT_TYPES
from pets.models import Pet

logger = logging.getLogger(__name__)

WEEKDAY_CHOICES = [
    ("0", "Пн"), ("1", "Вт"), ("2", "Ср"), ("3", "Чт"),
    ("4", "Пт"), ("5", "Сб"), ("6", "Вс"),
]


@dataclass
class EventFormData:
    title: str = ''
    event_type: str = ''
    date: Optional[datetime.date] = None
    time: Optional[datetime.time] = None
    duration: Optional[int] = None
    note: str = ''
    is_yearly: bool = False
    
    @classmethod
    def from_post(cls, post_data) -> 'EventFormData':
        return cls(
            title=post_data.get('title', '').strip(),
            event_type=post_data.get('event_type', ''),
            date=parse_date(post_data.get('date')),
            time=parse_time(post_data.get('time')),
            duration=parse_int(post_data.get('duration')),
            note=post_data.get('note', ''),
            is_yearly=post_data.get('is_yearly') == 'on',
        )
    
    def to_context(self) -> dict:
        return {
            'title': self.title,
            'event_type': self.event_type,
            'date': self.date.strftime('%Y-%m-%d') if self.date else '',
            'time': self.time.strftime('%H:%M') if self.time else '',
            'duration': str(self.duration) if self.duration else '',
            'note': self.note,
            'is_yearly': 'on' if self.is_yearly else '',
        }


@dataclass
class ReminderFormData:
    remind_at: Optional[time] = None
    remind_date: Optional[date] = None
    repeat: bool = False
    repeat_days: List[str] = None
    repeat_every: int = 1
    
    def __post_init__(self):
        if self.repeat_days is None:
            self.repeat_days = []
    
    @classmethod
    def from_post(cls, post_data) -> 'ReminderFormData':
        repeat = post_data.get('repeat') == 'on'
        repeat_every = parse_int(post_data.get('repeat_every')) or 1
        if repeat_every <= 0:
            repeat_every = 1
            
        return cls(
            remind_at=parse_time(post_data.get('remind_at')),
            remind_date=parse_date(post_data.get('remind_date')) if not repeat else None,
            repeat=repeat,
            repeat_days=post_data.getlist('repeat_days') if repeat else [],
            repeat_every=repeat_every,
        )
    
    @classmethod
    def from_reminder(cls, reminder: Optional[ReminderSettings]) -> 'ReminderFormData':
        if not reminder:
            return cls()
        
        return cls(
            remind_at=reminder.remind_at,
            remind_date=reminder.remind_date if not reminder.repeat else None,
            repeat=reminder.repeat,
            repeat_days=[str(d) for d in (reminder.repeat_days or [])],
            repeat_every=reminder.repeat_every or 1,
        )
    
    def to_context(self) -> dict:
        return {
            'remind_at': self.remind_at.strftime('%H:%M') if self.remind_at else '',
            'remind_date': self.remind_date.strftime('%Y-%m-%d') if self.remind_date else '',
            'repeat': 'on' if self.repeat else '',
            'repeat_every': str(self.repeat_every),
            'repeat_days': self.repeat_days,
        }



def parse_time(value: str) -> Optional[time]:
    if not value or len(value) < 5:
        return None
    try:
        return datetime.strptime(value, '%H:%M').time()
    except ValueError:
        return None


def parse_date(value: str) -> Optional[date]:
    if not value or len(value) < 10:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def parse_int(value: str) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None



class EventService:
    
    @staticmethod
    def check_duplicate(pet: Pet, title: str, event_date: date, exclude_id: int = None) -> bool:
        qs = Event.objects.filter(pet=pet, title=title, date=event_date)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        return qs.exists()
    
    @staticmethod
    def calculate_yearly_start_year(event_date: date) -> Tuple[int, Optional[str]]:

        current_year = timezone.now().year
        input_year = event_date.year
        warning = None
        
        if input_year >= current_year - 1:
            start_year = input_year
        else:
            start_year = current_year - 1
            warning = (
                f"Событие создано как ежегодная серия, начинающаяся с {start_year} года, "
                "так как оригинальная дата слишком далеко в прошлом."
            )
        
        return start_year, warning
    
    @staticmethod
    def get_safe_date(year: int, month: int, day: int) -> Optional[date]:
        try:
            return date(year, month, day)
        except ValueError:
            if month == 2 and day == 29:
                return date(year, 2, 28)
            raise
    
    @staticmethod
    def create_yearly_series(
        pet: Pet,
        form_data: EventFormData,
        years: List[int]
    ) -> Tuple[Optional[Event], List[Event]]:

        original_event = None
        created_events = []
        
        for year in years:
            series_date = EventService.get_safe_date(
                year, form_data.date.month, form_data.date.day
            )
            
            if series_date is None:
                logger.info(f"Skipping year {year} for event '{form_data.title}' (invalid date)")
                continue
            
            if EventService.check_duplicate(pet, form_data.title, series_date):
                logger.warning(f"Skipping duplicate: '{form_data.title}' on {series_date}")
                continue
            
            event = Event(
                pet=pet,
                title=form_data.title,
                event_type=form_data.event_type,
                date=series_date,
                time=form_data.time,
                duration_minutes=form_data.duration,
                note=form_data.note,
                is_yearly=True,
                is_done=False,
                original_event=original_event,
            )
            
            if original_event is None:
                event.save()
                original_event = event
            else:
                created_events.append(event)
        
        if created_events:
            Event.objects.bulk_create(created_events)
        
        return original_event, created_events
    
    @staticmethod
    def create_single_event(pet: Pet, form_data: EventFormData) -> Event:
        event = Event(
            pet=pet,
            title=form_data.title,
            event_type=form_data.event_type,
            date=form_data.date,
            time=form_data.time,
            duration_minutes=form_data.duration,
            note=form_data.note,
            is_yearly=False,
            is_done=False,
        )
        event.save()
        return event
    
    @staticmethod
    def get_series_events(event: Event) -> List[Event]:
        if event.original_event:
            main_event = event.original_event
        else:
            main_event = event
        
        return [main_event] + list(main_event.recurring_events.all())
    
    @staticmethod
    def update_events(
        events: List[Event],
        form_data: EventFormData,
        update_date: bool = True
    ) -> List[Event]:
        used_pairs = set()
        updated = []
        
        for ev in events:
            if update_date:
                new_date = date(ev.date.year, form_data.date.month, form_data.date.day)
            else:
                new_date = ev.date
            
            pair = (form_data.title, new_date)
            if pair in used_pairs:
                continue
            
            if EventService.check_duplicate(ev.pet, form_data.title, new_date, exclude_id=ev.id):
                continue
            
            used_pairs.add(pair)
            
            ev.title = form_data.title
            ev.event_type = form_data.event_type
            ev.date = new_date
            ev.time = form_data.time
            ev.duration_minutes = form_data.duration
            ev.note = form_data.note
            ev.is_yearly = form_data.is_yearly
            updated.append(ev)
        
        if updated:
            Event.objects.bulk_update(
                updated,
                ['title', 'event_type', 'date', 'time', 'duration_minutes', 'note', 'is_yearly']
            )
        
        return updated


class ReminderService:
    
    @staticmethod
    def save_reminder(
        event: Event,
        reminder_data: ReminderFormData,
        adjust_date_to_event_year: bool = False
    ) -> Optional[ReminderSettings]:
        if not reminder_data.remind_at:
            return None
        
        reminder, _ = ReminderSettings.objects.get_or_create(
            event=event,
            defaults={'pet': event.pet}
        )
        
        reminder.remind_at = reminder_data.remind_at
        reminder.repeat = reminder_data.repeat
        reminder.repeat_days = reminder_data.repeat_days
        reminder.repeat_every = reminder_data.repeat_every
        
        if reminder_data.remind_date and not reminder_data.repeat:
            if adjust_date_to_event_year:
                reminder.remind_date = date(
                    event.date.year,
                    reminder_data.remind_date.month,
                    reminder_data.remind_date.day
                )
            else:
                reminder.remind_date = reminder_data.remind_date
        else:
            reminder.remind_date = None
        
        reminder.save()
        return reminder
    
    @staticmethod
    def save_reminders_for_events(
        events: List[Event],
        reminder_data: ReminderFormData
    ) -> List[ReminderSettings]:
        reminders = []
        
        for event in events:
            reminder = ReminderService.save_reminder(
                event, reminder_data, adjust_date_to_event_year=True
            )
            if reminder:
                reminders.append(reminder)
        
        return reminders



def check_pet_owner(user, pet: Pet) -> bool:
    return user in pet.owners.all()


def redirect_to_calendar(pet_id: int, event_date: date):
    url = f'/pets/{pet_id}/?tab=calendar#{event_date.strftime("%Y-%m-%d")}'
    return redirect(url)


def _create_yearly_event_v2(
    pet: Pet,
    event_data: EventFormData,
    reminder_data: ReminderFormData
) -> Union[List[Event], str]:
    start_year, _ = EventService.calculate_yearly_start_year(event_data.date)
    
    start_date = EventService.get_safe_date(
        start_year, event_data.date.month, event_data.date.day
    )
    
    if EventService.check_duplicate(pet, event_data.title, start_date):
        return f"Событие с таким названием и датой ({start_date}) уже существует."
    
    years_to_create = [start_year, start_year + 1, start_year + 2]
    original_event, created_events = EventService.create_yearly_series(
        pet, event_data, years_to_create
    )
    
    if not original_event:
        return "Не удалось создать ежегодную серию событий."
    
    all_events = [original_event] + created_events
    ReminderService.save_reminders_for_events(all_events, reminder_data)
    
    return all_events


def _create_single_event_v2(
    pet: Pet,
    event_data: EventFormData,
    reminder_data: ReminderFormData
) -> Union[Event, str]:
    if EventService.check_duplicate(pet, event_data.title, event_data.date):
        return "Событие с таким названием и датой уже существует."
    
    event = EventService.create_single_event(pet, event_data)
    ReminderService.save_reminder(event, reminder_data)
    
    return event


@login_required
def add_event(request, pet_id):
    pet = get_object_or_404(Pet, id=pet_id)
    
    if not check_pet_owner(request.user, pet):
        messages.error(request, "У вас нет прав для добавления событий для этого питомца.")
        return redirect('pets:list')
    
    context = {
        'pet': pet,
        'event_type_choices': EVENT_TYPES,
        'weekday_choices': WEEKDAY_CHOICES,
        'initial': {},
        'error': None,
    }
    
    if request.method != 'POST':
        return render(request, 'calendarapp/add_event.html', context)
    
    event_data = EventFormData.from_post(request.POST)
    reminder_data = ReminderFormData.from_post(request.POST)
    
    context['initial'] = {
        **event_data.to_context(),
        **reminder_data.to_context(),
    }
    
    if not event_data.date:
        context['error'] = "Дата события обязательна."
        return render(request, 'calendarapp/add_event.html', context)
    
    if not event_data.title:
        context['error'] = "Название события обязательно."
        return render(request, 'calendarapp/add_event.html', context)
    
    try:
        with transaction.atomic():
            if event_data.is_yearly:
                result = _create_yearly_event_v2(pet, event_data, reminder_data)
                if isinstance(result, str):
                    context['error'] = result
                    return render(request, 'calendarapp/add_event.html', context)
                else:
                    return redirect_to_calendar(pet_id, result[0].date)
            else:
                result = _create_single_event_v2(pet, event_data, reminder_data)
                if isinstance(result, str):
                    context['error'] = result
                    return render(request, 'calendarapp/add_event.html', context)
                else:
                    return redirect_to_calendar(pet_id, result.date)
    
    except Exception as e:
        logger.error(f"Error adding event for pet {pet_id}: {e}", exc_info=True)
        context['error'] = "Произошла ошибка при добавлении события."
    
    return render(request, 'calendarapp/add_event.html', context)


@login_required
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    
    if not check_pet_owner(request.user, event.pet):
        messages.error(request, "У вас нет прав для редактирования этого события.")
        return redirect('pets:list')
    
    pet = event.pet
    is_birthday = event.event_type == 'birthday'
    reminder = getattr(event, 'reminder', None)
    
    if request.method == 'POST':
        return _handle_edit_post(request, event, is_birthday)
    
    event_data = EventFormData(
        title=event.title or '',
        event_type=event.event_type or '',
        date=event.date,
        time=event.time,
        duration=event.duration_minutes,
        note=event.note or '',
        is_yearly=event.is_yearly,
    )
    
    reminder_data = ReminderFormData.from_reminder(reminder)
    
    context = {
        'event': event,
        'form_data': {**event_data.to_context(), **reminder_data.to_context()},
        'repeat_days_selected': reminder_data.repeat_days,
        'error': None,
        'is_birthday': is_birthday,
        'event_type_choices': EVENT_TYPES,
        'weekday_choices': WEEKDAY_CHOICES,
        'reminder': reminder,
    }
    
    return render(request, 'calendarapp/edit_event.html', context)


def _handle_edit_post(request, event: Event, is_birthday: bool):
    pet = event.pet
    reminder_data = ReminderFormData.from_post(request.POST)
    apply_to_all = request.POST.get('apply_to_all') == 'on'
    
    if is_birthday:
        return _handle_birthday_edit(request, event, reminder_data, apply_to_all)
    
    return _handle_regular_event_edit(request, event, reminder_data, apply_to_all)


def _handle_birthday_edit(
    request,
    event: Event,
    reminder_data: ReminderFormData,
    apply_to_all: bool
):
    pet = event.pet
    
    time_val = parse_time(request.POST.get('time'))
    duration = parse_int(request.POST.get('duration'))
    note = request.POST.get('note', '')
    
    with transaction.atomic():
        if apply_to_all:
            events = Event.objects.select_for_update().filter(
                pet=pet, event_type='birthday', is_yearly=True
            )
        else:
            events = [event]
        
        for ev in events:
            ev.time = time_val
            ev.duration_minutes = duration
            ev.note = note
            ev.save()
        
        ReminderService.save_reminders_for_events(list(events), reminder_data)
    
    return redirect_to_calendar(pet.id, event.date)


def _handle_regular_event_edit(
    request,
    event: Event,
    reminder_data: ReminderFormData,
    apply_to_all: bool
):
    pet = event.pet
    event_data = EventFormData.from_post(request.POST)
    
    context = {
        'event': event,
        'form_data': {**event_data.to_context(), **reminder_data.to_context()},
        'repeat_days_selected': reminder_data.repeat_days,
        'event_type_choices': EVENT_TYPES,
        'weekday_choices': WEEKDAY_CHOICES,
        'reminder': getattr(event, 'reminder', None),
        'is_birthday': event.event_type == 'birthday',
    }

    if not event_data.date:
        context['error'] = "Неверный формат даты."
        return render(request, 'calendarapp/edit_event.html', context)
    
    if event_data.is_yearly and event_data.date.month == 2 and event_data.date.day == 29:
        context['error'] = "29 февраля не может быть установлено для ежегодного события."
        return render(request, 'calendarapp/edit_event.html', context)
    
    with transaction.atomic():
        if apply_to_all and event.is_yearly:
            events = EventService.get_series_events(event)
        else:
            events = [event]
        
        updated_events = EventService.update_events(events, event_data)
        ReminderService.save_reminders_for_events(updated_events, reminder_data)
    
    return redirect_to_calendar(pet.id, event.date)


@login_required
def mark_done(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    
    if not check_pet_owner(request.user, event.pet):
        messages.error(request, "У вас нет прав для изменения этого события.")
        return redirect('pets:list')
    
    event.is_done = True
    event.done_year = timezone.now().year
    event.save()
    
    return redirect_to_calendar(event.pet.id, event.date)



@login_required
def delete_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    
    if not check_pet_owner(request.user, event.pet):
        return redirect('pets:list')
    
    pet = event.pet
    event_date = event.date
    
    # Обрабатываем только POST-запросы
    if request.method != 'POST':
        return redirect_to_calendar(pet.id, event_date)
    
    is_series_original = (
        event.is_yearly and 
        event.recurring_events.exists() and 
        event.original_event is None
    )
    
    delete_all = request.POST.get('delete_all') == 'on'
    
    if is_series_original and not delete_all:
        error_msg = f"Нельзя удалить только первое событие в ежегодной серии '{event.title}'. Удалите всю серию при необходимости."
        request.session['calendar_error'] = error_msg
        return redirect_to_calendar(pet.id, event_date)
    
    event_title = event.title
    
    try:
        with transaction.atomic():
            if delete_all and event.is_yearly:
                Event.objects.filter(pet=pet, title=event_title, is_yearly=True).delete()
                logger.info(f"Deleted yearly series '{event_title}' for pet {pet.id}")
            else:
                event.delete()
                logger.info(f"Deleted event {event_id} for pet {pet.id}")
    except Exception as e:
        logger.error(f"Error deleting event {event_id}: {e}", exc_info=True)
        error_msg = "Произошла ошибка при удалении события."
        request.session['calendar_error'] = error_msg
        return redirect_to_calendar(pet.id, event_date)
    
    return redirect_to_calendar(pet.id, event_date)


def create_next_year_events():
    current_year = timezone.now().year
    next_year = current_year + 1
    target_year = next_year + 1
    
    last_year_events = Event.objects.filter(
        is_yearly=True,
        date__year=current_year - 1
    )
    
    created_count = 0
    
    for event in last_year_events:
        new_date = EventService.get_safe_date(
            target_year, event.date.month, event.date.day
        )
        
        if new_date and not EventService.check_duplicate(event.pet, event.title, new_date):
            Event.objects.create(
                pet=event.pet,
                title=event.title,
                event_type=event.event_type,
                date=new_date,
                time=event.time,
                duration_minutes=event.duration_minutes,
                note=event.note,
                is_yearly=True,
                is_done=False,
                original_event=event.original_event or event,
            )
            created_count += 1
    
    logger.info(f"Created {created_count} events for year {target_year}")
    return created_count
