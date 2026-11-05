# API 명세

Langration 4차 Django API 정리입니다. 화면(`static/js/api.js`)은 이 API만 불러서 동작합니다.

- 기준: 2026-11-05 `dev`
- 형식: 요청 · 응답 모두 JSON (채팅만 NDJSON 스트리밍)
- 실패 응답은 모두 `{"ok": false, "error": "이유"}`

## 1. 한눈에

| 앱 | 메서드 | 경로 | 하는 일 | 로그인 |
|---|---|---|---|---|
| `users` | POST | `/api/users/signup/` | 아이디 만들기 + 로그인 | 불필요 |
| `users` | POST | `/api/users/login/` | 로그인 | 불필요 |
| `users` | POST | `/api/users/logout/` | 로그아웃 | 필요 |
| `langration` | POST | `/api/langration/sessions/` | 새 대화 번호 받기 | 필요 |
| `langration` | GET | `/api/langration/sessions/` | 내 대화 목록 (최근 50개) | 필요 |
| `langration` | GET | `/api/langration/sessions/<id>/` | 대화 다시 열기 | 필요 |
| `langration` | DELETE | `/api/langration/sessions/<id>/` | 대화 삭제 | 필요 |
| `langration` | POST | `/api/langration/chat/` | 질문 처리 (스트리밍) | 필요 |

화면 주소: `/login/`(로그인) · `/login/signup/`(가입) · `/langration/`(대화 화면, 로그인 안 했으면 `/login/`으로 이동)

## 2. 공통 규칙

| 항목 | 내용 |
|---|---|
| 로그인 | Django 세션. 로그인 · 가입하면 `request.session["user_id"]`에 아이디가 저장되고, 세션 키를 새로 발급(`cycle_key`) |
| CSRF | 모든 POST · DELETE는 CSRF 토큰 필요. 화면 JS가 `X-CSRFToken` 헤더로 보냄 |
| 로그인 안 함 | `langration` API는 **401** `{"ok": false, "error": "로그인이 필요해요."}` |
| 남의 대화 | 다른 사람의 `session_id`로 요청하면 **404** `대화를 찾지 못했어요.` |

## 3. users

### POST `/api/users/signup/`

| 보내는 값 | 규칙 |
|---|---|
| `user_id` | 한글 · 영문 · 숫자 · `_` 2~20자, 중복 불가 |
| `password` | 6~64자 |
| `password_confirm` | `password`와 같아야 함 |

```json
{"ok": true, "user_id": "langration_user"}
```

실패 예: 아이디 형식 · 비밀번호 길이 · 확인 불일치 · 이미 있는 아이디 (동시 가입은 DB 고유 제약으로 한 번 더 막음)

### POST `/api/users/login/`

| 보내는 값 | |
|---|---|
| `user_id`, `password` | |

```json
{"ok": true, "user_id": "langration_user"}
```

- 아이디가 없거나 비밀번호가 틀리면 둘 다 같은 문구 `아이디 또는 비밀번호가 맞지 않아요`
- 없는 아이디도 비밀번호 비교와 같은 시간이 걸리게 맞춤 (응답 시간으로 아이디 존재 여부가 드러나지 않게)

### POST `/api/users/logout/`

```json
{"ok": true}
```

## 4. langration

### POST `/api/langration/sessions/`

새 대화 번호(uuid)를 받습니다. 번호만 만들고 DB에는 저장하지 않으며, 첫 질문이 저장될 때 목록에 나타납니다 (빈 대화가 쌓이지 않게).

```json
{"ok": true, "session_id": "4f1c…"}
```

### GET `/api/langration/sessions/`

```json
{
  "ok": true,
  "sessions": [
    {"session_id": "4f1c…", "title": "첫 질문 앞부분", "started_at": "…", "last_at": "…", "turns": 3}
  ]
}
```

### GET `/api/langration/sessions/<id>/`

```json
{"ok": true, "messages": [{"question": "…", "answer": "…", "created_at": "…"}]}
```

### DELETE `/api/langration/sessions/<id>/`

그 대화의 질문 · 답을 모두 지웁니다 (되돌릴 수 없음).

```json
{"ok": true, "deleted": 3}
```

### POST `/api/langration/chat/`

| 보내는 값 | 규칙 |
|---|---|
| `session_id` | 필수 |
| `message` | 필수, 20,000자 이내 (코드 포함) |

응답은 **NDJSON 스트리밍**입니다. 한 줄에 JSON 하나씩 옵니다.

```text
{"type": "step", "done": "① 바꿀 부분 2곳 찾음 · 목표 LangChain 1.4.5", "next": "② 근거 찾는 중", "details": [...], "sec": 6.0}
{"type": "step", ...}
{"type": "done", "kind": "migration", "reply": "2군데를 고쳤어요…", "result": {...}, "steps": [...], "seconds": 20.0}
```

| 이벤트 | 언제 | 내용 |
|---|---|---|
| `step` | 그래프 단계가 끝날 때마다 | 끝난 단계(`done`) · 다음 단계(`next`) · 세부 내용 · 경과 초 |
| `done` | 마지막 한 줄 | 답 종류(`kind`: migration · search · general), 대화에 보일 답(`reply`), 결과 패널 데이터(`result`: 변경 · 근거 · 검사 · 설치 패키지 등), 전체 단계, 걸린 시간 |
| `error` | 실패했을 때 한 줄 | 이유 |
| 빈 줄 | 15초 동안 보낼 게 없을 때 | 연결 유지 (화면은 무시) |

처리 순서

1. 일하는 스레드가 그래프를 실행합니다 (`thread_id = 아이디:세션`으로 대화마다 기억을 나눔).
2. 단계가 끝날 때마다 큐에 `step`을 넣고, 응답이 꺼내는 대로 바로 보냅니다.
3. 끝나면 질문 · 답을 `chat_history`에 저장하고 `done`을 보냅니다.
4. 응답 헤더 `X-Accel-Buffering: no`로 Nginx가 모아 두지 않게 합니다.

## 5. 오류 정리

| 상태 | 경우 |
|---|---|
| 200 + `ok: false` | 가입 · 로그인 입력 오류 (형식 · 길이 · 중복 · 로그인 실패) |
| 400 | 채팅에 `session_id` · `message`가 없음, 질문이 20,000자를 넘음 |
| 401 | 로그인하지 않고 `langration` API 호출 |
| 404 | 없는 대화 또는 남의 대화 |
| 405 | 허용하지 않은 메서드 |

## 6. 관련 파일

| 파일 | 내용 |
|---|---|
| `users/views.py` · `users/urls.py` | 가입 · 로그인 · 로그아웃 |
| `langration/views.py` · `langration/urls.py` | 대화 세션 · 채팅 스트리밍 |
| `langration/reply.py` | 코드 변환 결과를 대화용 요약 문장으로 |
| `config/urls.py` | `/api/users/` · `/api/langration/` 연결 |
| `static/js/api.js` | 화면 쪽 API 주소 · 호출 · 스트리밍 읽기 |
