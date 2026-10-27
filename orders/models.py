from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Менеджер: создаёт пользователей по email вместо username."""
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        # normalize_email приводит домен к нижнему регистру
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)  # пароль хранится хешем, не открытым текстом
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Пользователь сервиса: покупатель или поставщик."""
    USER_TYPES = (
        ('shop', 'Поставщик'),
        ('buyer', 'Покупатель'),
    )

    username = None  # убираем стандартное поле username
    email = models.EmailField('Email', unique=True)
    company = models.CharField('Компания', max_length=60, blank=True)
    position = models.CharField('Должность', max_length=60, blank=True)
    type = models.CharField('Тип', max_length=5, choices=USER_TYPES, default='buyer')

    USERNAME_FIELD = 'email'   # по этому полю происходит вход
    REQUIRED_FIELDS = []       # createsuperuser спросит только email и пароль

    objects = UserManager()

    def __str__(self):
        return self.email