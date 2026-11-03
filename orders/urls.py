from django.urls import path

from .views import (
    ConfirmEmailView, LoginView, ProductDetailView, ProductListView, RegisterView,
)

urlpatterns = [
    path('user/register', RegisterView.as_view()),
    path('user/register/confirm', ConfirmEmailView.as_view()),
    path('user/login', LoginView.as_view()),
    path('products', ProductListView.as_view()),
    path('products/<int:pk>', ProductDetailView.as_view()),
]