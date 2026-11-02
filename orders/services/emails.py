from django.conf import settings
from django.core.mail import send_mail


def send_confirmation_email(user, token):
    """Отправляет пользователю письмо с токеном подтверждения регистрации."""
    send_mail(
        subject='Подтверждение регистрации',
        message=(
            f'Здравствуйте, {user.first_name or user.email}!\n\n'
            f'Ваш токен подтверждения: {token.key}\n\n'
            'Отправьте его на /api/v1/user/register/confirm вместе с вашим email.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )