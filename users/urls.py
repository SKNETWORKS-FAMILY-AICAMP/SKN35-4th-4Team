from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.main, name='main'),
    path('login/', views.login, name='main'),
    path('logout/', views.logout, name='logout'),
    path('signin/', views.signin, name='signin'),
]
