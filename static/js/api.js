// ─────────────────────────────────────────────
// 백엔드(①)와 주고받는 주소와 공통 함수
// 주소가 바뀌면 이 파일의 API 만 고치면 됨 (화면 코드는 그대로)
// ─────────────────────────────────────────────
const API = {
    signup: "/api/users/signup/",
    login: "/api/users/login/",
    logout: "/api/users/logout/",
    sessions: "/api/langration/sessions/",                      // GET 목록 · POST 새 대화
    session: (id) => `/api/langration/sessions/${encodeURIComponent(id)}/`,   // GET 대화 내용
    chat: "/api/langration/chat/",
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

// 백엔드에 요청을 보내고 JSON 답장을 돌려줌
// 성공: { ok: true, ... }   실패: { ok: false, error: "이유" }
async function callApi(url, { method = "GET", body } = {}) {
    let response;
    try {
        response = await fetch(url, {
            method,
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            body: body ? JSON.stringify(body) : undefined,
        });
    } catch (error) {
        return { ok: false, error: "서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요." };
    }

    if (response.status === 401 || response.status === 403) {   // 로그인이 풀렸으면 로그인 화면으로
        window.location.href = PAGE.login;
        return { ok: false, error: "로그인이 필요해요." };
    }

    try {
        return await response.json();
    } catch (error) {
        return { ok: false, error: `서버 응답을 읽지 못했어요. (HTTP ${response.status})` };
    }
}

// 안내 문구 바꾸기 (ok 가 true 면 초록, 아니면 빨강)
function showMessage(element, text, ok = false) {
    element.textContent = text;
    element.classList.toggle("ok", ok);
}
