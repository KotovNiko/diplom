from django.db import transaction
from django.db.models import F

from orders.models import ProductInfo
from orders.services.emails import send_order_emails


class OrderError(Exception):
    """Заказ нельзя подтвердить (пустая корзина, нет товара и т.д.)."""


@transaction.atomic  # всё или ничего: любая ошибка откатит и списание остатков
def confirm_order(order, contact):
    """Подтверждает корзину: проверяет и списывает остатки, фиксирует цены, меняет статус."""
    if order.state != 'basket':
        raise OrderError('Подтвердить можно только корзину.')

    items = list(order.items.select_related('product_info__shop'))
    if not items:
        raise OrderError('Корзина пуста.')

    for item in items:
        info = item.product_info
        if info is None:
            raise OrderError(f'Товар «{item.name}» больше недоступен.')
        if not info.shop.accepts_orders:
            raise OrderError(f'Магазин «{info.shop}» сейчас не принимает заказы.')

        # Условное списание одним запросом: сработает, только если остатка хватает.
        # F('quantity') даёт базе команду вычесть из текущего значения,
        # поэтому два одновременных заказа не спишут один и тот же остаток дважды
        updated = ProductInfo.objects.filter(
            pk=info.pk, quantity__gte=item.quantity
        ).update(quantity=F('quantity') - item.quantity)
        if not updated:
            raise OrderError(f'Товара «{item.name}» недостаточно в наличии.')

        item.price = info.price  # цена на момент покупки
        item.save(update_fields=['price'])

    order.contact = contact
    order.state = 'new'
    order.save(update_fields=['contact', 'state'])

    # Письма уходят только после успешного завершения транзакции.
    # robust=True: ошибка почты будет записана в лог и не отменит уже оформленный заказ
    transaction.on_commit(lambda: send_order_emails(order.pk), robust=True)
    return order