from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConfirmEmailToken, User
from .serializers import ConfirmEmailSerializer, LoginSerializer, RegisterSerializer
from .services.emails import send_confirmation_email


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