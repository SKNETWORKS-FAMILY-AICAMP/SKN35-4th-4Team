// ─────────────────────────────────────────────
// 대화 화면 (3차 streamlit_app.py 의 chat_screen · sidebar · handle 을 옮긴 것)
//
// 백엔드와 주고받는 것 (API 는 api.js)
//   새 대화 첫 질문 → POST API.sessions      → { ok, session_id }
//   질문 · 예제     → POST API.chat (스트리밍) → step 줄 여러 개 … → done 줄 하나
//                     done = 3차 client.ask() 결과 그대로 { kind, reply, result, steps, seconds }
//   내 대화 목록    → GET  API.sessions      → { ok, sessions: [{ session_id, title, last_at, started_at?, turns? }] }
//   대화 다시 열기  → GET  API.session(id)   → { ok, messages: [{ question, answer, created_at }] }
//   로그아웃        → POST API.logout        → { ok }
// ─────────────────────────────────────────────

const $ = (id) => document.getElementById(id);
const el = {
    frame: $("frame"), messages: $("messages"), sessions: $("session-list"), resultBody: $("result-body"),
    title: $("chat-title"), meta: $("chat-meta"), status: $("status"),
    composers: [...document.querySelectorAll("[data-composer]")],
};

const state = {
    user: document.body.dataset.user || "",
    sessionId: null,       // 지금 대화 번호 (새 대화는 첫 질문을 보낼 때 받음)
    sessions: [],          // 내 대화 목록
    results: [],           // 이 대화에서 나온 변환 결과들 (변환 기록 ① ② …)
    hasMessages: false,
    reopened: false,       // 저장된 대화를 다시 열었는지 (결과 패널은 비어 있음)
    busy: false,
    resultClosed: false,   // 사용자가 결과 패널을 닫았는지
    examples: [],
};


// ─────────────── 1. 처음 열렸을 때 ───────────────
function init() {
    const initial = (state.user || "?").slice(0, 1).toUpperCase();
    $("avatar").textContent = initial;
    $("avatar-side").textContent = initial;
    if (window.DOMPurify) {                                     // 답 안의 링크는 새 탭으로
        DOMPurify.addHook("afterSanitizeAttributes", (node) => {
            if (node.tagName === "A") { node.target = "_blank"; node.rel = "noopener noreferrer"; }
        });
    }
    el.composers.forEach(setupComposer);
    loadExamples();
    loadSessions();
    renderResult();
}


// ─────────────── 2. 입력창 ───────────────
function setupComposer(form) {
    const box = form.querySelector("textarea");
    const send = form.querySelector(".send");
    const grow = () => {
        box.style.height = "auto";
        box.style.height = `${Math.min(box.scrollHeight, 260)}px`;
        send.classList.toggle("ready", box.value.trim() !== "" && !state.busy);
    };
    box.addEventListener("input", grow);
    box.addEventListener("keydown", (e) => {                    // Enter 보내기 · Shift+Enter 줄 바꿈
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
    });
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = box.value;
        if (!text.trim() || state.busy) return;
        box.value = "";
        grow();
        sendQuestion(text);
    });
    form.grow = grow;
}

function setBusy(busy) {
    state.busy = busy;
    el.composers.forEach((f) => { f.querySelector(".send").disabled = busy; f.grow && f.grow(); });
}

function focusComposer() {
    const visible = el.frame.classList.contains("welcome") ? el.composers[0] : el.composers[1];
    visible.querySelector("textarea").focus();
}


// ─────────────── 3. 질문 보내기 (스트리밍) ───────────────
async function sendQuestion(text) {
    text = text.trim();
    if (!text || state.busy) return;
    setBusy(true);
    showChat();
    addUserTurn(text);
    const bot = addBotTurn();
    const progress = progressBox();
    bot.body.append(progress.node);
    scrollDown();

    // 새 대화의 첫 질문 → 새 대화 번호
    if (!state.sessionId) {
        const created = await callApi(API.sessions, { method: "POST" });
        if (!created.ok) return fail(bot, progress, created.error);
        state.sessionId = created.session_id;
    }

    let finished = false;
    await streamApi(API.chat, { session_id: state.sessionId, message: text }, (ev) => {
        if (ev.type === "step") {
            progress.add(ev);
        } else if (ev.type === "done") {
            finished = true;
            progress.node.remove();
            showAnswer(bot, ev, text, true);
        } else if (ev.type === "error") {
            finished = true;
            fail(bot, progress, ev.error);
        }
    });
    if (!finished) fail(bot, progress, "답변을 받지 못했어요.");
    setBusy(false);
    loadSessions();
}

function fail(bot, progress, error) {
    progress.node.remove();
    const b = h("div", "bubble error", `⚠ ${error || "답변을 받지 못했어요."} 같은 질문을 다시 보내 보세요.`);
    bot.body.append(b);
    setBusy(false);
    scrollDown();
}

// 진행 상자: "Langration이 생각 중입니다… · ② 근거 찾는 중" + 끝난 단계 목록 (항상 펼쳐 둠 — 3차 화면 기록 ⑤ 문제)
function progressBox() {
    const node = h("div", "progress");
    const head = h("div", "head");
    const label = h("span", "", "Langration이 생각 중입니다…");
    head.append(h("span", "spin"), label);
    const list = h("div", "list");
    node.append(head, list);
    return {
        node,
        add(ev) {
            list.append(stepRow(ev));
            if (ev.next) label.textContent = `Langration이 생각 중입니다… · ${ev.next}`;
            scrollDown();
        },
    };
}

// 답 하나 그리기: 처리 과정(접었다 펴기) + 답 글 + 결과 패널
function showAnswer(bot, data, request, fresh) {
    const steps = data.steps || [];
    if (steps.length) {
        // 가장 최근 답의 처리 과정만 펼쳐 둠
        el.messages.querySelectorAll("details.steps[open]").forEach((d) => d.removeAttribute("open"));
        const d = h("details", "steps");
        d.open = fresh;
        const sum = h("summary");
        sum.append(icon("tree"), document.createTextNode(
            `처리 과정 보기 · ${steps.length}단계${data.seconds != null ? ` · ${Math.round(data.seconds)}초` : ""}`), icon("chev", "chev"));
        d.append(sum, stepsView(steps, data.seconds, false));
        bot.body.append(d);
    }
    const result = data.result || null;
    let reply = data.reply || (result ? summarize(result) : "") || "답을 만들지 못했어요. 다시 물어봐 주세요.";
    if (data.graph_error) {
        reply = `⚠ 팀 챗봇 실행 중 오류가 나서 임시 결과를 보여 드려요.\n\n\`${data.graph_error}\`\n\n${reply}`;
    }
    const bubble = h("div", "bubble md");
    setMarkdown(bubble, reply);
    bot.body.append(bubble);

    if (result) {
        result.request = request;                 // "같은 요청으로 다시 시도" 가 그대로 다시 보냄
        if (!result.steps && steps.length) { result.steps = steps; result.seconds = data.seconds; }
        state.results.push(result);
        state.resultClosed = false;               // 새 결과가 오면 패널을 다시 엶
    }
    setStatus(result && result.mode !== "graph" ? "팀 챗봇 연결 안 됨 · 임시 결과로 보여 줘요" : data.graph_error ? "팀 챗봇 오류" : "");
    renderResult();
    scrollDown();
}


// ─────────────── 4. 말풍선 ───────────────
function addUserTurn(text) {
    state.hasMessages = true;
    const turn = h("div", "turn user");
    const body = h("div", "body");
    const bubble = h("div", "bubble md");
    setMarkdown(bubble, asMarkdown(text));
    body.append(bubble);
    turn.append(body);
    el.messages.append(turn);
    return { turn, body };
}

function addBotTurn() {
    const turn = h("div", "turn bot");
    const who = h("span", "who");
    who.append(icon("logo"));
    const body = h("div", "body");
    turn.append(who, body);
    el.messages.append(turn);
    return { turn, body };
}

// 마크다운 → 안전한 HTML (DOMPurify 로 스크립트 등을 걸러냄). 라이브러리가 없으면 글자 그대로
function setMarkdown(node, text) {
    if (window.marked && window.DOMPurify) {
        node.innerHTML = DOMPurify.sanitize(marked.parse(text, { breaks: true }));
    } else {
        node.textContent = text;
        node.style.whiteSpace = "pre-wrap";
    }
}

// 코드만 붙여 넣은 메시지는 코드 상자로 (3차 as_markdown)
function asMarkdown(text) {
    if (text.includes("```")) return text;
    return /^\s*(from|import)\s+langchain/m.test(text) ? "```python\n" + text.trim() + "\n```" : text;
}

function scrollDown() { el.messages.scrollTop = el.messages.scrollHeight; }


// ─────────────── 5. 화면 상태 ───────────────
function showChat() {
    el.frame.classList.remove("welcome");
    applyResultState();
}

function showWelcome() {
    el.frame.classList.add("welcome");
    el.frame.classList.remove("no-result");
}

function applyResultState() {
    if (el.frame.classList.contains("welcome")) return;
    el.frame.classList.toggle("no-result", state.resultClosed);
}

function renderResult() {
    renderResultPanel(el.resultBody, {
        results: state.results, reopened: state.reopened, hasMessages: state.hasMessages,
        onRetry: (request) => sendQuestion(request),
    });
    applyResultState();
}

function setStatus(text) {
    el.status.hidden = !text;
    el.status.textContent = text;
}

function resetChat() {
    state.sessionId = null;
    state.results = [];
    state.hasMessages = false;
    state.reopened = false;
    el.messages.replaceChildren();
    el.title.textContent = "새 대화";
    el.meta.textContent = "";
    renderResult();
    showWelcome();
    markActive();
}

$("toggle-result").addEventListener("click", () => { state.resultClosed = !state.resultClosed; applyResultState(); });
$("close-result").addEventListener("click", () => { state.resultClosed = true; applyResultState(); });


// ─────────────── 6. 새 대화 · 내 대화 ───────────────
$("new-chat").addEventListener("click", () => {
    if (state.busy) return;
    resetChat();
    focusComposer();
});

async function loadSessions() {
    const data = await callApi(API.sessions);
    el.sessions.replaceChildren();
    if (!data.ok) { el.sessions.append(h("p", "empty", data.error)); return; }
    state.sessions = data.sessions || [];
    if (!state.sessions.length) { el.sessions.append(h("p", "empty", "아직 대화가 없어요.")); return; }

    let lastGroup = null;
    state.sessions.forEach((s) => {
        const group = dayGroup(s.last_at);
        if (group !== lastGroup) { el.sessions.append(h("div", "group", group)); lastGroup = group; }
        const b = h("button", "item");
        b.type = "button";
        b.dataset.id = s.session_id;
        b.title = s.title || "";
        b.append(icon("chat"), h("span", "t", s.title || "(제목 없음)"));
        b.addEventListener("click", () => openSession(s.session_id));
        el.sessions.append(b);
    });
    markActive();
    updateHead();
}

async function openSession(id) {
    if (state.busy) return;
    const data = await callApi(API.session(id));
    if (!data.ok) { toast(data.error || "대화를 열지 못했어요"); return; }
    resetChat();
    state.sessionId = id;
    state.reopened = true;
    showChat();
    (data.messages || []).forEach((m) => {     // 기록에는 질문 · 답만 있음 (결과 패널은 비어 있음, 3차와 같음)
        addUserTurn(m.question);
        const bot = addBotTurn();
        const b = h("div", "bubble md");
        setMarkdown(b, m.answer || "");
        bot.body.append(b);
    });
    renderResult();
    markActive();
    updateHead();
    scrollDown();
}

function markActive() {
    el.sessions.querySelectorAll(".item").forEach((b) => b.classList.toggle("on", b.dataset.id === state.sessionId));
}

// 대화 위 안내: "세션 2137eb0d · 11/04 14:30 시작 · 질문 3개"
function updateHead() {
    const s = state.sessions.find((x) => x.session_id === state.sessionId);
    if (!state.sessionId) { el.title.textContent = "새 대화"; el.meta.textContent = ""; return; }
    el.title.textContent = (s && s.title) || "대화";
    const parts = [`세션 ${String(state.sessionId).slice(0, 8)}`];
    if (s && s.started_at) parts.push(`${fmtTime(s.started_at)} 시작`);
    if (s && s.turns) parts.push(`질문 ${s.turns}개`);
    el.meta.textContent = parts.join(" · ");
}

function toDate(v) {
    if (v === undefined || v === null || v === "") return null;
    const d = typeof v === "number" ? new Date(v < 1e12 ? v * 1000 : v) : new Date(v);
    return isNaN(d) ? null : d;
}
function dayGroup(v) {
    const d = toDate(v);
    if (!d) return "내 대화";
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const days = Math.floor((today - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 864e5);
    return days <= 0 ? "오늘" : days === 1 ? "어제" : days < 7 ? "이전 7일" : "더 이전";
}
function fmtTime(v) {
    const d = toDate(v);
    if (!d) return "";
    const p = (n) => String(n).padStart(2, "0");
    return `${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}


// ─────────────── 7. 확인용 예제 (3차 평가 질문 중 1.x 로 올리는 30개) ───────────────
const TYPE_ICON = { "LLMChain → LCEL": ["code", "v"], "메모리": ["history", "b"], "RAG": ["book", "g"], "에이전트 · 도구": ["flask", "o"] };

async function loadExamples() {
    try {
        const res = await fetch(document.body.dataset.examples);
        state.examples = await res.json();
    } catch (e) { state.examples = []; }
    $("example-count").textContent = state.examples.length;

    // 첫 화면 추천: 종류가 다른 예제 3개 + 코드 없는 질문 1개
    const list = $("suggest-list");
    const picks = [];
    for (const t of ["LLMChain → LCEL", "메모리", "RAG"]) {
        const q = state.examples.find((x) => x.type === t);
        if (q) picks.push(q);
    }
    picks.forEach((q) => list.append(suggestButton(q.request, q.type, TYPE_ICON[q.type] || ["code", "v"], () => sendExample(q))));
    const ask = "LangChain 1.x에서 create_agent는 무엇이고 initialize_agent와 뭐가 달라요?";
    list.append(suggestButton("create_agent와 initialize_agent는 뭐가 달라요?", "문서 질문", ["book", "g"], () => sendQuestion(ask)));
    renderExampleList("");
}

function suggestButton(text, tag, [ic, color], onClick) {
    const b = h("button", "sg");
    b.type = "button";
    const i = h("span", `ic ${color}`); i.append(icon(ic));
    b.append(i, h("span", "t", text), h("span", "tag", tag));
    b.addEventListener("click", onClick);
    return b;
}

function exampleText(q) { return `${q.request}\n\n\`\`\`python\n${q.code}\`\`\``; }
function sendExample(q) { closeModals(); sendQuestion(exampleText(q)); }

function renderExampleList(word) {
    const box = $("example-list");
    box.replaceChildren();
    const w = word.trim().toLowerCase();
    const hits = state.examples.filter((q) => !w || `${q.id} ${q.type} ${q.request} ${q.code}`.toLowerCase().includes(w));
    if (!hits.length) { box.append(h("p", "empty", "맞는 예제가 없어요.")); return; }
    let last = null;
    hits.forEach((q) => {
        if (q.type !== last) { box.append(h("div", "group", q.type)); last = q.type; }
        const b = suggestButton(`${q.id} · ${q.request}`, `${q.difficulty} · ${q.source_version} → 1.x`, TYPE_ICON[q.type] || ["code", "v"], () => sendExample(q));
        box.append(b);
    });
}

$("example-search").addEventListener("input", (e) => renderExampleList(e.target.value));
[$("open-examples"), $("rail-examples"), $("more-examples")].forEach((b) => b.addEventListener("click", () => openModal("examples")));
$("rail-help").addEventListener("click", () => openModal("help"));


// ─────────────── 8. 로그아웃 · 확인창 ───────────────
$("logout").addEventListener("click", () => openModal("confirm"));
$("confirm-ok").addEventListener("click", async () => {
    await callApi(API.logout, { method: "POST" });
    window.location.href = PAGE.login;
});

function openModal(id) {
    $(id).classList.add("show");
    const f = $(id).querySelector("input");
    if (f) setTimeout(() => f.focus(), 30);
}
function closeModals() { document.querySelectorAll(".modal.show").forEach((m) => m.classList.remove("show")); }
document.querySelectorAll(".modal").forEach((m) => m.addEventListener("click", (e) => {
    if (e.target === m || e.target.closest("[data-close]")) closeModals();
}));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModals(); });

init();
