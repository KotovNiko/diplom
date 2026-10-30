import yaml
from django.db import transaction

from orders.models import (
    Shop, Category, Product, ProductInfo, Parameter, ProductParameter,
)


def load_yaml(path):
    """Читает YAML-файл и возвращает словарь."""
    with open(path, encoding='utf-8') as file:
        return yaml.safe_load(file)  # safe_load не выполняет произвольный код


@transaction.atomic  # всё или ничего: при ошибке все изменения откатятся
def import_shop_data(data, user=None):
    """Загружает данные одного магазина. Возвращает (магазин, число товаров)."""
    shop, _ = Shop.objects.get_or_create(name=data['shop'])
    if user is not None:
        # Для импорта через API: привязываем магазин к поставщику
        shop.user = user
        shop.save()

    # Категории создаём с id из файла, чтобы товары могли на них сослаться
    for item in data['categories']:
        category, _ = Category.objects.get_or_create(
            id=item['id'], defaults={'name': item['name']}
        )
        category.shops.add(shop)  # связываем категорию с магазином

    for item in data['goods']:
        # Если категории нет в файле, будет ошибка, и транзакция откатится
        category = Category.objects.get(id=item['category'])
        product, _ = Product.objects.get_or_create(
            name=item['name'], category=category
        )
        # update_or_create: при повторном импорте запись обновится, а не продублируется
        info, _ = ProductInfo.objects.update_or_create(
            shop=shop,
            external_id=item['id'],
            defaults={
                'product': product,
                'model': item.get('model', ''),
                'price': item['price'],
                'price_rrc': item['price_rrc'],
                'quantity': item['quantity'],
            },
        )
        # Характеристики: набор произвольный, заранее не задан
        for name, value in item.get('parameters', {}).items():
            parameter, _ = Parameter.objects.get_or_create(name=name)
            ProductParameter.objects.update_or_create(
                product_info=info,
                parameter=parameter,
                defaults={'value': str(value)},  # числа и true приводим к строке
            )

    return shop, len(data['goods'])