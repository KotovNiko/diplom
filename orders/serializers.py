from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Order, OrderItem, ProductInfo, User


class RegisterSerializer(serializers.ModelSerializer):
    """Проверяет данные регистрации и создаёт неактивного пользователя."""
    # write_only: пароль принимаем, но никогда не отдаём обратно
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'first_name', 'last_name',
                  'company', 'position', 'type')
        # Имя и фамилия обязательны по спецификации API
        extra_kwargs = {
            'first_name': {'required': True, 'allow_blank': False},
            'last_name': {'required': True, 'allow_blank': False},
        }

    def validate_password(self, value):
        # Стандартные правила Django: длина, не слишком простой и т.д.
        validate_password(value)
        return value

    def create(self, validated_data):
        # create_user хеширует пароль; is_active=False до подтверждения почты
        return User.objects.create_user(is_active=False, **validated_data)


class ConfirmEmailSerializer(serializers.Serializer):
    """Данные для подтверждения почты: email и токен из письма."""
    email = serializers.EmailField()
    token = serializers.UUIDField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ProductInfoSerializer(serializers.ModelSerializer):
    """Товар в магазине в том виде, в котором его видит покупатель."""
    # source='product.name' берёт значение через связь: ProductInfo -> Product -> name
    name = serializers.CharField(source='product.name', read_only=True)
    description = serializers.CharField(source='product.description', read_only=True)
    category = serializers.CharField(source='product.category.name', read_only=True)
    shop = serializers.CharField(source='shop.name', read_only=True)
    parameters = serializers.SerializerMethodField()

    class Meta:
        model = ProductInfo
        fields = ('id', 'name', 'description', 'category', 'shop', 'model',
                  'price', 'price_rrc', 'quantity', 'parameters')

    def get_parameters(self, obj):
        # Характеристики в виде словаря {"Цвет": "чёрный", ...}.
        # Данные уже подгружены через prefetch_related во view, запросов в базу тут нет
        return {p.parameter.name: p.value for p in obj.parameters.all()}


class BasketItemInputSerializer(serializers.Serializer):
    """Входные данные: какой товар и сколько штук."""
    # В корзину можно положить только товар магазина, который принимает заказы.
    # PrimaryKeyRelatedField сам проверяет, что такой товар существует
    product_info = serializers.PrimaryKeyRelatedField(
        queryset=ProductInfo.objects.filter(shop__accepts_orders=True)
        .select_related('product', 'shop')
    )
    quantity = serializers.IntegerField(min_value=1)


class BasketItemSerializer(serializers.ModelSerializer):
    """Позиция корзины в ответе API."""
    shop = serializers.SerializerMethodField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product_info', 'name', 'shop', 'price', 'quantity', 'total')

    def get_shop(self, obj):
        # product_info может быть пустым, если товар позже удалили
        return obj.product_info.shop.name if obj.product_info else None


class BasketSerializer(serializers.ModelSerializer):
    """Корзина целиком: позиции и итоговая сумма."""
    items = BasketItemSerializer(many=True, read_only=True)
    total_sum = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'items', 'total_sum')