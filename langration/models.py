from django.db import models
from utils.generate_uuid import generate_uuid

# Create your models here.
 
class ChatHistory(models.Model):
    uuid = models.CharField(
        max_length=36,
        primary_key=True,
        default=generate_uuid,
        editable=False,
    )
    # users 앱의 User.user_id 를 참조 (1명이 여러 대화)
    user = models.ForeignKey(
        "users.User",
        to_field="user_id",
        db_column="user_id",
        on_delete=models.CASCADE,
        related_name="chat_histories",
    )
    session_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="대화방 단위",
    )
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="대화 순서 정렬용",
    )
 
    class Meta:
        db_table = "chat_history"
        ordering = ["created_at"]
 
    def __str__(self) -> str:
        return f"{self.session_id} / {self.created_at:%Y-%m-%d %H:%M}"