"""로그인 · 회원가입 (비밀번호 없이 아이디만, 3차와 같은 방식).

화면 : /login/          → users/login.html
       /login/signup/   → users/signup.html
API  : POST /api/users/signup/  {user_id} → {ok, user_id}  (중복이면 ok=false)
       POST /api/users/login/   {user_id} → {ok, user_id}
       POST /api/users/logout/            → {ok}
로그인 상태는 Django 세션의 request.session["user_id"] 에 둔다.
"""

import json
import re

from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import User

USER_ID_RULE = re.compile(r"^[0-9A-Za-z가-힣_]{2,20}$")   # 3차와 같은 규칙


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
    user_id = (_body(request).get("user_id") or "").strip()
    if not USER_ID_RULE.match(user_id):
        return _fail("아이디는 한글 · 영문 · 숫자 · _ 로 2~20자예요.")
    if User.objects.filter(user_id=user_id).exists():
        return _fail(f"'{user_id}'은 이미 있는 아이디예요. 다른 아이디를 쓰거나 로그인해 주세요.")
    try:
        User.objects.create(user_id=user_id)
    except IntegrityError:                       # 그사이 누가 먼저 가입한 경우
        return _fail(f"'{user_id}'은 이미 있는 아이디예요. 다른 아이디를 써 주세요.")
    request.session["user_id"] = user_id
    return JsonResponse({"ok": True, "user_id": user_id})


@require_POST
def api_login(request):
    user_id = (_body(request).get("user_id") or "").strip()
    if not user_id or not User.objects.filter(user_id=user_id).exists():
        return _fail("그 아이디는 없어요. 아이디를 먼저 만들어 주세요.")
    request.session.cycle_key()                  # 로그인할 때 세션 키를 새로 (세션 고정 공격 방지)
    request.session["user_id"] = user_id
    return JsonResponse({"ok": True, "user_id": user_id})


@require_POST
def api_logout(request):
    request.session.flush()
    return JsonResponse({"ok": True})
