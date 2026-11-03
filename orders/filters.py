import django_filters

from .models import ProductInfo


class ProductInfoFilter(django_filters.FilterSet):
    """Параметры запроса: ?shop=1&category=224&price_min=1000&price_max=70000"""
    shop = django_filters.NumberFilter(field_name='shop_id')
    category = django_filters.NumberFilter(field_name='product__category_id')
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')

    class Meta:
        model = ProductInfo
        fields = []  # все фильтры описаны явно выше