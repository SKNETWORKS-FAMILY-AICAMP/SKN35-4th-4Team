from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('execute-langration/', views.execute_langration, name='execute_langration'),
]
