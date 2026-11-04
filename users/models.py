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
    # 비밀번호는 원문이 아니라 Django make_password() 로 만든 해시만 저장 (pbkdf2_sha256)
    # db_default: 이 칸을 모르는 옛 코드가 INSERT 해도 DB 가 빈 값으로 채움
    password = models.CharField(max_length=128, default="", db_default="", help_text="비밀번호 해시")
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "users"
 
    def __str__(self) -> str:
        return self.user_id