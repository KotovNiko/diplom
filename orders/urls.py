from django.urls import path

from .views import (
    ConfirmEmailView,
    LoginView,
    ProductDetailView,
    ProductListView,
    RegisterView,
    BasketItemView,
    BasketView,
    ContactDetailView,
    ContactListCreateView,
    OrderListCreateView,
    OrderDetailView,
)

urlpatterns = [
    path('user/register', RegisterView.as_view()),
    path('user/register/confirm', ConfirmEmailView.as_view()),
    path('user/login', LoginView.as_view()),
    path('products', ProductListView.as_view()),
    path('products/<int:pk>', ProductDetailView.as_view()),
    path('basket', BasketView.as_view()),
    path('basket/<int:item_id>', BasketItemView.as_view()),
    path('user/contact', ContactListCreateView.as_view()),
    path('user/contact/<int:pk>', ContactDetailView.as_view()),
    path('order', OrderListCreateView.as_view()),
    path('order/<int:pk>', OrderDetailView.as_view()),
]