// ─────────────────────────────────────────────
// 채팅 화면
//   새 대화      → POST API.sessions        → { ok, session_id }
//   질문 · 예제  → POST API.chat            → { ok, route, answer, result }
//   내 대화 목록 → GET  API.sessions        → { ok, sessions: [{ session_id, title, last_at }] }
//   대화 열기    → GET  API.session(id)     → { ok, messages: [{ question, answer, created_at }] }
//   로그아웃     → POST API.logout          → { ok }
// ─────────────────────────────────────────────

// 3차 확인용 예제 중 일부 (예제 보내기도 일반 질문과 같은 채팅 API 를 씀)
const EXAMPLES = [
    {
        title: "LLMChain → LCEL",
        text: "LLMChain 쓰는 옛날 코드예요. 1.x로 바꿔 주세요.\n\n```python\nfrom langchain.llms import OpenAI\nfrom langchain.chains import LLMChain\nfrom langchain.prompts import PromptTemplate\n\nprompt = PromptTemplate.from_template(\"{word}의 반대말은?\")\nchain = LLMChain(llm=OpenAI(temperature=0), prompt=prompt)\nprint(chain.run(word=\"크다\"))\n```",
    },
    {
        title: "Document · ChatPromptTemplate",
        text: "Document 만들어서 쓰는 부분인데 0.3 코드예요. 1.x로 바꿔 주세요.\n\n```python\nfrom langchain.schema import Document\nfrom langchain.prompts import ChatPromptTemplate\n\ndocs = [Document(page_content=\"LangChain 1.0 출시\", metadata={\"src\": \"news\"})]\nprompt = ChatPromptTemplate.from_messages([(\"system\", \"요약가\"), (\"human\", \"{text}\")])\nprint(prompt.format_messages(text=docs[0].page_content))\n```",
    },
    {
        title: "LangChain 질문 (설명)",
        text: "LangChain 1.x에서 create_agent는 무엇이고 initialize_agent와 뭐가 달라요?",
    },
];

// 화면 요소
const el = {
    messages: document.getElementById("messages"),
    form: document.getElementById("chat-form"),
    input: document.getElementById("chat-input"),
    send: document.getElementById("chat-send"),
    result: document.getElementById("result"),
    sessions: document.getElementById("session-list"),
    newChat: document.getElementById("new-chat"),
    exampleSelect: document.getElementById("example-select"),
    exampleText: document.getElementById("example-text"),
    exampleSend: document.getElementById("example-send"),
    logout: document.getElementById("logout"),
};

// 화면이 기억하는 값 (상태)
const state = {
    sessionId: null,      // 지금 대화 번호 (없으면 첫 질문 전에 새로 받음)
    busy: false,          // 답을 기다리는 중인지
};


// ─────────────── 1. 처음 열렸을 때 ───────────────
function init() {
    EXAMPLES.forEach((ex, i) => el.exampleSelect.add(new Option(ex.title, i)));
    showExample();
    loadSessions();
}


// ─────────────── 2. 질문 보내기 ───────────────
el.form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendQuestion(el.input.value);
});

// Enter = 전송, Shift+Enter = 줄 바꿈
el.input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        el.form.requestSubmit();
    }
});

el.exampleSelect.addEventListener("change", showExample);
el.exampleSend.addEventListener("click", () => sendQuestion(EXAMPLES[el.exampleSelect.value].text));

async function sendQuestion(text) {
    text = text.trim();
    if (!text || state.busy) return;

    setBusy(true);
    clearEmpty(el.messages);
    addBubble("user", text);
    el.input.value = "";
    const waiting = addBubble("bot", "답변을 만드는 중이에요... (코드 변환은 수십 초 걸릴 수 있어요)", "loading");

    // 대화 번호가 없으면 먼저 받음 (새 대화 버튼을 안 누르고 바로 질문한 경우)
    if (!state.sessionId) {
        const created = await callApi(API.sessions, { method: "POST" });
        if (!created.ok) return failBubble(waiting, created.error);
        state.sessionId = created.session_id;
    }

    const data = await callApi(API.chat, {
        method: "POST",
        body: { session_id: state.sessionId, message: text },
    });
    if (!data.ok) return failBubble(waiting, data.error);

    waiting.remove();
    addBubble("bot", data.answer || "(답변이 비어 있어요)");
    renderResult(data.result);          // 코드 변환이 아니면 result 는 null
    setBusy(false);
    loadSessions();                     // 첫 질문이면 목록에 새 대화가 생김
}

function failBubble(bubble, error) {
    bubble.classList.remove("loading");
    bubble.classList.add("error");
    bubble.textContent = `⚠️ ${error || "답변을 받지 못했어요."} 같은 질문을 다시 보내 보세요.`;
    setBusy(false);
}

function setBusy(busy) {
    state.busy = busy;
    el.send.disabled = busy;
    el.exampleSend.disabled = busy;
    el.send.textContent = busy ? "처리 중" : "전송";
}


// ─────────────── 3. 새 대화 · 이전 대화 ───────────────
el.newChat.addEventListener("click", async () => {
    if (state.busy) return;
    const data = await callApi(API.sessions, { method: "POST" });
    if (!data.ok) return alert(data.error);
    state.sessionId = data.session_id;
    resetScreen();
    markActive();
});

async function loadSessions() {
    const data = await callApi(API.sessions);
    el.sessions.innerHTML = "";
    if (!data.ok) return addEmpty(el.sessions, data.error);
    if (!data.sessions.length) return addEmpty(el.sessions, "아직 대화가 없어요.");

    data.sessions.forEach((s) => {
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = s.title || "(제목 없음)";
        btn.title = s.title || "";
        btn.dataset.id = s.session_id;
        btn.addEventListener("click", () => openSession(s.session_id));
        li.append(btn);
        el.sessions.append(li);
    });
    markActive();
}

async function openSession(id) {
    if (state.busy) return;
    const data = await callApi(API.session(id));
    if (!data.ok) return alert(data.error);

    state.sessionId = id;
    resetScreen();
    clearEmpty(el.messages);
    data.messages.forEach((m) => {             // 질문 · 답변만 복원 (결과 패널은 3차처럼 비움)
        addBubble("user", m.question);
        if (m.answer) addBubble("bot", m.answer);
    });
    markActive();
}

function markActive() {
    el.sessions.querySelectorAll("button").forEach((b) => {
        b.classList.toggle("active", b.dataset.id === state.sessionId);
    });
}

function resetScreen() {
    el.messages.innerHTML = "";
    addEmpty(el.messages, "옛 LangChain 코드를 붙여 넣거나, 왼쪽 예제를 보내 보세요.", "p");
    renderResult(null);
}


// ─────────────── 4. 로그아웃 ───────────────
el.logout.addEventListener("click", async () => {
    await callApi(API.logout, { method: "POST" });
    window.location.href = PAGE.login;
});


// ─────────────── 5. 결과 패널 ───────────────
function renderResult(result) {
    el.result.innerHTML = "<h2>결과</h2>";
    if (!result) {
        addEmpty(el.result, "코드 변환 결과가 여기에 나와요.", "p");
        return;
    }

    // 검증 배지
    const v = result.verification || {};
    const badges = document.createElement("div");
    badges.className = "badges";
    badges.append(
        badge(v.success ? `✅ 검증 통과 · ${v.attempts || 1}회` : `❌ 검증 실패 · ${v.attempts || 1}회`, v.success ? "ok" : "fail"),
        badge(`목표 버전 ${result.target_version || "1.x"}`),
    );
    el.result.append(badges);
    if (!v.success && v.message) {
        const why = document.createElement("p");
        why.className = "message";
        why.textContent = `실패 이유: ${v.message}`;
        el.result.append(why);
    }

    // 탭 3개: 버튼을 누르면 아래 내용만 바꿔 끼움
    const changes = result.changes || [];
    const tabs = [
        ["전후 비교", () => diffView(result.original_code || "", result.migrated_code || "", changes)],
        [`변경 사항 ${changes.length}`, () => changesView(changes)],
        [`근거 ${changes.filter((c) => c.evidence_id).length}`, () => evidenceView(changes)],
    ];
    const bar = document.createElement("div");
    bar.className = "tabs";
    const body = document.createElement("div");
    tabs.forEach(([name, draw], i) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = name;
        btn.addEventListener("click", () => {
            bar.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            body.replaceChildren(draw());
        });
        bar.append(btn);
        if (i === 0) btn.click();                 // 처음엔 첫 탭
    });
    el.result.append(bar, body);
}

// 전후 비교: 바뀐 줄에 색칠
function diffView(before, after, changes) {
    const oldLines = new Set(changes.map((c) => (c.old || "").trim()));
    const newLines = new Set(changes.map((c) => (c.new || "").trim()));
    const wrap = document.createElement("div");
    wrap.className = "diff";
    wrap.append(codeBox("변경 전", before, oldLines, "old"), codeBox("변경 후", after, newLines, "new"));
    return wrap;
}

function codeBox(title, code, marked, cls) {
    const box = document.createElement("div");
    const h = document.createElement("h4");
    h.textContent = title;
    const pre = document.createElement("pre");
    pre.className = "code";
    code.split("\n").forEach((line) => {
        const span = document.createElement("span");
        span.textContent = line || " ";
        if (marked.has(line.trim())) span.classList.add(cls);
        pre.append(span);
    });
    box.append(h, pre);
    return box;
}

// 변경 사항 표
function changesView(changes) {
    if (!changes.length) return emptyText("바뀐 줄이 없어요.");
    return table(["옛 줄", "새 줄", "종류"], changes.map((c) => [code(c.old), code(c.new), kindLabel(c)]));
}

// 근거 표
function evidenceView(changes) {
    const rows = changes.filter((c) => c.evidence_id);
    if (!rows.length) return emptyText("붙은 근거가 없어요.");
    return table(["근거 ID", "출처", "바뀐 줄"], rows.map((c) => [code(c.evidence_id), c.source || "-", code(c.new)]));
}

function kindLabel(c) {
    const names = { native: "최신 방식", classic_fallback: "옛 창고(classic)", unresolved: "대응 없음" };
    const text = names[c.kind] || c.kind || "-";
    return c.alternative ? `${text} · 대안: ${c.alternative}` : text;
}


// ─────────────── 6. 작은 도우미 함수 ───────────────
// 말풍선 추가. 답변 안의 ```코드``` 는 코드 상자로, 나머지는 글자 그대로
// (textContent 만 써서 답변에 HTML 이 섞여 있어도 화면에 실행되지 않게 함)
function addBubble(who, text, extra = "") {
    const div = document.createElement("div");
    div.className = `bubble ${who} ${extra}`.trim();
    text.split(/```(?:\w+)?\n?/).forEach((part, i) => {
        if (!part) return;
        const node = document.createElement(i % 2 ? "pre" : "div");
        node.textContent = part;
        if (i % 2 === 0) node.style.whiteSpace = "pre-wrap";
        div.append(node);
    });
    el.messages.append(div);
    el.messages.scrollTop = el.messages.scrollHeight;      // 맨 아래로 스크롤
    return div;
}

function badge(text, cls = "") {
    const span = document.createElement("span");
    span.className = `badge ${cls}`.trim();
    span.textContent = text;
    return span;
}

function table(heads, rows) {
    const t = document.createElement("table");
    t.className = "changes";
    const tr = t.insertRow();
    heads.forEach((h) => { const th = document.createElement("th"); th.textContent = h; tr.append(th); });
    rows.forEach((cells) => {
        const r = t.insertRow();
        cells.forEach((c) => { const td = r.insertCell(); typeof c === "string" ? (td.textContent = c) : td.append(c); });
    });
    return t;
}

function code(text) {
    const c = document.createElement("code");
    c.textContent = text || "-";
    return c;
}

function emptyText(text) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = text;
    return p;
}

function addEmpty(parent, text, tag = "li") {
    const node = document.createElement(tag);
    node.className = "empty";
    node.textContent = text;
    parent.append(node);
}

function clearEmpty(parent) {
    parent.querySelectorAll(":scope > .empty").forEach((n) => n.remove());
}

function showExample() {
    el.exampleText.textContent = EXAMPLES[el.exampleSelect.value].text.split("\n")[0];
}

init();
