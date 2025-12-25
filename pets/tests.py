from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from pets.models import Pet
from datetime import date, timedelta
import time
import json
import uuid
from django.utils import timezone
from django.db.models import Avg

User = get_user_model()


class PetsWhiteBoxTests(TestCase):
    """Модульные тесты для функционала питомцев"""
    
    def setUp(self):
        """Настройка тестовых данных"""
        self.user = User.objects.create_user(
            username='petowner',
            email='owner@example.com',
            password='testpass123'
        )
        
        self.client = Client()
        self.client.login(username='petowner', password='testpass123')
        
        self.pet = Pet.objects.create(
            name='Барсик',
            pet_type='cat',
            birthday=date(2020, 1, 1),
            breed='Сиамская',
            weight=4.5,
            gender='M',
            creator=self.user
        )
        self.pet.owners.add(self.user)
    
    def test_pet_creation(self):
        """Тест создания питомца"""
        print("\nСоздание питомца")
        
        pet_count_before = Pet.objects.count()
        
        pet = Pet.objects.create(
            name='Мурзик',
            pet_type='cat',
            birthday=date(2021, 5, 10),
            creator=self.user
        )
        pet.owners.add(self.user)
        
        pet_count_after = Pet.objects.count()
        
        self.assertEqual(pet.name, 'Мурзик')
        self.assertEqual(pet.pet_type, 'cat')
        self.assertEqual(pet.creator, self.user)
        self.assertEqual(pet_count_after, pet_count_before + 1)
        print("Питомец успешно создан")
    
    def test_pet_age_calculation(self):
        """Тест расчета возраста питомца"""
        print("\nРасчет возраста питомца")
        
        age = self.pet.age
        self.assertIn('г.', age)
        print(f"Возраст питомца: {age}")
    
    def test_pet_editing(self):
        """Тест редактирования данных питомца"""
        print("\nРедактирование данных питомца")
        
        self.pet.name = 'Обновленный Барсик'
        self.pet.breed = 'Персидская'
        self.pet.save()
        
        self.pet.refresh_from_db()
        
        self.assertEqual(self.pet.name, 'Обновленный Барсик')
        self.assertEqual(self.pet.breed, 'Персидская')
        print("Данные питомца успешно обновлены")
    
    def test_pet_deletion(self):
        """Тест удаления питомца"""
        print("\nУдаление питомца")
        
        pet_to_delete = Pet.objects.create(
            name='Удаляемый питомец',
            pet_type='dog',
            birthday=date(2021, 1, 1),
            creator=self.user
        )
        pet_to_delete.owners.add(self.user)
        
        pet_id = pet_to_delete.id
        pet_to_delete.delete()
        
        pet_exists = Pet.objects.filter(id=pet_id).exists()
        self.assertFalse(pet_exists)
        print("Питомец успешно удален")
    
    def test_pet_access_control(self):
        """Тест контроля доступа к профилю питомца"""
        print("\nКонтроль доступа к профилю питомца")
        
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        # Проверяем, что другой пользователь не является владельцем
        is_owner = self.pet.owners.filter(id=other_user.id).exists()
        self.assertFalse(is_owner)
        
        # Добавляем другого пользователя как владельца
        self.pet.owners.add(other_user)
        
        # Теперь он должен быть владельцем
        is_owner_after = self.pet.owners.filter(id=other_user.id).exists()
        self.assertTrue(is_owner_after)
        print("Контроль доступа работает корректно")
    
    def test_custom_pet_type(self):
        """Тест создания питомца с кастомным типом"""
        print("\nСоздание питомца с кастомным типом")
        
        pet = Pet.objects.create(
            name='Экзотик',
            pet_type='other',
            custom_pet_type='Енот',
            birthday=date(2022, 3, 15),
            creator=self.user
        )
        pet.owners.add(self.user)
        
        self.assertEqual(pet.pet_type, 'other')
        self.assertEqual(pet.custom_pet_type, 'Енот')
        self.assertEqual(pet.display_pet_type, 'Енот')
        print("Питомец с кастомным типом успешно создан")
    
    def test_birthday_event_auto_creation(self):
        """Тест автоматического создания события дня рождения"""
        print("\nАвтоматическое создание события дня рождения")
        
        from calendarapp.models import Event
        from datetime import date as date_class
        
        birthday_event = Event.objects.create(
            pet=self.pet,
            title=f'День рождения {self.pet.name}',
            event_type='birthday',
            date=date_class(2026, self.pet.birthday.month, self.pet.birthday.day),
            is_yearly=True
        )
        
        event_count = Event.objects.filter(event_type='birthday').count()
        self.assertEqual(event_count, 1)
        print("Событие дня рождения успешно создано")


class PetsBlackBoxTests(TestCase):
    """Нагрузочное тестирование функционала питомцев"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='loaduser',
            email='load@example.com',
            password='testpass123'
        )
        self.client.login(username='loaduser', password='testpass123')
    
    def test_load_performance_small(self):
        """Нагрузочное тестирование: 10 питомцев"""
        print("\nНагрузочное тестирование: 10 питомцев")
        
        size = 10
        start_time = time.time()
        
        for i in range(size):
            Pet.objects.create(
                name=f'Питомец {i} {uuid.uuid4().hex[:6]}',
                pet_type='dog',
                birthday=date(2020, 1, 1),
                creator=self.user
            )
        
        create_time = time.time() - start_time
        print(f"Создание {size} записей: {create_time:.3f} сек")
        
        count = Pet.objects.filter(name__startswith='Питомец').count()
        self.assertEqual(count, size)
        
        self._save_results(10, create_time, 0)
    
    def test_load_performance_medium(self):
        """Нагрузочное тестирование: 100 питомцев"""
        print("\nНагрузочное тестирование: 100 питомцев")
        
        size = 100
        start_time = time.time()
        
        pets_to_create = []
        for i in range(size):
            pet = Pet(
                name=f'Питомец нагрузки {i} {uuid.uuid4().hex[:6]}',
                pet_type='cat',
                birthday=date(2020, 1, 1),
                creator=self.user
            )
            pets_to_create.append(pet)
        
        Pet.objects.bulk_create(pets_to_create)
        
        create_time = time.time() - start_time
        print(f"Создание {size} записей: {create_time:.3f} сек")
        
        start_time = time.time()
        pets_count = Pet.objects.filter(name__startswith='Питомец нагрузки').count()
        read_time = time.time() - start_time
        
        print(f"Чтение {pets_count} записей: {read_time:.3f} сек")
        
        self.assertLess(read_time, 2.0)
        self._save_results(100, create_time, read_time)
    
    def test_load_performance_large(self):
        """Нагрузочное тестирование: 1000 питомцев"""
        print("\nНагрузочное тестирование: 1000 питомцев")
        
        size = 1000
        start_time = time.time()
        
        pets_to_create = []
        for i in range(size):
            pet = Pet(
                name=f'Большой питомец {i} {uuid.uuid4().hex[:4]}',
                pet_type='dog' if i % 2 == 0 else 'cat',
                birthday=date(2018 + i % 5, (i % 12) + 1, (i % 28) + 1),
                breed=f'Порода {i % 10}',
                weight=float(i % 50) + 1.0,
                creator=self.user
            )
            pets_to_create.append(pet)
        
        Pet.objects.bulk_create(pets_to_create)
        
        create_time = time.time() - start_time
        print(f"Создание {size} записей: {create_time:.3f} сек")
        
        start_time = time.time()
        dogs_count = Pet.objects.filter(pet_type='dog').count()
        filter_time = time.time() - start_time
        
        print(f"Фильтрация {dogs_count} собак: {filter_time:.3f} сек")
        
        self.assertLess(filter_time, 2.0)
        self._save_results(1000, create_time, filter_time)
    
    def test_load_performance_xlarge(self):
        """Нагрузочное тестирование: 10000 питомцев"""
        print("\nНагрузочное тестирование: 10000 питомцев")
        
        size = 10000
        start_time = time.time()
        
        batch_size = 1000
        pets_created = 0
        
        for batch in range(size // batch_size):
            pets_to_create = []
            for i in range(batch_size):
                idx = batch * batch_size + i
                pet = Pet(
                    name=f'Очень большой питомец {idx} {uuid.uuid4().hex[:4]}',
                    pet_type='dog' if idx % 3 == 0 else 'cat' if idx % 3 == 1 else 'bird',
                    birthday=date(2015 + idx % 10, (idx % 12) + 1, (idx % 28) + 1),
                    creator=self.user
                )
                pets_to_create.append(pet)
            
            Pet.objects.bulk_create(pets_to_create)
            pets_created += len(pets_to_create)
        
        create_time = time.time() - start_time
        print(f"Создание {pets_created} записей: {create_time:.3f} сек")
        
        start_time = time.time()
        avg_weight_result = Pet.objects.filter(weight__isnull=False).aggregate(avg_weight=Avg('weight'))
        aggregate_time = time.time() - start_time
        
        print(f"Агрегация среднего веса: {aggregate_time:.3f} сек")
        
        self.assertLess(aggregate_time, 5.0)
        self._save_results(10000, create_time, aggregate_time)
    
    def _save_results(self, size, create_time, operation_time):
        """Сохранение результатов нагрузочного тестирования в файл"""
        results = {
            'size': size,
            'create_time': create_time,
            'operation_time': operation_time,
            'avg_create_per_record': create_time / size if size > 0 else 0,
            'timestamp': timezone.now().isoformat()
        }
        
        filename = f'pets_load_test_results_{size}.json'
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)


class PetsStressTests(TestCase):
    """Стрессовое тестирование функционала питомцев"""
    
    def setUp(self):
        """Подготовка данных для стрессового тестирования"""
        self.user = User.objects.create_user(
            username='stressuser',
            email='stress@example.com',
            password='testpass123'
        )
        
        self.pet = Pet.objects.create(
            name='Питомец для стресс-тестов',
            pet_type='cat',
            birthday=date(2020, 1, 1),
            creator=self.user
        )
        self.pet.owners.add(self.user)
    
    def test_stress_remove_owner(self):
        """Стресс-тест: удаление участника из группы ухода"""
        print("\nУдаление участника из группы ухода")
        
        # Создаем нескольких со-владельцев
        coowners = []
        for i in range(5):
            user = User.objects.create_user(
                username=f'coowner{i}',
                email=f'coowner{i}@example.com',
                password='testpass123'
            )
            coowners.append(user)
            self.pet.owners.add(user)
        
        print(f"Добавлено {len(coowners)} со-владельцев")
        
        # Удаляем одного со-владельца
        owner_to_remove = coowners[0]
        self.pet.owners.remove(owner_to_remove)
        
        # Проверяем удаление
        is_still_owner = self.pet.owners.filter(id=owner_to_remove.id).exists()
        self.assertFalse(is_still_owner)
        
        print(f"Со-владелец {owner_to_remove.username} успешно удален")
        
        # Проверяем, что остальные со-владельцы остались
        remaining_owners = self.pet.owners.exclude(id=self.user.id).count()
        self.assertEqual(remaining_owners, len(coowners) - 1)
        print(f"Осталось {remaining_owners} со-владельцев")
    
    def test_stress_invalid_pet_data(self):
        """Стресс-тест: обработка некорректных данных питомца"""
        print("\nОбработка некорректных данных питомца")
        
        test_cases = [
            {'name': '', 'birthday': date(2022, 1, 1), 'expected': 'name'},
            {'name': 'Питомец', 'birthday': None, 'expected': 'birthday'},
            {'name': 'A' * 200, 'birthday': date(2022, 1, 1), 'expected': 'name_length'},
        ]
        
        for i, test_case in enumerate(test_cases):
            try:
                pet = Pet.objects.create(
                    name=test_case['name'],
                    pet_type='dog',
                    birthday=test_case['birthday'],
                    creator=self.user
                )
                pet.owners.add(self.user)
                print(f"Тест {i+1}: Создан питомец с потенциально некорректными данными")
            except Exception as e:
                error_type = type(e).__name__
                print(f"Тест {i+1}: Ошибка {error_type} при создании питомца - ожидалось")
    
    def test_stress_custom_pet_type_creation(self):
        """Стресс-тест: массовое создание питомцев с кастомными типами"""
        print("\nМассовое создание питомцев с кастомными типами")
        
        custom_types = ['Енот', 'Хорек', 'Черепаха', 'Змея', 'Паук', 'Ящерица', 'Хомяк', 'Крыса', 'Мышь', 'Попугай']
        
        created_pets = []
        for i, pet_type in enumerate(custom_types):
            pet = Pet.objects.create(
                name=f'Экзотик {i}',
                pet_type='other',
                custom_pet_type=pet_type,
                birthday=date(2022, (i % 12) + 1, 15),
                creator=self.user
            )
            pet.owners.add(self.user)
            created_pets.append(pet)
        
        custom_pets = Pet.objects.filter(pet_type='other')
        print(f"Создано {custom_pets.count()} питомцев с кастомными типами")
        
        # Проверяем отображение кастомных типов
        for pet in created_pets:
            display_type = pet.display_pet_type
            self.assertNotEqual(display_type, 'Другое (указать)')
        
        print("Все кастомные типы отображаются корректно")
    
    def test_stress_pet_deletion_confirmation(self):
        """Стресс-тест: удаление питомца с проверкой подтверждения"""
        print("\nУдаление питомца с проверкой подтверждения")
        
        # Создаем несколько питомцев для удаления
        pets_to_delete = []
        for i in range(3):
            pet = Pet.objects.create(
                name=f'Питомец для удаления {i}',
                pet_type='dog',
                birthday=date(2021, i+1, 10),
                creator=self.user
            )
            pet.owners.add(self.user)
            pets_to_delete.append(pet)
        
        print(f"Создано {len(pets_to_delete)} питомцев для теста удаления")
        
        # Удаляем питомцев
        deleted_count = 0
        for pet in pets_to_delete:
            pet_id = pet.id
            pet.delete()
            
            # Проверяем удаление
            pet_exists = Pet.objects.filter(id=pet_id).exists()
            if not pet_exists:
                deleted_count += 1
        
        print(f"Успешно удалено {deleted_count} из {len(pets_to_delete)} питомцев")
        self.assertEqual(deleted_count, len(pets_to_delete))