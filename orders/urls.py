from django.urls import path

from .views import ConfirmEmailView, LoginView, RegisterView

urlpatterns = [
    path('user/register', RegisterView.as_view()),
    path('user/register/confirm', ConfirmEmailView.as_view()),
    path('user/login', LoginView.as_view()),
]