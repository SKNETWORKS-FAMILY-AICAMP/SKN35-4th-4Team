"""대화 화면 · 대화 API (3차 streamlit_app.py 의 handle · sidebar 를 Django 로 옮긴 것).

화면 : /langration/                         → langration/home.html (로그인 필요)
API  : POST /api/langration/sessions/        → {ok, session_id}       새 대화 (첫 질문을 보낼 때 화면이 부름)
       GET  /api/langration/sessions/        → {ok, sessions: [...]}  내 대화 목록
       GET  /api/langration/sessions/<id>/   → {ok, messages: [...]}  대화 다시 열기 (질문 · 답만)
       DELETE /api/langration/sessions/<id>/ → {ok, deleted}          대화 삭제
       POST /api/langration/chat/  {session_id, message}
            → 스트리밍 (JSON 한 줄씩): step … step → done (3차 client.ask() 결과) / error
그래프 호출은 3차와 같이 langration/src/ui/client.py 한 곳 (그래프는 한 번만 만들고, 대화마다 thread_id 로 기억을 나눔).
"""

import json
import queue
import threading
import time
import traceback
import uuid
from functools import wraps

from django.db import close_old_connections, connection
from django.db.models import Count, Max, Min
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from langration.src.ui import client
from langration.src.ui.mock import import_paths
from users.models import User

from .models import ChatHistory
from .reply import extract_code, summary

LIST_LIMIT = 50


def _user_id(request):
    return request.session.get("user_id")


def api_login_required(view):
    """API 는 로그인 안 했으면 401 (화면이 로그인 화면으로 보냄)."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not _user_id(request):
            return JsonResponse({"ok": False, "error": "로그인이 필요해요."}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


def _body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def _owner_ok(session_id: str, user_id: str) -> bool:
    """남의 대화 번호가 아닌지 (처음 쓰는 번호면 통과)."""
    return not ChatHistory.objects.filter(session_id=session_id).exclude(user_id=user_id).exists()


# ── 화면 ──
def home(request):
    user_id = _user_id(request)
    if not user_id or not User.objects.filter(user_id=user_id).exists():
        request.session.flush()
        return redirect("/login/")
    return render(request, "langration/home.html", {"user_id": user_id})


# ── 대화 목록 · 새 대화 ──
@require_http_methods(["GET", "POST"])
@api_login_required
def api_sessions(request):
    user_id = _user_id(request)
    if request.method == "POST":
        return JsonResponse({"ok": True, "session_id": str(uuid.uuid4())})

    rows = list(ChatHistory.objects.filter(user_id=user_id)
                .values("session_id")
                .annotate(started_at=Min("created_at"), last_at=Max("created_at"), turns=Count("uuid"))
                .order_by("-last_at")[:LIST_LIMIT])
    titles = {}
    for r in (ChatHistory.objects.filter(user_id=user_id, session_id__in=[x["session_id"] for x in rows])
              .order_by("created_at").values("session_id", "question")):
        titles.setdefault(r["session_id"], r["question"])
    sessions = [{
        "session_id": r["session_id"],
        "title": (titles.get(r["session_id"]) or "").strip().splitlines()[0][:40] if titles.get(r["session_id"]) else "",
        "started_at": r["started_at"].isoformat(),
        "last_at": r["last_at"].isoformat(),
        "turns": r["turns"],
    } for r in rows]
    return JsonResponse({"ok": True, "sessions": sessions})


@require_http_methods(["GET", "DELETE"])
@api_login_required
def api_session(request, session_id):
    rows = ChatHistory.objects.filter(user_id=_user_id(request), session_id=session_id).order_by("created_at")
    if not rows.exists():                                # 없는 대화 · 남의 대화
        return JsonResponse({"ok": False, "error": "대화를 찾지 못했어요."}, status=404)
    if request.method == "DELETE":                       # 대화 삭제 (그 대화의 질문 · 답 전부, 되돌릴 수 없음)
        deleted, _ = rows.delete()
        return JsonResponse({"ok": True, "deleted": deleted})
    messages = [{"question": r.question, "answer": r.answer, "created_at": r.created_at.isoformat()} for r in rows]
    return JsonResponse({"ok": True, "messages": messages})


# ── 질문 보내기 (스트리밍) ──
def _answer(text: str, user_id: str, session_id: str, emit) -> dict:
    """질문 하나 처리: 팀 그래프 → (못 쓰면) 임시 결과 → 답 글. 3차 handle() 과 같은 순서."""
    t0 = time.time()

    def on_step(done, nxt, details=()):
        emit({"type": "step", "done": done, "next": nxt, "details": list(details or []), "sec": round(time.time() - t0, 1)})

    graph_error = None
    try:
        answer = client.ask(text, on_step, thread_id=f"{user_id}:{session_id}")   # 그래프를 쓸 수 없으면 None
    except Exception as e:                                   # 그래프 실행 중 오류 → 임시 결과로 계속
        answer = None
        graph_error = f"{type(e).__name__}: {str(e)[:300]}"
        traceback.print_exc()

    if answer is not None:
        result = answer["result"]
        out = {"kind": answer["kind"], "reply": summary(result) if result else answer["reply"], "result": result,
               "steps": answer.get("steps") or [], "seconds": answer.get("seconds")}
    else:
        code = extract_code(text)
        if import_paths(code):                               # 그래프 없음: 대응표로 만든 임시 결과
            result = client.run(code)
            out = {"kind": "migration", "reply": summary(result), "result": result, "steps": [], "seconds": None}
        else:
            out = {"kind": "general", "reply": "옛 LangChain 코드를 붙여 넣어 주세요. 코드가 있어야 바꿔 드릴 수 있어요.",
                   "result": None, "steps": [], "seconds": None}
        if graph_error:
            out["graph_error"] = graph_error
    return out


@require_POST
@api_login_required
def api_chat(request):
    user_id = _user_id(request)
    data = _body(request)
    session_id = str(data.get("session_id") or "").strip()[:100]
    text = (data.get("message") or "").strip()
    if not session_id or not text:
        return JsonResponse({"ok": False, "error": "대화 번호와 질문이 필요해요."}, status=400)
    if not _owner_ok(session_id, user_id):
        return JsonResponse({"ok": False, "error": "대화를 찾지 못했어요."}, status=404)

    events: queue.Queue = queue.Queue()

    def work():
        close_old_connections()
        try:
            out = _answer(text, user_id, session_id, events.put)
            ChatHistory.objects.create(user_id=user_id, session_id=session_id, question=text, answer=out["reply"] or "")
            events.put({"type": "done", **out})
        except Exception as e:
            traceback.print_exc()
            events.put({"type": "error", "error": f"답을 만들지 못했어요 ({type(e).__name__})."})
        finally:
            connection.close()                               # 이 스레드가 연 DB 연결 정리
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while True:
            try:
                item = events.get(timeout=15)
            except queue.Empty:                              # 오래 걸리는 단계: 연결이 끊기지 않게 빈 줄
                yield "\n"
                continue
            if item is None:
                return
            yield json.dumps(item, ensure_ascii=False, default=str) + "\n"

    response = StreamingHttpResponse(stream(), content_type="application/x-ndjson; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"                     # Nginx 가 모아 두지 않고 바로 보내게
    return response
