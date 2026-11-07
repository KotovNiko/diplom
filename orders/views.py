from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from .serializers import (
    ConfirmEmailSerializer,
    LoginSerializer,
    RegisterSerializer,
    ProductInfoSerializer,
    BasketItemInputSerializer,
    BasketSerializer,
    ContactSerializer,
    OrderDetailSerializer, OrderConfirmSerializer, OrderListSerializer,
)
from .services.emails import send_confirmation_email
from .filters import ProductInfoFilter
from .models import ConfirmEmailToken, Order, OrderItem, ProductInfo, Contact
from .services.orders import OrderError, confirm_order


class RegisterView(APIView):
    """POST /api/v1/user/register: регистрация нового пользователя."""

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        # raise_exception: при ошибке DRF сам вернёт 400 с описанием проблем
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = ConfirmEmailToken.objects.create(user=user)
        send_confirmation_email(user, token)
        return Response(
            {'detail': 'Регистрация принята. Проверьте почту и подтвердите email.'},
            status=status.HTTP_201_CREATED,
        )


class ConfirmEmailView(APIView):
    """POST /api/v1/user/register/confirm: активирует пользователя по токену."""

    def post(self, request):
        serializer = ConfirmEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Ищем токен, который принадлежит именно этому email
        token = ConfirmEmailToken.objects.filter(
            key=data['token'], user__email__iexact=data['email']
        ).select_related('user').first()
        if token is None:
            return Response({'detail': 'Неверный токен или email.'},
                            status=status.HTTP_400_BAD_REQUEST)

        token.user.is_active = True
        token.user.save(update_fields=['is_active'])
        token.delete()  # токен одноразовый
        return Response({'detail': 'Email подтверждён. Теперь можно войти.'})


class LoginView(APIView):
    """POST /api/v1/user/login: проверка email и пароля, выдача токена."""

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # authenticate вернёт None при неверных данных и для неактивных пользователей
        user = authenticate(request, email=data['email'], password=data['password'])
        if user is None:
            return Response(
                {'detail': 'Неверный email или пароль, либо email не подтверждён.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key})


def catalog_queryset():
    """Товары магазинов, которые принимают заказы, с заранее подгруженными связями."""
    return (
        ProductInfo.objects
        .filter(shop__accepts_orders=True)
        # select_related: связи «к одному» подтягиваются тем же запросом (JOIN)
        .select_related('product__category', 'shop')
        # prefetch_related: характеристики подтягиваются одним дополнительным запросом
        .prefetch_related('parameters__parameter')
        .order_by('id')
    )


class ProductListView(ListAPIView):
    """GET /api/v1/products: список товаров с фильтрами, поиском и сортировкой."""
    queryset = catalog_queryset()
    serializer_class = ProductInfoSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductInfoFilter
    search_fields = ['product__name', 'model', 'product__description']  # ?search=iphone
    ordering_fields = ['price', 'quantity']                             # ?ordering=-price


class ProductDetailView(RetrieveAPIView):
    """GET /api/v1/products/<id>: полная информация об одном товаре."""
    queryset = catalog_queryset()
    serializer_class = ProductInfoSerializer


class BasketView(APIView):
    """Корзина текущего пользователя."""
    permission_classes = [IsAuthenticated]  # без токена будет 401

    def _basket(self, user):
        # Корзина одна на пользователя: берём существующую или создаём
        basket, _ = Order.objects.get_or_create(user=user, state='basket')
        return basket

    def _response(self, basket, status_code=status.HTTP_200_OK):
        # Перечитываем корзину с позициями, чтобы ответ отражал свежие данные
        basket = (Order.objects
                  .prefetch_related('items__product_info__shop')
                  .get(pk=basket.pk))
        return Response(BasketSerializer(basket).data, status=status_code)

    @staticmethod
    def _check_stock(info, quantity):
        # Нельзя положить больше, чем есть на складе поставщика
        if quantity > info.quantity:
            raise ValidationError(
                {'detail': f'Товара «{info.product.name}» в наличии только {info.quantity}.'}
            )

    def get(self, request):
        return self._response(self._basket(request.user))

    def post(self, request):
        """Тело запроса: список [{"product_info": 1, "quantity": 2}, ...]."""
        serializer = BasketItemInputSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        basket = self._basket(request.user)

        # atomic: если на одной из позиций случится ошибка, не добавится ни одна
        with transaction.atomic():
            for data in serializer.validated_data:
                info = data['product_info']
                item, _ = OrderItem.objects.get_or_create(
                    order=basket, product_info=info,
                    defaults={'quantity': 0, 'price': info.price,
                              'name': info.product.name},
                )
                item.quantity += data['quantity']
                self._check_stock(info, item.quantity)
                item.save()
        return self._response(basket, status.HTTP_201_CREATED)

    def put(self, request):
        """Меняет количество уже добавленных позиций на указанное."""
        serializer = BasketItemInputSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        basket = self._basket(request.user)

        with transaction.atomic():
            for data in serializer.validated_data:
                info = data['product_info']
                item = basket.items.filter(product_info=info).first()
                if item is None:
                    raise ValidationError({'detail': f'«{info.product.name}» нет в корзине.'})
                self._check_stock(info, data['quantity'])
                item.quantity = data['quantity']
                item.save()
        return self._response(basket)


class BasketItemView(APIView):
    """DELETE /api/v1/basket/<id позиции>: удаляет позицию из корзины."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        # Фильтр по order__user обязателен: иначе можно было бы удалить
        # позицию из чужой корзины, угадав её номер
        deleted, _ = OrderItem.objects.filter(
            pk=item_id, order__user=request.user, order__state='basket'
        ).delete()
        if not deleted:
            return Response({'detail': 'Позиция не найдена.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactListCreateView(ListCreateAPIView):
    """GET: мои контакты. POST: добавить контакт."""
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # контактов мало, постраничный вывод не нужен

    def get_queryset(self):
        # Только контакты текущего пользователя
        return Contact.objects.filter(user=self.request.user).order_by('id')

    def perform_create(self, serializer):
        # Владелец берётся из токена, а не из тела запроса
        serializer.save(user=self.request.user)


class ContactDetailView(RetrieveUpdateDestroyAPIView):
    """GET, PUT, PATCH, DELETE одного моего контакта."""
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Чужой контакт в этот набор не попадает, поэтому вернётся 404
        return Contact.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            # Order.contact защищён: нельзя удалить адрес, использованный в заказе
            return Response(
                {'detail': 'Контакт используется в заказах и не может быть удалён.'},
                status=status.HTTP_409_CONFLICT,
            )


def user_orders(user):
    """Оформленные заказы пользователя (корзина в историю не входит)."""
    return (Order.objects
            .filter(user=user)
            .exclude(state='basket')
            .select_related('contact')
            .prefetch_related('items__product_info__shop'))


class OrderListCreateView(APIView):
    """GET: история заказов. POST: подтверждение заказа."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = user_orders(request.user)
        return Response(OrderListSerializer(orders, many=True).data)

    def post(self, request):
        serializer = OrderConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Корзина и контакт должны принадлежать этому пользователю, иначе 404
        basket = get_object_or_404(Order, pk=data['id'], user=request.user)
        contact = get_object_or_404(Contact, pk=data['contact'], user=request.user)
        try:
            confirm_order(basket, contact)
        except OrderError as error:
            return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)

        order = user_orders(request.user).get(pk=basket.pk)
        return Response(OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(RetrieveAPIView):
    """GET /api/v1/order/<id>: детали заказа."""
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return user_orders(self.request.user)