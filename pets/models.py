import uuid
from django.db import models
from django.contrib.auth import get_user_model
from datetime import date

User = get_user_model()

class Pet(models.Model):
    GENDER_CHOICES = [
        ('M', 'Мальчик'),
        ('F', 'Девочка'),
    ]
    
    PET_TYPE_CHOICES = [
        ('dog', '🐶 Собака'),
        ('cat', '🐱 Кошка'),
        ('bird', '🐦 Птица'),
        ('rodent', '🐹 Грызун'),
        ('rabbit', '🐰 Кролик'),
        ('reptile', '🐍 Рептилия'),
        ('fish', '🐠 Рыбка'),
        ('other', '❓ Другое (указать)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    pet_type = models.CharField(
        max_length=20, 
        choices=PET_TYPE_CHOICES, 
        default='dog',
        verbose_name='Тип животного'
    )
    custom_pet_type = models.CharField(
        max_length=100, 
        verbose_name='Свой вариант', 
        blank=True, 
        null=True,
        help_text='Укажите, если выбрали "Другое"'
    )
    birthday = models.DateField(null=True, blank=False)
    owners = models.ManyToManyField(User, related_name='pets')
    photo = models.ImageField(upload_to='pet_photos/', blank=True, null=True)
    breed = models.CharField(max_length=100, verbose_name='Порода', blank=True, null=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Вес (кг)', blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, verbose_name='Пол', blank=True, null=True)
    features = models.TextField(
        verbose_name='Особенности', 
        blank=True, 
        null=True, 
        help_text='Аллергии, хронические заболевания и другие особенности питомца'
    )

    def __str__(self):
        return self.name
    
    @property
    def display_pet_type(self):
        """Отображает тип животного с учетом кастомного варианта"""
        if self.pet_type == 'other' and self.custom_pet_type:
            return self.custom_pet_type
        return self.get_pet_type_display().replace('❓ ', '') 
    
    @property
    def age(self):
        if not self.birthday:
            return None
        today = date.today()
        years = today.year - self.birthday.year
        months = today.month - self.birthday.month
        days = today.day - self.birthday.day

        if days < 0:
            months -= 1
        if months < 0:
            years -= 1
            months += 12

        if years == 0:
            return f"{months} мес."
        elif months == 0:
            return f"{years} г."
        else:
            return f"{years} г. {months} мес."
    
    def is_owner(self, user):
        """Проверяет, является ли пользователь владельцем питомца"""
        return self.owners.filter(id=user.id).exists()
    
    def can_edit(self, user):
        """Проверяет, может ли пользователь редактировать питомца"""
        return self.is_owner(user)
