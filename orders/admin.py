from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    User, Shop, Category, Product, ProductInfo, Parameter,
    ProductParameter, Contact, Order, OrderItem, ConfirmEmailToken,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ('email',)
    list_display = ('email', 'company', 'type', 'is_staff', 'first_name', 'last_name', 'is_active')
    search_fields = ('email', 'first_name', 'last_name', 'company')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личные данные', {'fields': ('first_name', 'last_name', 'company', 'position', 'type')}),
        ('Права', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),
    )


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'accepts_orders', 'user')
    list_filter = ('accepts_orders',)
    search_fields = ('name',)  # нужен для autocomplete_fields в ProductInfo


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    filter_horizontal = ('shops',)  # удобный выбор для ManyToMany


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)  # нужен для autocomplete_fields в ProductInfo
    list_select_related = ('category',)  # один запрос вместо запроса на каждую строку


class ProductParameterInline(admin.TabularInline):
    """Характеристики показываются внутри карточки товара в магазине."""
    model = ProductParameter
    extra = 0


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ('product', 'shop', 'model', 'price', 'price_rrc', 'quantity')
    list_filter = ('shop', 'product__category')
    search_fields = ('product__name', 'model')  # двойное подчёркивание: поле связанной модели
    list_select_related = ('product', 'shop')
    autocomplete_fields = ('product', 'shop')   # поиск вместо огромного выпадающего списка
    inlines = [ProductParameterInline]


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    search_fields = ('name',)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'user', 'city', 'street', 'house', 'phone')
    search_fields = ('last_name', 'first_name', 'phone', 'user__email')


class OrderItemInline(admin.TabularInline):
    """Позиции показываются внутри заказа."""
    model = OrderItem
    extra = 0
    autocomplete_fields = ('product_info',)
    # Сумму по позиции только показываем, редактировать её нельзя
    readonly_fields = ('total',)
    fields = ('product_info', 'name', 'quantity', 'price', 'total')

    @admin.display(description='Сумма')
    def total(self, obj):
        return obj.total if obj.pk else '—'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'state', 'created_at', 'order_sum')
    list_filter = ('state',)
    search_fields = ('id', 'user__email')
    list_select_related = ('user',)
    readonly_fields = ('created_at',)
    inlines = [OrderItemInline]

    def get_queryset(self, request):
        # Подгружаем позиции заранее, иначе сумма каждого заказа
        # породит отдельный запрос (проблема N+1)
        return super().get_queryset(request).prefetch_related('items')

    @admin.display(description='Сумма')
    def order_sum(self, obj):
        return obj.total_sum


@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at')
    readonly_fields = ('key', 'created_at')