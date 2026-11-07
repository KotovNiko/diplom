from rest_framework.permissions import BasePermission


class IsShop(BasePermission):
    """Доступ только для пользователей с типом «Поставщик»."""
    message = 'Доступно только поставщикам.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.type == 'shop')