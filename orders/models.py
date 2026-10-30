import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q

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

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('email',)

    def __str__(self):
        return self.email


class Shop(models.Model):
    name = models.CharField('Название', max_length=50, unique=True)
    url = models.URLField('Ссылка на прайс', blank=True, null=True)
    user = models.OneToOneField(User, verbose_name='Владелец',
                                on_delete=models.PROTECT, null=True, blank=True)
    accepts_orders = models.BooleanField('Приём заказов', default=True)

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Магазины'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField('Название', max_length=60)
    shops = models.ManyToManyField(Shop, verbose_name='Магазины',
                                   related_name='categories', blank=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField('Название', max_length=100)
    description = models.TextField('Описание', blank=True)
    category = models.ForeignKey(Category, verbose_name='Категория',
                                 related_name='products', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ('name',)

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    product = models.ForeignKey(Product, verbose_name='Товар',
                                related_name='infos', on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, verbose_name='Магазин',
                             related_name='infos', on_delete=models.PROTECT)
    external_id = models.PositiveIntegerField('Внешний ID')
    model = models.CharField('Модель', max_length=100, blank=True)
    quantity = models.PositiveIntegerField('Количество')
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)
    price_rrc = models.DecimalField('Рекомендуемая розничная цена',
                                    max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Информация о товаре'
        verbose_name_plural = 'Информация о товарах'
        constraints = [
            models.UniqueConstraint(fields=['product', 'shop', 'external_id'],
                                    name='unique_product_info'),
        ]

    def clean(self):
        super().clean()
        if not self.product_id or not self.shop_id:
            return
        category = self.product.category  # прямая связь вместо лишнего запроса
        # Пустой список магазинов у категории означает «разрешено всем»
        if category.shops.exists() and not category.shops.filter(pk=self.shop_id).exists():
            raise ValidationError({'shop': 'Магазин не продаёт товары этой категории'})

    def __str__(self):
        suffix = f' [{self.model}]' if self.model else ''
        return f'{self.product}{suffix} ({self.shop})'


class Parameter(models.Model):
    name = models.CharField('Название', max_length=60, unique=True)

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = 'Параметры'

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, verbose_name='Товар в магазине',
                                     related_name='parameters', on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameter, verbose_name='Параметр',
                                  on_delete=models.CASCADE)
    value = models.CharField('Значение', max_length=100)

    class Meta:
        verbose_name = 'Параметр товара'
        verbose_name_plural = 'Параметры товаров'
        constraints = [
            models.UniqueConstraint(fields=['product_info', 'parameter'],
                                    name='unique_product_parameter'),
        ]

    def __str__(self):
        return f'{self.parameter}: {self.value}'


class Contact(models.Model):
    user = models.ForeignKey(User, verbose_name='Пользователь',
                             related_name='contacts', on_delete=models.CASCADE)
    last_name = models.CharField('Фамилия', max_length=50)
    first_name = models.CharField('Имя', max_length=50)
    patronymic = models.CharField('Отчество', max_length=50, blank=True)
    email = models.EmailField('Email')
    phone = models.CharField('Телефон', max_length=20)
    city = models.CharField('Город', max_length=50)
    street = models.CharField('Улица', max_length=100)
    house = models.CharField('Дом', max_length=15)
    building = models.CharField('Корпус', max_length=15, blank=True)
    structure = models.CharField('Строение', max_length=15, blank=True)
    apartment = models.CharField('Квартира', max_length=15, blank=True)

    class Meta:
        verbose_name = 'Контакт'
        verbose_name_plural = 'Контакты'

    def __str__(self):
        return f'{self.last_name} {self.first_name}, {self.city}, {self.street}, {self.house}'


class Order(models.Model):
    STATES = (
        ('basket', 'Корзина'),
        ('new', 'Новый'),
        ('confirmed', 'Подтверждён'),
        ('assembled', 'Собран'),
        ('sent', 'Отправлен'),
        ('delivered', 'Доставлен'),
        ('canceled', 'Отменён'),
    )
    user = models.ForeignKey(User, verbose_name='Пользователь',
                             related_name='orders', on_delete=models.PROTECT)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True, db_index=True)
    state = models.CharField('Статус', max_length=15, choices=STATES, default='basket', db_index=True)
    contact = models.ForeignKey(Contact, verbose_name='Контакт',
                                null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['user'], condition=Q(state='basket'),
                name='one_basket_per_user',
            ),
        ]
    @property
    def total_sum(self):
        return sum((i.total for i in self.items.all()), Decimal('0'))

    def __str__(self):
        local = timezone.localtime(self.created_at)
        return f'Заказ №{self.pk} от {local:%d.%m.%Y}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, verbose_name='Заказ',
                              related_name='items', on_delete=models.CASCADE)
    product_info = models.ForeignKey(ProductInfo, related_name='order_items', verbose_name='Товар в магазине',
                                     on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField('Количество', validators=[MinValueValidator(1)])
    price = models.DecimalField('Цена на момент заказа', max_digits=10, decimal_places=2)
    # снимок названия, чтобы отображать даже если ProductInfo удалят
    name = models.CharField('Название на момент заказа', max_length=100, blank=True)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'
        constraints = [
            models.UniqueConstraint(fields=['order', 'product_info'],
                                    name='unique_order_item'),
        ]

    def save(self, *args, **kwargs):
        # Снимок названия: заполняем один раз, если не задан
        if self.product_info_id and not self.name:
            self.name = self.product_info.product.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name or self.product_info} × {self.quantity}'

    @property
    def total(self):
        return self.quantity * self.price


class ConfirmEmailToken(models.Model):
    user = models.ForeignKey(User, verbose_name='Пользователь', on_delete=models.CASCADE)
    key = models.UUIDField('Токен', default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Токен подтверждения'
        verbose_name_plural = 'Токены подтверждения'

    def __str__(self):
        return f'{self.user.email} — {self.key}'