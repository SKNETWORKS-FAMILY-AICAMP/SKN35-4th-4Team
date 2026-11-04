// ─────────────────────────────────────────────
// 백엔드(①)와 주고받는 주소와 공통 함수
// 주소가 바뀌면 이 파일의 API 만 고치면 됨 (화면 코드는 그대로)
// ─────────────────────────────────────────────
const API = {
    signup: "/api/users/signup/",
    login: "/api/users/login/",
    logout: "/api/users/logout/",
    sessions: "/api/langration/sessions/",                                     // GET 목록 · POST 새 대화
    session: (id) => `/api/langration/sessions/${encodeURIComponent(id)}/`,   // GET 대화 내용
    chat: "/api/langration/chat/",                                            // POST · 한 줄씩 흘려보내는 응답 (스트리밍)
};

const PAGE = {
    login: "/login/",
    chat: "/langration/",
};

// {% csrf_token %} 이 만든 숨은 칸에서 보안 토큰을 꺼냄 (POST 에 꼭 필요)
function getCsrfToken() {
    const field = document.querySelector("input[name=csrfmiddlewaretoken]");
    return field ? field.value : "";
}

function headers() {
    return { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() };
}

function needLogin(response) {
    if (response.status === 401 || response.status === 403) {   // 로그인이 풀렸으면 로그인 화면으로
        window.location.href = PAGE.login;
        return true;
    }
    return false;
}

// 보통 요청: JSON 답장 하나를 돌려줌
// 성공: { ok: true, ... }   실패: { ok: false, error: "이유" }
async function callApi(url, { method = "GET", body } = {}) {
    let response;
    try {
        response = await fetch(url, { method, headers: headers(), body: body ? JSON.stringify(body) : undefined });
    } catch (error) {
        return { ok: false, error: "서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요." };
    }
    if (needLogin(response)) return { ok: false, error: "로그인이 필요해요." };
    try {
        return await response.json();
    } catch (error) {
        return { ok: false, error: `서버 응답을 읽지 못했어요. (HTTP ${response.status})` };
    }
}

// 스트리밍 요청: 백엔드가 JSON 을 한 줄씩 흘려보내면 줄마다 onEvent(한 줄) 을 부름
//   {"type": "step", "done": "① 바꿀 부분 3곳 찾음", "next": "② 근거 찾는 중", "details": [...], "sec": 2.1}
//   {"type": "done", "kind": ..., "reply": ..., "result": ..., "steps": [...], "seconds": 18.2}
//   {"type": "error", "error": "이유"}
async function streamApi(url, body, onEvent) {
    let response;
    try {
        response = await fetch(url, { method: "POST", headers: headers(), body: JSON.stringify(body) });
    } catch (error) {
        onEvent({ type: "error", error: "서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요." });
        return;
    }
    if (needLogin(response)) return;
    if (!response.ok || !response.body) {
        let error = `서버 오류 (HTTP ${response.status})`;
        try { error = (await response.json()).error || error; } catch (e) { /* JSON 이 아니면 그대로 */ }
        onEvent({ type: "error", error });
        return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finished = false;
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();                                  // 아직 덜 온 마지막 줄은 남겨 둠
        for (const line of lines) {
            if (!line.trim()) continue;
            let event;
            try { event = JSON.parse(line); } catch (e) { continue; }
            if (event.type === "done" || event.type === "error") finished = true;
            onEvent(event);
        }
    }
    if (buffer.trim()) {
        try { const event = JSON.parse(buffer); finished = true; onEvent(event); } catch (e) { /* 무시 */ }
    }
    if (!finished) onEvent({ type: "error", error: "답변이 중간에 끊겼어요. 같은 질문을 다시 보내 보세요." });
}

// 안내 문구 바꾸기 (ok 가 true 면 초록, 아니면 빨강)
function showMessage(element, text, ok = false) {
    element.textContent = text;
    element.classList.toggle("ok", ok);
}

// 아래 검정 알림
function toast(text) {
    let box = document.getElementById("toast");
    if (!box) {
        box = document.createElement("div");
        box.id = "toast";
        box.className = "toast";
        box.innerHTML = '<span class="ok"></span><span class="tx"></span>';
        box.firstChild.append(icon("check"));
        document.body.append(box);
    }
    box.querySelector(".tx").textContent = text;
    box.classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => box.classList.remove("show"), 1800);
}
