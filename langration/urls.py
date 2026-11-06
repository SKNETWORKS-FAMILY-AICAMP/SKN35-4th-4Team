from django.urls import path

from . import views

# /langration/ 아래 화면
urlpatterns = [
    path("", views.home, name="home"),
]

# /api/langration/ 아래 API
api_urlpatterns = [
    path("sessions/", views.api_sessions, name="api_sessions"),
    path("sessions/<str:session_id>/", views.api_session, name="api_session"),
    path("chat/", views.api_chat, name="api_chat"),
]
