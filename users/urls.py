from django.urls import path

from . import views

# /login/ 아래 화면
urlpatterns = [
    path("", views.login_page, name="login"),
    path("signup/", views.signup_page, name="signup"),
]

# /api/users/ 아래 API
api_urlpatterns = [
    path("signup/", views.api_signup, name="api_signup"),
    path("login/", views.api_login, name="api_login"),
    path("logout/", views.api_logout, name="api_logout"),
]
