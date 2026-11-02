from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


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