"""로그인 · 회원가입 (아이디 + 비밀번호).

화면 : /login/          → users/login.html
       /login/signup/   → users/signup.html
API  : POST /api/users/signup/  {user_id, password, password_confirm} → {ok, user_id}  (중복이면 ok=false)
       POST /api/users/login/   {user_id, password}                   → {ok, user_id}
       POST /api/users/logout/                                        → {ok}
비밀번호는 원문을 저장하지 않고 make_password() 해시만 users.password 에 둔다 (확인은 check_password()).
로그인 상태는 Django 세션의 request.session["user_id"] 에 둔다.
"""

import json
import re

from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import User

USER_ID_RULE = re.compile(r"^[0-9A-Za-z가-힣_]{2,20}$")   # 3차와 같은 규칙
PASSWORD_MIN, PASSWORD_MAX = 6, 64
LOGIN_FAIL = "아이디 또는 비밀번호가 맞지 않아요."        # 어느 쪽이 틀렸는지는 알려 주지 않음


def current_user_id(request):
    return request.session.get("user_id")


def _body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def _fail(error: str, status: int = 200) -> JsonResponse:
    return JsonResponse({"ok": False, "error": error}, status=status)


# ── 화면 ──
def login_page(request):
    if current_user_id(request):
        return redirect("/langration/")
    return render(request, "users/login.html")


def signup_page(request):
    if current_user_id(request):
        return redirect("/langration/")
    return render(request, "users/signup.html")


# ── API ──
@require_POST
def api_signup(request):
    data = _body(request)
    user_id = (data.get("user_id") or "").strip()
    password = data.get("password") or ""
    if not USER_ID_RULE.match(user_id):
        return _fail("아이디는 한글 · 영문 · 숫자 · _ 로 2~20자예요.")
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        return _fail(f"비밀번호는 {PASSWORD_MIN}~{PASSWORD_MAX}자로 정해 주세요.")
    if password != (data.get("password_confirm") or ""):
        return _fail("비밀번호 확인이 맞지 않아요. 같은 비밀번호를 두 번 입력해 주세요.")
    if User.objects.filter(user_id=user_id).exists():
        return _fail(f"'{user_id}'은 이미 있는 아이디예요. 다른 아이디를 쓰거나 로그인해 주세요.")
    try:
        User.objects.create(user_id=user_id, password=make_password(password))
    except IntegrityError:                       # 그사이 누가 먼저 가입한 경우
        return _fail(f"'{user_id}'은 이미 있는 아이디예요. 다른 아이디를 써 주세요.")
    request.session.cycle_key()
    request.session["user_id"] = user_id
    return JsonResponse({"ok": True, "user_id": user_id})


@require_POST
def api_login(request):
    data = _body(request)
    user_id = (data.get("user_id") or "").strip()
    password = data.get("password") or ""
    user = User.objects.filter(user_id=user_id).first() if user_id else None
    if user is None or not password:
        return _fail(LOGIN_FAIL)
    if not user.password:                        # 비밀번호 기능 전에 만든 아이디
        return _fail("비밀번호가 없는 예전 아이디예요. 새 아이디를 만들어 주세요.")
    if not check_password(password, user.password):
        return _fail(LOGIN_FAIL)
    request.session.cycle_key()                  # 로그인할 때 세션 키를 새로 (세션 고정 공격 방지)
    request.session["user_id"] = user_id
    return JsonResponse({"ok": True, "user_id": user_id})


@require_POST
def api_logout(request):
    request.session.flush()
    return JsonResponse({"ok": True})
