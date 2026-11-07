from django.conf import settings
from django.core.mail import send_mail

from collections import defaultdict
from orders.models import Order

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


def _send(subject, body, recipients):
    """Отправка письма. В режиме разработки текст ещё и печатается в консоль,
    потому что консольный backend выводит письма в закодированном виде."""
    if settings.DEBUG:
        print(f'[DEV] {subject} -> {recipients}\n{body}\n')
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)


def _contact_text(contact):
    """Адрес доставки одной строкой."""
    parts = [contact.city, f'ул. {contact.street}', f'д. {contact.house}']
    if contact.building:
        parts.append(f'корп. {contact.building}')
    if contact.structure:
        parts.append(f'стр. {contact.structure}')
    if contact.apartment:
        parts.append(f'кв. {contact.apartment}')
    return ', '.join(parts)


def send_order_emails(order_id):
    """Письмо клиенту с подтверждением и накладная администратору."""
    order = (Order.objects
             .select_related('user', 'contact')
             .prefetch_related('items__product_info__shop')
             .get(pk=order_id))
    contact = order.contact

    # Клиенту: что заказал и куда доставим
    lines = [f'{i.name} × {i.quantity} = {i.total} руб.' for i in order.items.all()]
    client_body = (
        f'Здравствуйте, {contact.first_name}!\n\n'
        f'Ваш заказ №{order.pk} принят.\n\n'
        + '\n'.join(lines)
        + f'\n\nИтого: {order.total_sum} руб.\n'
        f'Доставка: {_contact_text(contact)}\n'
    )
    _send(f'Заказ №{order.pk} принят', client_body, [order.user.email])

    # Администратору: накладная, позиции сгруппированы по поставщикам
    by_shop = defaultdict(list)
    for item in order.items.all():
        shop_name = item.product_info.shop.name if item.product_info else 'неизвестен'
        by_shop[shop_name].append(item)

    blocks = []
    for shop_name, items in by_shop.items():
        rows = '\n'.join(f'  {i.name} × {i.quantity} по {i.price} = {i.total}' for i in items)
        blocks.append(f'Поставщик: {shop_name}\n{rows}')

    admin_body = (
        f'Накладная по заказу №{order.pk}\n\n'
        f'Получатель: {contact.last_name} {contact.first_name} {contact.patronymic}\n'
        f'Телефон: {contact.phone}\n'
        f'Адрес: {_contact_text(contact)}\n\n'
        + '\n\n'.join(blocks)
        + f'\n\nИтого: {order.total_sum} руб.\n'
    )
    _send(f'Накладная по заказу №{order.pk}', admin_body, [settings.ADMIN_EMAIL])