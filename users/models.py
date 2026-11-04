from django.db import models
from utils.generate_uuid import generate_uuid

# Create your models here.
 
class User(models.Model):
    uuid = models.CharField(
        max_length=36,
        primary_key=True,
        default=generate_uuid,
        editable=False,
    )
    user_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="로그인 아이디",
    )
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "users"
 
    def __str__(self) -> str:
        return self.user_id