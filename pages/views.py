from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from pets.models import Pet
from calendarapp.models import Event
# УДАЛЕНО: from training.models import PetLessonProgress
from datetime import date, timedelta

@login_required
def dashboard(request):
    pets = Pet.objects.filter(owners=request.user)
    today = date.today()
    two_weeks_later = today + timedelta(days=30)

    # Получаем события на ближайшие 2 недели, которые не выполнены
    events = Event.objects.filter(
        pet__in=pets,
        date__gte=today,
        date__lte=two_weeks_later,
        is_done=False
    ).order_by('date', 'time')  # Сортируем по дате и времени

    # УДАЛЕНО: Дрессировки в процессе
    # progress = PetLessonProgress.objects.filter(
    #     pet__in=pets,
    #     status='in_progress'
    # )

    # Ближайшие дни рождения (30 дней)
    upcoming_birthdays = []
    for pet in pets:
        if pet.birthday:
            next_bd = pet.birthday.replace(year=today.year)
            if next_bd < today:
                next_bd = next_bd.replace(year=today.year + 1)
            days_left = (next_bd - today).days
            if days_left <= 30:
                upcoming_birthdays.append((pet, days_left))

    return render(request, 'dashboard.html', {
        'events': events,  # Теперь без ограничения количества
        # УДАЛЕНО: 'progress': progress,
        'birthdays': upcoming_birthdays,
    })