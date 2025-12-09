import uuid
from venv import logger
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Pet
from calendarapp.models import Event, ReminderSettings
from datetime import date, timedelta, datetime, time
import copy
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def pets_list(request):
    pets = request.user.pets.all()
    return render(request, 'pets/pets_list.html', {'pets': pets})

@login_required
def pet_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        pet_type = request.POST.get('pet_type', 'dog')
        custom_pet_type = request.POST.get('custom_pet_type', '').strip()
        birthday = request.POST.get('birthday')
        weight = request.POST.get('weight') or None
        breed = request.POST.get('breed') or ''
        gender = request.POST.get('gender') or None
        photo = request.FILES.get('photo')
        features = request.POST.get('features') or ''

        # Валидация обязательных полей
        if not name:
            messages.error(request, 'Имя питомца обязательно для заполнения.')
            return render(request, 'pets/pet_add.html')
        
        if not birthday:
            messages.error(request, 'Дата рождения обязательна для заполнения.')
            return render(request, 'pets/pet_add.html')

        # Если выбран "Другое", используем кастомное значение
        if pet_type == 'other' and custom_pet_type:
            # Используем кастомное значение как основной тип
            final_pet_type = 'other'
            final_custom_type = custom_pet_type
        else:
            final_pet_type = pet_type
            final_custom_type = ''

        try:
            pet = Pet.objects.create(
                name=name,
                pet_type=final_pet_type,
                custom_pet_type=final_custom_type,
                birthday=birthday,
                weight=weight,
                breed=breed,
                gender=gender,
                photo=photo,
                features=features
            )
            pet.owners.add(request.user)
            create_or_update_birthday_event(pet)
            messages.success(request, f'Питомец {name} успешно добавлен!')
            return redirect('pets:list')
        except Exception as e:
            messages.error(request, f'Ошибка при создании питомца: {str(e)}')
            return render(request, 'pets/pet_add.html')

    return render(request, 'pets/pet_add.html')

@login_required
def pet_edit(request, pet_id):
    pet = get_object_or_404(Pet, id=pet_id)

    # Проверяем, что пользователь является создателем питомца
    if not is_pet_creator(request.user, pet):
        messages.error(request, 'Только создатель питомца может редактировать его профиль.')
        return redirect('pets:list')

    if request.method == 'POST':
        pet.name = request.POST.get('name')
        pet.pet_type = request.POST.get('pet_type', 'dog')
        custom_pet_type = request.POST.get('custom_pet_type', '').strip()
        
        # Валидация обязательных полей
        if not pet.name:
            messages.error(request, 'Имя питомца обязательно для заполнения.')
            return render(request, 'pets/pet_edit.html', {'pet': pet})
        
        # Обработка кастомного типа
        if pet.pet_type == 'other' and custom_pet_type:
            pet.custom_pet_type = custom_pet_type
        else:
            pet.custom_pet_type = ''
        
        birthday_input = request.POST.get('birthday')
        if not birthday_input:
            messages.error(request, 'Дата рождения обязательна для заполнения.')
            return render(request, 'pets/pet_edit.html', {'pet': pet})
        
        pet.birthday = birthday_input
        pet.weight = request.POST.get('weight') or None
        pet.breed = request.POST.get('breed') or ''
        pet.gender = request.POST.get('gender') or None
        pet.features = request.POST.get('features') or ''
        
        if request.FILES.get('photo'):
            pet.photo = request.FILES['photo']
        
        try:
            pet.save()
            Event.objects.filter(pet=pet, event_type='birthday', is_yearly=True).delete()
            create_or_update_birthday_event(pet)
            messages.success(request, f'Информация о питомце {pet.name} обновлена!')
            return redirect('pets:detail', pet_id=pet.id)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении питомца: {str(e)}')
            return render(request, 'pets/pet_edit.html', {'pet': pet})

    return render(request, 'pets/pet_edit.html', {'pet': pet})

@login_required
def pet_detail(request, pet_id):
    pet = get_object_or_404(Pet, id=pet_id)

    if request.user not in pet.owners.all():
        messages.error(request, 'У вас нет доступа к этому питомцу.')
        return redirect('pets:list')

    tab = request.GET.get('tab', 'info')
    context = {'pet': pet, 'tab': tab}

    if tab == 'info':
        birthday_today = False
        birthday_soon = None

        if pet.birthday:
            today = date.today()
            next_birthday = pet.birthday.replace(year=today.year)
            if next_birthday < today:
                next_birthday = next_birthday.replace(year=today.year + 3)

            delta = (next_birthday - today).days
            if delta == 0:
                birthday_today = True
            elif delta <= 7:
                birthday_soon = delta

        # Проверяем, является ли пользователь создателем питомца
        is_creator = is_pet_creator(request.user, pet)
        context.update({
            'birthday_today': birthday_today,
            'birthday_soon': birthday_soon,
            'is_creator': is_creator,
        })

    elif tab == 'calendar':
        today = date.today()
        events = Event.objects.filter(pet=pet).order_by('date', 'time')
        context['events'] = events

    return render(request, 'pets/pet_detail.html', context)

@login_required
def remove_owner(request, pet_id, owner_id):
    """Удаление совладельца из профиля питомца"""
    pet = get_object_or_404(Pet, id=pet_id)
    
    # Проверяем, что пользователь является создателем питомца
    if not is_pet_creator(request.user, pet):
        messages.error(request, 'Только создатель питомца может удалять совладельцев.')
        return redirect('pets:detail', pet_id=pet_id)
    
    # Проверяем, что не пытаемся удалить последнего владельца
    if pet.owners.count() <= 1:
        messages.error(request, 'Нельзя удалить последнего владельца питомца.')
        return redirect('pets:detail', pet_id=pet_id)
    
    # Находим владельца для удаления
    owner_to_remove = get_object_or_404(User, id=owner_id)
    
    # Не позволяем удалить самого создателя
    if is_pet_creator(owner_to_remove, pet):
        messages.error(request, 'Нельзя удалить создателя питомца.')
        return redirect('pets:detail', pet_id=pet_id)
    
    try:
        # Удаляем владельца
        pet.owners.remove(owner_to_remove)
        messages.success(request, f'Владелец {owner_to_remove.email} удален из профиля питомца.')
    except Exception as e:
        messages.error(request, f'Ошибка при удалении владельца: {str(e)}')
    
    return redirect('pets:detail', pet_id=pet_id)

@login_required
def pet_delete(request, pet_id):
    """Удаление питомца"""
    pet = get_object_or_404(Pet, id=pet_id)

    # Проверяем, что пользователь является создателем питомца
    if not is_pet_creator(request.user, pet):
        messages.error(request, 'Только создатель питомца может удалить его профиль.')
        return redirect('pets:list')

    if request.method == 'POST':
        pet_name = pet.name
        try:
            # Удаляем все связанные события перед удалением питомца
            Event.objects.filter(pet=pet).delete()
            pet.delete()
            messages.success(request, f'Питомец {pet_name} удален.')
            return redirect('pets:list')
        except Exception as e:
            messages.error(request, f'Ошибка при удалении питомца: {str(e)}')
            return redirect('pets:detail', pet_id=pet_id)

    return render(request, 'pets/pet_delete.html', {'pet': pet})

def is_pet_creator(user, pet):
    """
    Проверяет, является ли пользователь создателем питомца.
    Создателем считается первый владелец, добавленный к питомцу.
    """

    if pet.owners.exists():
        return pet.owners.first() == user
    return False

def create_or_update_birthday_event(pet):
    """Создает или обновляет события дня рождения для питомца"""
    if not pet.birthday:
        return

    if isinstance(pet.birthday, str):
        try:
            pet_birthday = datetime.strptime(pet.birthday, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Invalid birthday format for pet {pet.id}: {pet.birthday}")
            return
    else:
        pet_birthday = pet.birthday

    # Удаляем старое событие, если оно существует
    Event.objects.filter(pet=pet, event_type='birthday', is_yearly=True).delete()

    current_year = date.today().year
    
    try:
        for year in [current_year, current_year + 1, current_year + 2]:
            try:
                new_date = pet_birthday.replace(year=year)
            except ValueError:
                # Обработка 29 февраля для невисокосных годов
                if pet_birthday.month == 2 and pet_birthday.day == 29:
                    new_date = date(year, 2, 28)
                else:
                    raise
            
            event = Event.objects.create(
                pet=pet,
                title='День рождения',
                event_type='birthday',
                date=new_date,
                time=None,
                duration_minutes=None,
                note=f'День рождения {pet.name}',
                is_yearly=True,
                is_done=False
            )
            
            # Создаем напоминание только для текущего года
            if year == current_year:
                ReminderSettings.objects.update_or_create(
                    event=event,
                    defaults={
                        'pet': pet,
                        'repeat': True,
                        'repeat_every': 365,
                        'remind_at': time(9, 0)
                    }
                )
    except Exception as e:
        logger.error(f"Error creating birthday events for pet {pet.id}: {e}")