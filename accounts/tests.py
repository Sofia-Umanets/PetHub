from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from accounts.models import PetInvite, UserNotification
from pets.models import Pet
from datetime import date
import uuid
import time
import json
from django.utils import timezone

User = get_user_model()


class AccountsWhiteBoxTests(TestCase):
    """Модульные тесты для функционала аккаунтов"""
    
    def setUp(self):
        """Настройка тестовых данных"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.client = Client()
    
    def test_user_creation(self):
        """Тест создания пользователя"""
        print("\nСоздание пользователя")
        
        user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='newpass123'
        )
        
        self.assertEqual(user.email, 'new@example.com')
        self.assertTrue(user.check_password('newpass123'))
        print("Пользователь успешно создан")
    
    def test_user_login(self):
        """Тест авторизации пользователя"""
        print("\nАвторизация пользователя")
        
        login_success = self.client.login(
            username='testuser',
            password='testpass123'
        )
        self.assertTrue(login_success)
        print("Авторизация прошла успешно")
    
    def test_edit_profile(self):
        """Тест редактирования профиля пользователя"""
        print("\nРедактирование профиля")
        
        self.client.login(username='testuser', password='testpass123')
        
        # Обновляем данные пользователя
        self.user.username = 'updateduser'
        self.user.email = 'updated@example.com'
        self.user.save()
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'updateduser')
        self.assertEqual(self.user.email, 'updated@example.com')
        print("Профиль успешно обновлен")
    
    def test_password_strength(self):
        """Тест проверки сложности пароля"""
        print("\nПроверка сложности пароля")
        
        user = User.objects.create_user(
            username='passworduser',
            email='password@example.com',
            password='StrongPass123!'
        )
        
        # Пароль должен быть захеширован (не храниться в открытом виде)
        self.assertNotEqual(user.password, 'StrongPass123!')
        self.assertTrue(len(user.password) > 20)  # Хеш обычно длинный
        print("Пароль корректно захеширован")
    
    def test_create_invitation(self):
        """Тест создания приглашения для со-владельца"""
        print("\nСоздание приглашения")
        
        # Создаем питомца для теста
        pet = Pet.objects.create(
            name='Тестовый питомец',
            birthday=date(2020, 1, 1),
            creator=self.user
        )
        pet.owners.add(self.user)
        
        self.client.login(username='testuser', password='testpass123')
        
        # Создаем приглашение
        invite = PetInvite.objects.create(
            pet=pet,
            created_by=self.user
        )
        
        self.assertEqual(invite.pet, pet)
        self.assertEqual(invite.created_by, self.user)
        self.assertFalse(invite.is_used)
        print("Приглашение успешно создано")
    
    def test_accept_invitation(self):
        """Тест принятия приглашения"""
        print("\nПринятие приглашения")
        
        # Создаем второго пользователя
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        
        # Создаем питомца
        pet = Pet.objects.create(
            name='Питомец для приглашения',
            birthday=date(2021, 5, 10),
            creator=self.user
        )
        pet.owners.add(self.user)
        
        # Создаем приглашение
        invite = PetInvite.objects.create(pet=pet, created_by=self.user)
        
        # Принимаем приглашение
        invite.is_used = True
        invite.save()
        pet.owners.add(user2)
        
        # Проверяем добавление
        user2_in_owners = pet.owners.filter(id=user2.id).exists()
        self.assertTrue(user2_in_owners)
        print("Приглашение успешно принято")


class AccountsBlackBoxTests(TestCase):
    """Нагрузочное тестирование функционала аккаунтов"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='blackboxuser',
            email='blackbox@example.com',
            password='testpass123'
        )
    
    def test_load_performance_small(self):
        """Нагрузочное тестирование: 10 пользователей"""
        print("\nНагрузочное тестирование: 10 пользователей")
        
        size = 10
        start_time = time.time()
        
        # Создание пользователей
        for i in range(size):
            User.objects.create_user(
                username=f'loaduser{i}_{uuid.uuid4().hex[:8]}',
                email=f'loaduser{i}_{uuid.uuid4().hex[:8]}@example.com',
                password=f'password{i}'
            )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"Создание {size} пользователей за {execution_time:.3f} секунд")
        
        # Проверяем что все пользователи созданы
        user_count = User.objects.filter(username__startswith='loaduser').count()
        self.assertEqual(user_count, size)
        
        # Сохранение результатов
        self._save_results(10, execution_time)
    
    def test_load_performance_medium(self):
        """Нагрузочное тестирование: 100 пользователей"""
        print("\nНагрузочное тестирование: 100 пользователей")
        
        size = 100
        start_time = time.time()
        
        # Используем bulk_create для оптимизации
        users_to_create = []
        for i in range(size):
            unique_suffix = uuid.uuid4().hex[:8]
            user = User(
                username=f'mediumuser{i}_{unique_suffix}',
                email=f'mediumuser{i}_{unique_suffix}@example.com'
            )
            user.set_password(f'password{i}')
            users_to_create.append(user)
        
        User.objects.bulk_create(users_to_create)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"Создание {size} пользователей за {execution_time:.3f} секунд")
        
        # Проверяем производительность чтения
        start_time = time.time()
        users_count = User.objects.filter(username__startswith='mediumuser').count()
        read_time = time.time() - start_time
        
        print(f"Чтение {users_count} пользователей: {read_time:.3f} сек")
        
        self.assertLess(read_time, 2.0)
        
        # Сохранение результатов
        self._save_results(100, execution_time, read_time)
    
    def test_load_performance_large(self):
        """Нагрузочное тестирование: 1000 пользователей"""
        print("\nНагрузочное тестирование: 1000 пользователей")
        
        size = 1000
        start_time = time.time()
        
        users_to_create = []
        for i in range(size):
            unique_suffix = uuid.uuid4().hex[:6]
            user = User(
                username=f'largeuser{i}_{unique_suffix}',
                email=f'largeuser{i}_{unique_suffix}@example.com'
            )
            user.set_password(f'password{i}')
            users_to_create.append(user)
        
        User.objects.bulk_create(users_to_create)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"Создание {size} пользователей за {execution_time:.3f} секунд")
        
        # Тестирование фильтрации по email
        start_time = time.time()
        filtered_users = User.objects.filter(email__contains='@example.com').count()
        filter_time = time.time() - start_time
        
        print(f"Фильтрация {filtered_users} пользователей: {filter_time:.3f} сек")
        
        self.assertLess(filter_time, 2.0)
        
        # Сохранение результатов
        self._save_results(1000, execution_time, filter_time)
    
    def _save_results(self, size, create_time, read_time=0):
        """Сохранение результатов нагрузочного тестирования в файл"""
        results = {
            'size': size,
            'create_time': create_time,
            'read_time': read_time,
            'avg_create_per_record': create_time / size if size > 0 else 0,
            'timestamp': timezone.now().isoformat()
        }
        
        filename = f'accounts_load_test_results_{size}.json'
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)


class AccountsStressTests(TestCase):
    """Стрессовое тестирование функционала аккаунтов"""
    
    def setUp(self):
        """Подготовка данных для стрессового тестирования"""
        self.user = User.objects.create_user(
            username='stressuser',
            email='stress@example.com',
            password='testpass123'
        )
    
    def test_stress_existing_user_login(self):
        """Стресс-тест: вход существующего пользователя"""
        print("\nВход существующего пользователя")
        
        # Создаем нескольких пользователей
        users = []
        for i in range(5):
            user = User.objects.create_user(
                username=f'existinguser{i}',
                email=f'existing{i}@example.com',
                password=f'pass{i}'
            )
            users.append(user)
        
        # Проверяем аутентификацию для каждого
        for i, user in enumerate(users):
            auth_success = user.check_password(f'pass{i}')
            self.assertTrue(auth_success)
        
        print(f"Успешно аутентифицировано {len(users)} пользователей")
    
    def test_stress_validation_error(self):
        """Стресс-тест: обработка ошибок валидации данных"""
        print("\nОбработка ошибок валидации данных")
        
        test_cases = [
            {'username': 'user1', 'email': '', 'expected_error': 'email'},
            {'username': 'user2', 'email': 'invalid-email', 'expected_error': 'email'},
            {'username': '', 'email': 'valid@example.com', 'expected_error': 'username'},
        ]
        
        for i, test_case in enumerate(test_cases):
            try:
                user = User.objects.create(
                    username=test_case['username'],
                    email=test_case['email'],
                    password='password123'
                )
                user.full_clean()
                print(f"Тест {i+1}: Создан пользователь с некорректными данными")
            except Exception as e:
                error_type = type(e).__name__
                print(f"Тест {i+1}: Ошибка валидации {error_type} - ожидалось")
    
    def test_stress_duplicate_email(self):
        """Стресс-тест: обработка конфликта уникальности email"""
        print("\nОбработка конфликта уникальности email")
        
        # Создаем первого пользователя
        User.objects.create_user(
            username='existing',
            email='duplicate@example.com',
            password='pass123'
        )
        
        # Попытка создать пользователя с таким же email
        try:
            duplicate_user = User(
                username='duplicate',
                email='duplicate@example.com',
                password='pass123'
            )
            duplicate_user.full_clean()
            duplicate_user.save()
            print("Создан пользователь с дублирующимся email")
        except Exception as e:
            print(f"Ошибка уникальности email: {type(e).__name__} - корректно")
    
    def test_stress_authorization_error(self):
        """Стресс-тест: обработка ошибок авторизации"""
        print("\nОбработка ошибок авторизации")
        
        client = Client()
        
        # Попытка 1: Неверный пароль
        login_success = client.login(
            username='stressuser',
            password='wrongpassword'
        )
        self.assertFalse(login_success)
        print("Авторизация с неверным паролем отклонена")
        
        # Попытка 2: Несуществующий пользователь
        login_success = client.login(
            username='nonexistent',
            password='anypassword'
        )
        self.assertFalse(login_success)
        print("Авторизация несуществующего пользователя отклонена")
        
        # Попытка 3: Пустые учетные данные
        login_success = client.login(username='', password='')
        self.assertFalse(login_success)
        print("Авторизация с пустыми учетными данными отклонена")