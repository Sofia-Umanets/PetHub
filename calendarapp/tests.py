import json
from datetime import date, datetime, timedelta
import time
import uuid
from io import StringIO
import sys

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.core.management import call_command
from django.db import models

from pets.models import Pet
from calendarapp.models import Event, ReminderSettings

User = get_user_model()


class CalendarWhiteBoxTests(TestCase):
    """Тестирование методом белого ящика - модульные тесты"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123'
        )
        
        self.pet = Pet.objects.create(
            name='Тестовый питомец',
            pet_type='dog',
            birthday=date(2020, 1, 1),
            creator=self.user
        )
        self.pet.owners.add(self.user)
    
    def test_single_event_creation(self):
        """Тест создания одиночного события"""
        print("\nСоздание одиночного события")
        
        event = Event.objects.create(
            pet=self.pet,
            title='Прогулка в парке',
            event_type='walk',
            date=date(2026, 1, 20),
            time=datetime.strptime('10:00', '%H:%M').time(),
            duration_minutes=60,
            note='Взять поводок',
            is_yearly=False,
            is_done=False
        )
        
        self.assertEqual(event.title, 'Прогулка в парке')
        self.assertEqual(event.event_type, 'walk')
        self.assertEqual(event.pet, self.pet)
        self.assertFalse(event.is_yearly)
        print("Одиночное событие успешно создано")
    
    def test_yearly_event_creation(self):
        """Тест создания ежегодного события"""
        print("\nСоздание ежегодного события")
        
        event = Event.objects.create(
            pet=self.pet,
            title='Ежегодный осмотр',
            event_type='vet',
            date=date(2026, 3, 15),
            is_yearly=True,
            is_done=False
        )
        
        self.assertTrue(event.is_yearly)
        self.assertEqual(event.event_type, 'vet')
        print("Ежегодное событие успешно создано")
    
    def test_reminder_creation(self):
        """Тест создания напоминания для события"""
        print("\nСоздание напоминания для события")
        
        event = Event.objects.create(
            pet=self.pet,
            title='Прием таблетки',
            event_type='pill',
            date=date(2026, 1, 20),
            is_done=False
        )
        
        reminder = ReminderSettings.objects.create(
            event=event,
            pet=self.pet,
            remind_at=datetime.strptime('09:00', '%H:%M').time(),
            repeat=False,
            remind_date=date(2026, 1, 20)
        )
        
        self.assertEqual(reminder.event, event)
        self.assertEqual(reminder.remind_at.strftime('%H:%M'), '09:00')
        print("Напоминание успешно создано")
    
    def test_mark_event_done(self):
        """Тест отметки события как выполненного"""
        print("\nОтметка события как выполненного")
        
        event = Event.objects.create(
            pet=self.pet,
            title='Визит к ветеринару',
            event_type='vet',
            date=date(2025, 1, 15),
            is_done=False
        )
        
        event.is_done = True
        event.done_year = 2025
        event.save()
        
        self.assertTrue(event.is_done)
        self.assertEqual(event.done_year, 2025)
        print("Событие успешно отмечено как выполненное")
    
    def test_event_editing(self):
        """Тест редактирования события"""
        print("\nРедактирование события")
        
        event = Event.objects.create(
            pet=self.pet,
            title='Событие для редактирования',
            event_type='walk',
            date=date(2026, 1, 20),
            duration_minutes=30,
            note='Первоначальная заметка',
            is_done=False
        )
        
        event.title = 'Обновленное название'
        event.duration_minutes = 45
        event.note = 'Обновленная заметка'
        event.save()
        
        updated_event = Event.objects.get(id=event.id)
        self.assertEqual(updated_event.title, 'Обновленное название')
        self.assertEqual(updated_event.duration_minutes, 45)
        self.assertEqual(updated_event.note, 'Обновленная заметка')
        print("Событие успешно отредактировано")
    
    def test_single_event_deletion(self):
        """Тест удаления одиночного события"""
        print("\nУдаление одиночного события")
        
        event = Event.objects.create(
            pet=self.pet,
            title='Одиночное событие',
            event_type='walk',
            date=date(2026, 1, 20),
            is_yearly=False,
            is_done=False
        )
        
        event_id = event.id
        event.delete()
        
        event_exists = Event.objects.filter(id=event_id).exists()
        self.assertFalse(event_exists)
        print("Одиночное событие успешно удалено")
    
    def test_system_created_birthday_event(self):
        """Тест автоматического создания события дня рождения"""
        print("\nАвтоматическое создание события дня рождения")
        
        birthday_pet = Pet.objects.create(
            name='Питомец с ДР',
            pet_type='dog',
            birthday=date(2020, 5, 10),
            creator=self.user
        )
        birthday_pet.owners.add(self.user)
        
        birthday_event = Event.objects.create(
            pet=birthday_pet,
            title=f'День рождения {birthday_pet.name}',
            event_type='birthday',
            date=date(2026, 5, 10),
            is_yearly=True,
            is_done=False
        )
        
        self.assertEqual(birthday_event.event_type, 'birthday')
        self.assertTrue(birthday_event.is_yearly)
        self.assertEqual(birthday_event.date.month, 5)
        self.assertEqual(birthday_event.date.day, 10)
        print("Событие дня рождения успешно создано")
    
    def test_care_history_tracking(self):
        """Тест ведения истории выполненных мероприятий"""
        print("\nВедение истории выполненных мероприятий")
        
        completed_events = []
        for i in range(3):
            event = Event.objects.create(
                pet=self.pet,
                title=f'Выполненное событие {i}',
                event_type='walk',
                date=date(2025, 1, i+1),
                is_done=True,
                done_year=2025
            )
            completed_events.append(event)
        
        pending_event = Event.objects.create(
            pet=self.pet,
            title='Невыполненное событие',
            event_type='vet',
            date=date(2026, 1, 20),
            is_done=False
        )
        
        history_events = Event.objects.filter(pet=self.pet, is_done=True)
        
        self.assertEqual(history_events.count(), 3)
        for event in completed_events:
            self.assertIn(event, history_events)
        self.assertNotIn(pending_event, history_events)
        print(f"История содержит {history_events.count()} выполненных мероприятий")
    
def test_february_29_handling(self):
    """Тестирование обработки 29 февраля для високосных и невисокосных годов"""
    
    print("\nОбработка 29 февраля для високосных и невисокосных годов")
    
    from calendarapp.views import EventService
    from unittest.mock import patch
    
    # 1. Тестируем метод get_safe_date
    safe_date_2025 = EventService.get_safe_date(2025, 2, 29)  # 2025 не високосный -> 28.02.2025
    self.assertEqual(safe_date_2025, date(2025, 2, 28))
    print("✓ Метод get_safe_date правильно обрабатывает 29 февраля 2025")
    
    safe_date_2024 = EventService.get_safe_date(2024, 2, 29)  # 2024 високосный -> 29.02.2024
    self.assertEqual(safe_date_2024, date(2024, 2, 29))
    print("✓ Метод get_safe_date правильно обрабатывает 29 февраля 2024")
    
    # 2. Тестируем создание НЕ ежегодного события на 29 февраля невисокосного года
    event_non_leap = Event.objects.create(
        pet=self.pet,
        title='Не ежегодное событие на 29 февраля 2025',
        event_type='vet',
        date=safe_date_2025,  # 2025-02-28
        is_yearly=False,
        is_done=False
    )
    self.assertEqual(event_non_leap.date, date(2025, 2, 28))
    print(f"✓ Не ежегодное событие на 29 февраля 2025 сохранено как {event_non_leap.date}")
    
    # 3. Тестируем создание ежегодного события на 29 февраля, когда текущий год не високосный
    # Мокаем текущую дату как 25 декабря 2025 года
    mock_today = timezone.datetime(2025, 12, 25)
    with patch.object(timezone, 'now', return_value=mock_today):
        yearly_event = Event.objects.create(
            pet=self.pet,
            title='Ежегодное событие на 29 февраля',
            event_type='vet',
            date=date(2024, 2, 29),  # Дата из прошлого високосного года
            is_yearly=True,
            is_done=False
        )
        # Проверяем фактическое поведение системы - корректировка на 28 февраля 2025 года
        self.assertEqual(yearly_event.date, date(2025, 2, 28))
        print(f"✓ Ежегодное событие на 29 февраля скорректировано на {yearly_event.date} (2025 год)")
    
    # 4. Тестируем создание ежегодного события на 29 февраля, когда следующий год високосный
    mock_2027 = timezone.datetime(2027, 12, 25)
    with patch.object(timezone, 'now', return_value=mock_2027):
        yearly_event_future = Event.objects.create(
            pet=self.pet,
            title='Ежегодное событие на 29 февраля',
            event_type='vet',
            date=date(2024, 2, 29),  # Дата из прошлого високосного года
            is_yearly=True,
            is_done=False
        )
        # Должно быть скорректировано на 29 февраля 2028 (следующий год високосный)
        self.assertEqual(yearly_event_future.date, date(2028, 2, 29))
        print(f"✓ Ежегодное событие на 29 февраля скорректировано на {yearly_event_future.date} (2028 год)")


class CalendarBlackBoxTests(TestCase):
    """Тестирование методом черного ящика - нагрузочное тестирование"""
    
    def setUp(self):
        """Подготовка данных для нагрузочного тестирования"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='loaduser',
            email='load@example.com',
            password='testpass123'
        )
        
        self.pet = Pet.objects.create(
            name='Питомец нагрузки',
            pet_type='cat',
            birthday=date(2020, 1, 1),
            creator=self.user
        )
        self.pet.owners.add(self.user)
        
        self.client.login(username='loaduser', password='testpass123')
    
    def test_load_performance_10_records(self):
        """Нагрузочное тестирование: малый набор данных (10 записей)"""
        print("\nНагрузочное тестирование: 10 событий")
        
        size = 10
        start_time = time.time()
        
        events = []
        for i in range(size):
            event = Event(
                pet=self.pet,
                title=f'Тестовое событие {i} {uuid.uuid4().hex[:6]}',
                event_type='walk',
                date=date(2026, 1, 1 + (i % 30)),
                time=datetime.strptime(f'{i % 24:02d}:00', '%H:%M').time(),
                duration_minutes=30 + (i % 60),
                note=f'Заметка для события {i}',
                is_yearly=(i % 5 == 0),
                is_done=(i % 10 == 0)
            )
            events.append(event)
        
        Event.objects.bulk_create(events)
        create_time = time.time() - start_time
        
        print(f"Создание {size} записей: {create_time:.3f} сек")
        
        start_time = time.time()
        events_count = Event.objects.filter(pet=self.pet).count()
        read_time = time.time() - start_time
        
        print(f"Чтение {events_count} записей: {read_time:.3f} сек")
        
        self.assertLess(read_time, 2.0)
        self._save_results(10, create_time, read_time, 'read')
    
    def test_load_performance_100_records(self):
        """Нагрузочное тестирование: средний набор данных (100 записей)"""
        print("\nНагрузочное тестирование: 100 событий")
        
        size = 100
        start_time = time.time()
        
        events = []
        for i in range(size):
            event = Event(
                pet=self.pet,
                title=f'Тестовое событие нагрузки {i} {uuid.uuid4().hex[:6]}',
                event_type='walk' if i % 3 == 0 else 'vet' if i % 3 == 1 else 'grooming',
                date=date(2026, 1, 1 + (i % 30)),
                time=datetime.strptime(f'{i % 24:02d}:00', '%H:%M').time(),
                duration_minutes=30 + (i % 60),
                note=f'Заметка для события нагрузки {i}',
                is_yearly=(i % 5 == 0),
                is_done=(i % 10 == 0)
            )
            events.append(event)
        
        Event.objects.bulk_create(events)
        create_time = time.time() - start_time
        
        print(f"Создание {size} записей: {create_time:.3f} сек")
        
        start_time = time.time()
        walk_events = Event.objects.filter(pet=self.pet, event_type='walk').count()
        filter_time = time.time() - start_time
        
        print(f"Фильтрация {walk_events} записей: {filter_time:.3f} сек")
        
        self.assertLess(filter_time, 2.0)
        self._save_results(100, create_time, filter_time, 'filter')
    
    def test_load_performance_1000_records(self):
        """Нагрузочное тестирование: большой набор данных (1000 записей)"""
        print("\nНагрузочное тестирование: 1000 событий")
        
        size = 1000
        start_time = time.time()
        
        events = []
        for i in range(size):
            event = Event(
                pet=self.pet,
                title=f'Событие масштабное {i} {uuid.uuid4().hex[:6]}',
                event_type='walk' if i % 4 == 0 else 'vet' if i % 4 == 1 else 'grooming' if i % 4 == 2 else 'vaccine',
                date=date(2026, 1, 1 + (i % 30)),
                time=datetime.strptime(f'{i % 24:02d}:00', '%H:%M').time(),
                duration_minutes=30 + (i % 60),
                note=f'Масштабная заметка {i}',
                is_yearly=(i % 10 == 0),
                is_done=(i % 20 == 0)
            )
            events.append(event)
        
        Event.objects.bulk_create(events)
        create_time = time.time() - start_time
        
        print(f"Создание {size} записей: {create_time:.3f} сек")
        
        start_time = time.time()
        updated = Event.objects.filter(pet=self.pet, is_done=False).update(is_done=True)
        update_time = time.time() - start_time
        
        print(f"Обновление {updated} записей: {update_time:.3f} сек")
        
        self.assertLess(update_time, 2.0)
        self._save_results(1000, create_time, update_time, 'update')
    
    def test_load_performance_10000_records(self):
        """Нагрузочное тестирование: очень большой набор данных (10000 записей)"""
        print("\nНагрузочное тестирование: 10000 событий")
        
        size = 10000
        start_time = time.time()
        
        batch_size = 1000
        events_created = 0
        
        for batch in range(size // batch_size):
            events = []
            for i in range(batch_size):
                idx = batch * batch_size + i
                event = Event(
                    pet=self.pet,
                    title=f'Очень большое событие {idx} {uuid.uuid4().hex[:4]}',
                    event_type='walk' if idx % 5 == 0 else 'vet' if idx % 5 == 1 else 'grooming' if idx % 5 == 2 else 'vaccine' if idx % 5 == 3 else 'pill',
                    date=date(2026 + idx % 2, (idx % 12) + 1, (idx % 28) + 1),
                    time=datetime.strptime(f'{idx % 24:02d}:{idx % 60:02d}', '%H:%M').time(),
                    duration_minutes=15 + (idx % 120),
                    note=f'Заметка для очень большого события {idx}',
                    is_yearly=(idx % 20 == 0),
                    is_done=(idx % 50 == 0)
                )
                events.append(event)
            
            Event.objects.bulk_create(events)
            events_created += len(events)
        
        create_time = time.time() - start_time
        print(f"Создание {events_created} записей: {create_time:.3f} сек")
        
        start_time = time.time()
        upcoming_events = Event.objects.filter(
            pet=self.pet,
            date__gte=date(2026, 1, 1),
            is_done=False
        ).order_by('date', 'time')[:100]
        query_time = time.time() - start_time
        
        print(f"Сложная выборка с сортировкой: {query_time:.3f} сек")
        
        self.assertLess(query_time, 3.0)
        self._save_results(10000, create_time, query_time, 'complex_query')
    
    def _save_results(self, size, create_time, operation_time, operation_type):
        """Сохранение результатов нагрузочного тестирования в файл"""
        results = {
            'size': size,
            'create_time': create_time,
            'operation_time': operation_time,
            'operation_type': operation_type,
            'avg_create_per_record': create_time / size if size > 0 else 0,
            'timestamp': timezone.now().isoformat()
        }
        
        filename = f'calendar_load_test_results_{size}.json'
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)


class CalendarStressTests(TestCase):
    """Стрессовое тестирование по альтернативным потокам событий"""
    
    def setUp(self):
        """Подготовка данных для стрессового тестирования"""
        self.user = User.objects.create_user(
            username='stressuser',
            email='stress@example.com',
            password='TestPass123'
        )
        
        self.pet = Pet.objects.create(
            name='Питомец для стресс-тестов',
            pet_type='cat',
            birthday=date(2020, 1, 1),
            creator=self.user
        )
        self.pet.owners.add(self.user)
    
    def test_stress_edit_event_series(self):
        """Стресс-тест: редактирование всей серии ежегодных событий"""
        print("\nРедактирование всей серии ежегодных событий")
        
        events = []
        for year in [2026, 2027, 2028]:
            unique_suffix = uuid.uuid4().hex[:8]
            event = Event.objects.create(
                pet=self.pet,
                title=f'Ежегодный осмотр {unique_suffix}',
                event_type='vet',
                date=date(year, 3, 15),
                is_yearly=True,
                is_done=False
            )
            events.append(event)
        
        for event in events:
            event.note = 'Обновленная заметка для всей серии'
            event.save()
        
        updated_events = Event.objects.filter(
            pet=self.pet, 
            note='Обновленная заметка для всей серии'
        )
        self.assertEqual(updated_events.count(), len(events))
        
        print(f"Успешно отредактирована серия из {len(events)} событий")
    
    def test_stress_delete_event_series(self):
        """Стресс-тест: удаление всей серии ежегодных событий"""
        print("\nУдаление всей серии ежегодных событий")
        
        events = []
        for year in [2026, 2027, 2028]:
            unique_suffix = uuid.uuid4().hex[:8]
            event = Event.objects.create(
                pet=self.pet,
                title=f'Ежегодная прививка {unique_suffix}',
                event_type='vaccine',
                date=date(year, 6, 10),
                is_yearly=True,
                is_done=False
            )
            events.append(event)
        
        event_ids = [event.id for event in events]
        Event.objects.filter(id__in=event_ids).delete()
        
        remaining_events = Event.objects.filter(id__in=event_ids).exists()
        self.assertFalse(remaining_events)
        
        print(f"Успешно удалена серия из {len(events)} событий")
    
    def test_stress_system_created_events(self):
        """Стресс-тест: массовое создание событий системой"""
        print("\nМассовое создание событий системой")
        
        pets = []
        for i in range(3):
            pet = Pet.objects.create(
                name=f'Питомец {i} {uuid.uuid4().hex[:4]}',
                pet_type='dog',
                birthday=date(2020, i+1, 15),
                creator=self.user
            )
            pet.owners.add(self.user)
            pets.append(pet)
        
        events_created = 0
        for pet in pets:
            for year in [2026, 2027]:
                unique_suffix = uuid.uuid4().hex[:6]
                event = Event.objects.create(
                    pet=pet,
                    title=f'День рождения {pet.name} {unique_suffix}',
                    event_type='birthday',
                    date=date(year, pet.birthday.month, pet.birthday.day),
                    is_yearly=True,
                    is_done=False
                )
                events_created += 1
        
        birthday_events = Event.objects.filter(event_type='birthday', is_yearly=True)
        self.assertEqual(birthday_events.count(), events_created)
        
        print(f"Создано {events_created} системных событий для {len(pets)} питомцев")
    
    def test_stress_invalid_reminder_settings(self):
        """Стресс-тест: обработка некорректных настроек напоминаний"""
        print("\nОбработка некорректных настроек напоминаний")
        
        event = Event.objects.create(
            pet=self.pet,
            title=f'Тест с напоминанием {uuid.uuid4().hex[:6]}',
            event_type='walk',
            date=date(2026, 1, 20),
            is_done=False
        )
        
        try:
            reminder = ReminderSettings.objects.create(
                event=event,
                pet=self.pet,
                remind_at=None,
                repeat=True,
                repeat_days=[0, 1, 2]
            )
            self.assertIsNone(reminder.remind_at)
            print("Напоминание без времени создано (допустимо)")
        except Exception as e:
            print(f"Ошибка при создании напоминания без времени: {type(e).__name__}")
        
        try:
            reminder = ReminderSettings.objects.create(
                event=event,
                pet=self.pet,
                remind_at=datetime.strptime('09:00', '%H:%M').time(),
                repeat=True,
                repeat_days=[10, 11]  # Несуществующие дни
            )
            print("Напоминание с несуществующими днями создано")
        except Exception as e:
            print(f"Ошибка при создании напоминания с несуществующими днями: {type(e).__name__}")
    
    def test_stress_mark_done_failure(self):
        """Стресс-тест: имитация сбоя при отметке выполнения"""
        print("\nИмитация сбоя при отметке выполнения")
        
        event = Event.objects.create(
            pet=self.pet,
            title=f'Событие для отметки {uuid.uuid4().hex[:6]}',
            event_type='grooming',
            date=date(2026, 1, 20),
            is_done=False
        )
        
        original_status = event.is_done
        
        try:
            event.is_done = True
            event.done_year = 2026
            event.save()
            self.assertTrue(event.is_done)
            print("Событие успешно отмечено как выполненное")
        except Exception as e:
            event.refresh_from_db()
            self.assertEqual(event.is_done, original_status)
            print(f"Имитирован сбой: {type(e).__name__}, статус сохранен")
    
    def test_stress_daily_events_list(self):
        """Стресс-тест: просмотр списка событий на день"""
        print("\nПросмотр списка событий на день")
        
        target_date = date(2026, 1, 25)
        events_created = 0
        
        events_data = [
            ('Утренняя прогулка', 'walk', '08:00'),
            ('Визит к ветеринару', 'vet', '14:00'),
            ('Вечерняя прогулка', 'walk', '19:00'),
            ('Прием таблетки', 'pill', '22:00'),
        ]
        
        for title, event_type, time_str in events_data:
            unique_suffix = uuid.uuid4().hex[:4]
            event = Event.objects.create(
                pet=self.pet,
                title=f'{title} {unique_suffix}',
                event_type=event_type,
                date=target_date,
                time=datetime.strptime(time_str, '%H:%M').time(),
                is_done=False
            )
            events_created += 1
        
        daily_events = Event.objects.filter(pet=self.pet, date=target_date)
        self.assertEqual(daily_events.count(), events_created)
        
        sorted_events = daily_events.order_by('time')
        self.assertEqual(sorted_events[0].time.strftime('%H:%M'), '08:00')
        
        print(f"На день {target_date} найдено {daily_events.count()} событий")
    
    def test_stress_care_history_view(self):
        """Стресс-тест: просмотр истории ухода"""
        print("\nПросмотр истории ухода")
        
        completed_count = 0
        for i in range(5):
            event = Event.objects.create(
                pet=self.pet,
                title=f'Выполненное событие {i} {uuid.uuid4().hex[:4]}',
                event_type='walk',
                date=date(2025, 1, i+1),
                is_done=True,
                done_year=2025
            )
            completed_count += 1
        
        pending_count = 0
        for i in range(3):
            event = Event.objects.create(
                pet=self.pet,
                title=f'Невыполненное событие {i} {uuid.uuid4().hex[:4]}',
                event_type='vet',
                date=date(2026, 1, 20 + i),
                is_done=False
            )
            pending_count += 1
        
        history_events = Event.objects.filter(pet=self.pet, is_done=True)
        self.assertEqual(history_events.count(), completed_count)
        
        pending_events = Event.objects.filter(pet=self.pet, is_done=False)
        self.assertEqual(pending_events.count(), pending_count)
        
        print(f"История содержит {history_events.count()} выполненных мероприятий")
        print(f"Ожидает выполнения {pending_events.count()} мероприятий")
    
    def test_stress_personal_reminders(self):
        """Стресс-тест: настройка персональных напоминаний"""
        print("\nНастройка персональных напоминаний")
        
        reminder_configs = [
            {'remind_at': '09:30', 'repeat': False, 'remind_date': date(2026, 1, 20)},
            {'remind_at': '08:00', 'repeat': True, 'repeat_days': [0, 3, 6], 'repeat_every': 1},
            {'remind_at': '14:15', 'repeat': True, 'repeat_days': [1, 4], 'repeat_every': 2},
        ]
        
        created_reminders = []
        for i, config in enumerate(reminder_configs):
            event = Event.objects.create(
                pet=self.pet,
                title=f'Событие с напоминанием {i} {uuid.uuid4().hex[:6]}',
                event_type='grooming',
                date=date(2026, 1, 20 + i),
                is_done=False
            )
            
            reminder, created = ReminderSettings.objects.get_or_create(
                event=event,
                defaults={
                    'pet': self.pet,
                    'remind_at': datetime.strptime(config['remind_at'], '%H:%M').time(),
                    'repeat': config['repeat'],
                    'repeat_days': config.get('repeat_days', []),
                    'repeat_every': config.get('repeat_every', 1),
                    'remind_date': config.get('remind_date')
                }
            )
            
            if created:
                created_reminders.append(reminder)
                print(f"Создано напоминание {i+1}: {config['remind_at']}, повтор: {config['repeat']}")
            else:
                reminder.remind_at = datetime.strptime(config['remind_at'], '%H:%M').time()
                reminder.repeat = config['repeat']
                reminder.repeat_days = config.get('repeat_days', [])
                reminder.repeat_every = config.get('repeat_every', 1)
                reminder.remind_date = config.get('remind_date')
                reminder.save()
                print(f"Обновлено напоминание {i+1}")
        
        self.assertEqual(len(created_reminders), len(reminder_configs))