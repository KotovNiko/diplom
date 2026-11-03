from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import ProductInfo, User


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