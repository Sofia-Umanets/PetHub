from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid
import os
from django.templatetags.static import static

class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ImageField(
        verbose_name='Аватар',
        upload_to="profile/avatars/",
        null=True,
        blank=True
    )
    email = models.EmailField('Email', unique=True)
    phone = models.CharField('Телефон', max_length=20, blank=True, null=True)
    birth_date = models.DateField('Дата рождения', null=True, blank=True)
    bio = models.TextField('О себе', max_length=500, blank=True)

    def clean(self):
        super().clean()
        if self.birth_date and self.birth_date > timezone.now().date():
            raise ValidationError({'birth_date': 'Дата рождения не может быть в будущем'})

    def get_age(self):
        if self.birth_date:
            today = timezone.now().date()
            age = today.year - self.birth_date.year
            if today.month < self.birth_date.month or (
                today.month == self.birth_date.month and 
                today.day < self.birth_date.day
            ):
                age -= 1
            return age
        return None

    def get_avatar(self):
        try:
            if self.avatar and os.path.exists(self.avatar.path):
                return self.avatar.url
        except:
            pass
        return static('img/image.webp')

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'



class PetInvite(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    pet = models.ForeignKey('pets.Pet', on_delete=models.CASCADE)
    created_by = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"Приглашение к {self.pet.name}"
    


class UserNotification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Уведомление для {self.user.username}"
