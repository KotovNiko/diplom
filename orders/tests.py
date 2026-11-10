from decimal import Decimal

from django.core import mail
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import (
    Category, ConfirmEmailToken, Contact, Order, OrderItem, Product, ProductInfo, Shop, User,
)

PASSWORD = 'Str0ng-Pass-2026'


class BaseAPITestCase(APITestCase):
    """Общие данные: покупатель, поставщик с магазином, один товар, один адрес."""

    def setUp(self):
        self.buyer = User.objects.create_user(
            email='buyer@example.com', password=PASSWORD,
            first_name='Иван', last_name='Петров',
        )
        self.partner = User.objects.create_user(
            email='shop@example.com', password=PASSWORD, type='shop',
        )
        self.shop = Shop.objects.create(name='Тестовый магазин', user=self.partner)
        category = Category.objects.create(name='Смартфоны')
        category.shops.add(self.shop)
        product = Product.objects.create(name='Смартфон X', category=category)
        self.info = ProductInfo.objects.create(
            product=product, shop=self.shop, external_id=1, model='x',
            quantity=5, price=Decimal('1000'), price_rrc=Decimal('1200'),
        )
        self.contact = Contact.objects.create(
            user=self.buyer, last_name='Петров', first_name='Иван',
            email='buyer@example.com', phone='+79001234567',
            city='Москва', street='Ленина', house='10',
        )

    def auth(self, user):
        """Подставляет токен пользователя во все следующие запросы клиента."""
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')


class RegistrationTests(APITestCase):
    def test_register_confirm_login(self):
        data = {'email': 'new@example.com', 'password': PASSWORD,
                'first_name': 'Анна', 'last_name': 'Сидорова'}
        response = self.client.post('/api/v1/user/register', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Пользователь создан неактивным, письмо с токеном отправлено
        user = User.objects.get(email='new@example.com')
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)

        # До подтверждения войти нельзя
        login = {'email': 'new@example.com', 'password': PASSWORD}
        response = self.client.post('/api/v1/user/login', login, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # После подтверждения можно
        token = ConfirmEmailToken.objects.get(user=user)
        response = self.client.post(
            '/api/v1/user/register/confirm',
            {'email': 'new@example.com', 'token': str(token.key)}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post('/api/v1/user/login', login, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)


class BasketTests(BaseAPITestCase):
    def test_basket_requires_auth(self):
        response = self.client.get('/api/v1/basket')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_add_to_basket(self):
        self.auth(self.buyer)
        response = self.client.post(
            '/api/v1/basket', [{'product_info': self.info.id, 'quantity': 2}], format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrderItem.objects.get().quantity, 2)

    def test_cannot_add_more_than_in_stock(self):
        self.auth(self.buyer)
        response = self.client.post(
            '/api/v1/basket', [{'product_info': self.info.id, 'quantity': 6}], format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrderItem.objects.count(), 0)


class OrderTests(BaseAPITestCase):
    def test_confirm_order(self):
        self.auth(self.buyer)
        self.client.post(
            '/api/v1/basket', [{'product_info': self.info.id, 'quantity': 2}], format='json',
        )
        basket = Order.objects.get(user=self.buyer, state='basket')

        # Письма отправляются после коммита транзакции; в тестах колбэки
        # коммита нужно выполнить явно
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/api/v1/order', {'id': basket.id, 'contact': self.contact.id}, format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Остаток списан, статус сменился, клиенту и администратору ушли письма
        self.info.refresh_from_db()
        self.assertEqual(self.info.quantity, 3)
        basket.refresh_from_db()
        self.assertEqual(basket.state, 'new')
        self.assertEqual(len(mail.outbox), 2)

        # Цена зафиксирована: изменение прайса не меняет сумму заказа
        self.info.price = Decimal('2000')
        self.info.save()
        self.assertEqual(basket.total_sum, Decimal('2000'))

        # Повторно подтвердить тот же заказ нельзя
        response = self.client.post(
            '/api/v1/order', {'id': basket.id, 'contact': self.contact.id}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PartnerTests(BaseAPITestCase):
    def test_buyer_cannot_use_partner_api(self):
        self.auth(self.buyer)
        response = self.client.get('/api/v1/partner/state')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_order_state_transitions(self):
        order = Order.objects.create(user=self.buyer, state='new', contact=self.contact)
        OrderItem.objects.create(
            order=order, product_info=self.info, quantity=1,
            price=Decimal('1000'), name='Смартфон X',
        )
        self.auth(self.partner)
        url = f'/api/v1/partner/orders/{order.id}'

        # Перескочить через стадии нельзя
        response = self.client.patch(url, {'state': 'delivered'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Допустимый переход работает
        response = self.client.patch(url, {'state': 'confirmed'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.state, 'confirmed')