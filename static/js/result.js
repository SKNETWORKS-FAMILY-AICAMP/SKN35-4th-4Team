// ─────────────────────────────────────────────
// 오른쪽 결과 패널 (3차 src/ui/result_view.py · streamlit_app.py show_result 를 옮긴 것)
// 탭: 전후 비교 · 변경 사항 · 근거 · 검사 결과 · 코드 받기 · (안내) · (처리 과정)
// 화면에 글을 넣을 때는 textContent 만 씀 → 답에 HTML 이 섞여 있어도 실행되지 않음
// ─────────────────────────────────────────────
const SOURCE = {   // 근거 출처 → [이름, 설명]
    import_map: ["import 대응표", "2번이 PyPI 패키지 코드에서 뽑은 옛 경로 → 1.x 경로 표 (실제로 import 해 보고 만든 것)"],
    method_map: ["메서드 대응표", "옛 메서드(.run · .predict 등) → 새 메서드 표"],
    latest_docs: ["최신 공식 문서", "LangChain 공식 문서 (docs.langchain.com)"],
    migration_guide: ["옛 마이그레이션 가이드", "0.3.30 시절 공식 마이그레이션 가이드"],
    version_map: ["버전별 도구 목록", "버전마다 실제로 있는 기능 목록을 비교"],
    version_symbols: ["버전별 도구 목록", "버전마다 실제로 있는 기능 목록을 비교"],
    sample: ["예시", "화면 시험용 예시 근거 (팀 데이터가 없을 때)"],
};
const KIND = {     // 근거 종류 → 쉬운 설명
    native: "목표 버전에 같은 기능이 있고, 위치(import 경로)만 바뀌었어요",
    moved: "목표 버전에서 위치가 바뀌었어요",
    same: "목표 버전에도 같은 위치에 그대로 있어요",
    classic_fallback: "1.x 에서는 langchain_classic(옛 창고)에만 남아 있어요. 대안이 있으면 최신 방식으로 바꿔요",
    unresolved: "목표 버전에서 같은 기능을 찾지 못했어요",
    deprecated: "아직 동작하지만 없어질 예정인 옛 메서드예요",
    removed: "목표 버전에서 없어진 메서드예요",
    exists: "목표 버전에서도 그대로 쓸 수 있어요",
};
const CHECKS = [   // [이름, 설명, 오류 · 경고 종류] — 3번 verifier 11가지
    ["문법", "파이썬 문법이 맞는지", ["syntax_error"]],
    ["근거 확인", "이번에 보여 준 근거만 썼는지", ["missing_evidence", "evidence_not_shown", "unknown_evidence_id"]],
    ["변경 기록", "기록 없이 바뀐 줄(환각)이 없는지", ["old_line_mismatch", "change_not_applied", "unrecorded_change"]],
    ["남은 옛 import", "옛 경로가 남지 않았는지", ["legacy_import_remaining", "no_1x_path"]],
    ["import 존재", "새 경로가 목표 버전에 정말 있는지", ["import_failed", "ungrounded_import", "install_required", "import_unverified", "import_not_in_evidence"]],
    ["남은 옛 메서드", ".run() 같은 옛 호출이 남지 않았는지", ["legacy_method_remaining"]],
    ["안 쓰는 import", "필요 없는 import가 남지 않았는지", ["unused_import"]],
    ["반환값 보존", "결과 모양(문자열 등)을 잃지 않았는지", ["return_type_changed"]],
    ["정의 안 된 이름", "실행하면 NameError가 나지 않는지", ["undefined_name"]],
    ["출력 꺼내기", "결과를 ['text']처럼 잘못 꺼내지 않는지", ["invoke_output_subscript"]],
    ["체인 입출력 키", "체인의 입력 · 출력 키가 맞는지", ["chain_io_key"]],
];
const MARKS = "①②③④⑤⑥⑦⑧⑨⑩";


// ── 작은 도우미 ──
function h(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
}
function ids(c) { return (c.evidence_id || "").split(",").map((s) => s.trim()).filter(Boolean); }
function isGraph(r) { return r.mode === "graph"; }

function versionLabel(r) {
    let src = r.source_version;
    const found = (r.detected || {}).candidates || [];
    if (!src && found.length) src = found.length === 1 ? found[0] : `${found[0]} ~ ${found[found.length - 1]}`;
    return src ? `${src} → ${r.target_version}` : `→ ${r.target_version}`;
}

// 답 요약 (3차 summary()): 백엔드가 reply 를 주지 않은 코드 변환 결과에 씀
function summarize(r) {
    const v = r.verification || {};
    if (isGraph(r)) {
        const n = (r.changes || []).length, left = (r.unresolved || []).length;
        const head = n ? `${n}군데를 고쳤어요.` : "바꿀 부분을 찾지 못했어요.";
        const tail = left ? ` 근거가 부족한 ${left}줄은 그대로 두었어요.` : "";
        const check = v.success ? ` 검사는 ${v.attempts}회 만에 통과했어요.` : ` 다만 ${v.attempts}회 시도 후에도 검사를 통과하지 못했어요.`;
        return head + tail + check + " 오른쪽에서 바뀐 줄과 근거를 보세요.";
    }
    if (!v.success) return v.message || "변환하지 못했어요.";
    const changes = r.changes || [];
    if (!changes.length) return `바꿀 import가 없어요. 쓰인 기능이 LangChain ${r.target_version}에도 그대로 있어요.`;
    return `import ${changes.length}줄을 찾아 고쳤어요. 검증은 ${v.attempts}회 만에 통과했어요. 오른쪽에서 자세히 보세요.`;
}


// ── 패널 전체 ──
// ctx: { results: 이 대화의 변환 결과들, reopened, hasMessages, onRetry(request) }
function renderResultPanel(body, ctx) {
    body.replaceChildren();
    const results = ctx.results || [];
    const r = results[results.length - 1];

    if (!r) {
        const none = h("div", "none");
        none.append(icon(ctx.reopened ? "history" : "code"));
        none.append(h("p", "", ctx.reopened
            ? "다시 연 대화는 질문과 답만 저장돼 있어요. 코드를 다시 보내면 결과가 여기에 나와요."
            : ctx.hasMessages
                ? "질문에 대한 답은 왼쪽 대화에 있어요. 코드 변환을 요청하면 여기에 전후 비교와 근거가 나와요."
                : "코드를 넣으면 여기에 전후 비교, 바뀐 줄과 근거가 나와요."));
        body.append(none);
        return;
    }

    // 변환 기록: ① 0.1 → 1.4.5 · ② 1.4.5 → 0.2 (지금 것은 진하게)
    if (results.length > 1) {
        const line = h("div", "history", "변환 기록");
        results.forEach((x, i) => line.append(h(i === results.length - 1 ? "b" : "span", "", `${MARKS[i] || i + 1} ${versionLabel(x)}`)));
        body.append(line);
    }

    // 배지
    const v = r.verification || {};
    const badges = h("div", "badges");
    const ok = h("span", `badge ${v.success ? "ok" : "bad"}`);
    ok.append(icon(v.success ? "check" : "alert"), document.createTextNode(
        v.success ? `검증 통과 · ${v.attempts}회` : isGraph(r) ? `검증 실패 · ${v.attempts}회` : "변환 못 함"));
    const ver = h("span", "badge info");
    ver.append(icon("swap"), document.createTextNode(versionLabel(r)));
    badges.append(ok, ver);
    if (!isGraph(r)) badges.append(h("span", "badge", "임시 결과"));
    body.append(badges);
    if (!isGraph(r)) body.append(h("p", "note", "팀 챗봇에 연결되지 않아 대응표로 만든 임시 결과예요."));

    // 실패: 이유 + 같은 요청으로 다시 시도
    if (!v.success) {
        const alert = h("div", "alert");
        alert.append(h("div", "", v.message || "검사를 통과하지 못했어요."));
        if (isGraph(r) && r.request && ctx.onRetry) {
            const retry = h("button", "btn primary sm");
            retry.append(icon("refresh"), document.createTextNode("같은 요청으로 다시 시도"));
            retry.title = "검사에 실패한 요청을 처음부터 다시 보내요. 챗봇이 근거를 새로 찾아 다시 고쳐요.";
            retry.addEventListener("click", () => ctx.onRetry(r.request));
            alert.append(retry);
        }
        body.append(alert);
        if (!isGraph(r)) return;
    }

    // 탭
    const evs = r.evidences || [];
    const nEv = evs.length || new Set((r.changes || []).flatMap(ids)).size;
    const tabs = [
        ["전후 비교", () => diffView(r.original_code || "", r.migrated_code || "")],
        [`변경 사항 ${(r.changes || []).length}`, () => changesView(r.changes || [], evs)],
        [`근거 ${nEv}`, () => evidenceView(evs, r.changes || [])],
        ["검사 결과", () => checksView(r)],
        ["코드 받기", () => downloadView(r)],
    ];
    if ((r.unresolved || []).length || (r.install_packages || []).length || (r.notes || []).length || (r.warnings || []).length) {
        tabs.push(["안내", () => notesView(r)]);
    }
    if ((r.steps || []).length) tabs.push(["처리 과정", () => stepsView(r.steps, r.seconds, true)]);

    const bar = h("div", "tabs");
    const pane = h("div", "stack");
    tabs.forEach(([name, draw], i) => {
        const b = h("button", "", name);
        b.type = "button";
        b.addEventListener("click", () => {
            bar.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
            b.classList.add("on");
            pane.replaceChildren(draw());
        });
        bar.append(b);
        if (i === 0) setTimeout(() => b.click());
    });
    body.append(bar, pane);
}


// ── 전후 비교: 줄 단위 비교 (difflib 처럼 같은 줄을 맞추고 나머지를 색칠) ──
function lineDiff(a, b) {
    const n = a.length, m = b.length;
    const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const dels = new Set(), adds = new Set();
    let i = 0, j = 0;
    while (i < n && j < m) {
        if (a[i] === b[j]) { i++; j++; }
        else if (dp[i + 1][j] >= dp[i][j + 1]) dels.add(i++);
        else adds.add(j++);
    }
    while (i < n) dels.add(i++);
    while (j < m) adds.add(j++);
    return { dels, adds };
}

function diffView(before, after) {
    const a = before.split("\n"), b = after.split("\n");
    const { dels, adds } = lineDiff(a, b);
    const wrap = h("div", "stack");
    const grid = h("div", "diff");
    grid.append(codePane("변경 전", a, dels, "del"), codePane("변경 후", b, adds, "add"));
    const legend = h("div", "legend");
    [["#ef4444", `지운 줄 ${dels.size}`], ["#22c55e", `새 줄 ${adds.size}`]].forEach(([c, t]) => {
        const s = h("span"); const sw = h("span", "sw"); sw.style.background = c; s.append(sw, document.createTextNode(t)); legend.append(s);
    });
    wrap.append(grid, legend);
    return wrap;
}

function codePane(title, lines, marks, cls) {
    const pane = h("div", "pane");
    pane.append(h("h4", "", title));
    const code = h("div", "code");
    lines.forEach((t, i) => {
        const ln = h("div", `ln ${marks.has(i) ? cls : ""}`);
        ln.append(h("span", "no", i + 1), document.createTextNode(t || " "));
        code.append(ln);
    });
    pane.append(code);
    return pane;
}


// ── 변경 사항: 옛 줄(빨강) → 새 줄(초록), 바꾼 까닭, 근거 출처 ──
function changesView(changes, evidences) {
    if (!changes.length) return h("div", "empty", "바뀐 줄이 없어요.");
    const bySrc = Object.fromEntries(evidences.map((e) => [e.evidence_id, e.source]));
    const list = h("div", "stack");
    changes.forEach((c, k) => {
        const card = h("div", "card");
        card.style.animationDelay = `${k * 0.05}s`;
        const head = h("div", "head");
        head.append(h("span", "num", k + 1));
        let names = [...new Set(ids(c).map((i) => bySrc[i]).filter(Boolean).map((s) => (SOURCE[s] || [s])[0]))];
        if (!names.length && c.source) names = [(SOURCE[c.source] || [c.source])[0]];
        names.forEach((n) => head.append(h("span", "chip", n)));
        if (!names.length && !ids(c).length) head.append(h("span", "chip gray", "근거 없음"));
        card.append(head);
        const old = c.old || "", nw = c.new || "";
        if (old && old !== "(새 줄)") { const r = h("div", "row del"); r.append(h("b", "", "−"), document.createTextNode(old)); card.append(r); }
        if (nw && nw !== "(삭제)") { const r = h("div", "row add"); r.append(h("b", "", "+"), document.createTextNode(nw)); card.append(r); }
        if (nw === "(삭제)") card.append(h("div", "src", "이 줄은 지웠어요"));
        if (c.reason) card.append(h("div", "why", c.reason));
        if (c.alternative) { const s = h("div", "src", "대안: "); s.append(h("span", "m", c.alternative)); card.append(s); }
        list.append(card);
    });
    return list;
}


// ── 근거: 출처 · 옛 경로 → 새 경로 · 종류 · 문서 링크 · 원문 ──
function evidenceView(evidences, changes) {
    const used = {};
    changes.forEach((c, n) => ids(c).forEach((i) => (used[i] = used[i] || []).push(n + 1)));
    let evs = evidences;
    if (!evs.length) {                                    // 임시 결과: 바뀐 줄에 적힌 근거만으로
        evs = Object.keys(used).map((i) => {
            const c = changes.find((x) => ids(x).includes(i)) || {};
            return { evidence_id: i, source: c.source, kind: c.kind };
        });
    }
    if (!evs.length) return h("div", "empty", "근거가 없어요.");
    const first = (e) => Math.min(...(used[e.evidence_id] || [99]));
    const list = h("div", "stack");
    [...evs].sort((a, b) => first(a) - first(b)).forEach((e, k) => {
        const [name, desc] = SOURCE[e.source] || [e.source || "근거", ""];
        const card = h("div", "card");
        card.style.animationDelay = `${k * 0.05}s`;
        const head = h("div", "head");
        head.append(h("span", "chip", name));
        const lines = used[e.evidence_id];
        head.append(h("span", "src", lines ? `변경 사항 ${lines.join(", ")}번의 근거` : "검색됐지만 변경에는 쓰이지 않음"));
        card.append(head);
        if (desc) card.append(h("div", "src", desc));
        if (e.old || e.new) card.append(h("div", "row plain", `${e.old || ""}  →  ${e.new || "(목표 버전에 없음)"}`));
        if (KIND[e.kind]) card.append(h("div", "src", KIND[e.kind]));
        if (e.alternative) { const s = h("div", "src", "대안: "); s.append(h("span", "m", e.alternative)); card.append(s); }
        if (e.title || e.url) {
            const s = h("div", "src", "문서: ");
            const title = [e.title, e.section].filter(Boolean).join(" · ") || e.url;
            if (e.url && /^https?:\/\//.test(e.url)) {
                const a = h("a", "", `${title} ↗`); a.href = e.url; a.target = "_blank"; a.rel = "noopener"; s.append(a);
            } else s.append(document.createTextNode(title));
            card.append(s);
        }
        if (e.text) {
            const d = h("details"); d.append(h("summary", "", "근거 원문 보기"), h("pre", "", e.text.slice(0, 700))); card.append(d);
        }
        list.append(card);
    });
    return list;
}


// ── 검사 결과: 11가지를 통과 · 경고 · 실패로 ──
function checksView(r) {
    const ck = r.checks || {};
    if (!ck.done) return h("div", "empty", "임시 결과라 검사 정보가 없어요. 팀 챗봇에 연결되면 11가지 검사 결과가 나와요.");
    const errs = ck.errors || [], warns = ck.warnings || [];
    const known = new Set(CHECKS.flatMap((c) => c[2]));
    let nOk = 0, nWarn = 0, nBad = 0;
    const grid = h("div", "checks");
    CHECKS.forEach(([name, desc, types], k) => {
        const bad = errs.filter((x) => types.includes(x.type)), warn = warns.filter((x) => types.includes(x.type));
        const [st, label] = bad.length ? ["bad", "실패"] : warn.length ? ["warn", "경고"] : ["ok", "통과"];
        nOk += st === "ok"; nWarn += st === "warn"; nBad += st === "bad";
        const card = h("div", "ck-card");
        card.style.animationDelay = `${k * 0.03}s`;
        const t = h("div", "t", `${k + 1}. ${name}`);
        t.append(h("span", `st ${st}`, label));
        card.append(t, h("div", "d", desc));
        [...bad, ...warn].slice(0, 3).forEach((x) => card.append(h("div", "m", `· ${x.message || ""}`)));
        grid.append(card);
    });
    const wrap = h("div", "stack");
    const sum = h("div", "sum");
    [[nOk, "통과"], [nWarn, "경고"], [nBad, "실패"], [(r.verification || {}).attempts, "회 시도"]].forEach(([n, t]) => {
        const d = h("div"); d.append(h("b", "", n), document.createTextNode(t)); sum.append(d);
    });
    wrap.append(sum, grid);
    const other = [...errs, ...warns].filter((x) => !known.has(x.type));
    if (other.length) {
        const card = h("div", "card"); card.append(h("div", "why", "그 밖의 메시지"));
        other.slice(0, 3).forEach((x) => card.append(h("div", "src", `· ${x.message || ""}`)));
        wrap.append(card);
    }
    wrap.append(h("p", "note", "마지막 시도 기준 · 오류는 다시 고칠 이유가 되고, 경고는 결과에 표시만 해요."));
    return wrap;
}


// ── 코드 받기: 복사 · .py · 변경 리포트 .md · 먼저 설치할 패키지 ──
function downloadView(r) {
    const wrap = h("div", "stack");
    wrap.append(h("p", "note", "바뀐 코드예요. 오른쪽 위 버튼으로 복사할 수 있어요."));
    const box = h("div", "codebox");
    box.append(h("pre", "", r.migrated_code || ""));
    const copy = h("button", "btn line sm");
    copy.append(icon("copy"), document.createTextNode("복사"));
    copy.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(r.migrated_code || ""); toast("코드를 복사했어요"); }
        catch (e) { toast("복사하지 못했어요. 직접 선택해 복사해 주세요"); }
    });
    box.append(copy);
    const acts = h("div", "actions");
    acts.append(
        saveButton("코드 내려받기 (.py)", "migrated.py", r.migrated_code || "", "text/x-python"),
        saveButton("변경 리포트 내려받기 (.md)", "migration_report.md", reportMd(r), "text/markdown"),
    );
    wrap.append(box, acts);
    if ((r.install_packages || []).length) {
        wrap.append(h("p", "note", "먼저 설치할 패키지"));
        const p = h("div", "codebox"); p.append(h("pre", "", `pip install ${r.install_packages.join(" ")}`)); wrap.append(p);
    }
    return wrap;
}

function saveButton(label, filename, text, type) {
    const b = h("button", "btn line sm");
    b.append(icon("download"), document.createTextNode(label));
    b.addEventListener("click", () => {
        const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
        const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        toast(`${filename} 을 내려받았어요`);
    });
    return b;
}

function reportMd(r) {
    const v = r.verification || {};
    const out = ["# LangChain 버전 변경 리포트", "", `- 버전: ${r.source_version || "?"} → ${r.target_version}`,
        `- 검사: ${v.success ? "통과" : "실패"} (${v.attempts}회 시도)`, ""];
    if ((r.install_packages || []).length) out.push("## 설치할 패키지", "", "```bash", `pip install ${r.install_packages.join(" ")}`, "```", "");
    out.push("## 변경 사항", "");
    (r.changes || []).forEach((c, n) => {
        out.push(`### ${n + 1}. ${c.reason || ""}`.trimEnd(), "", "```diff");
        if (c.old && c.old !== "(새 줄)") out.push(`- ${c.old}`);
        if (c.new && c.new !== "(삭제)") out.push(`+ ${c.new}`);
        out.push("```", "");
    });
    if ((r.unresolved || []).length) out.push("## 못 바꾼 줄", "", ...r.unresolved.map((u) => `- \`${u.code || ""}\`: ${u.reason || ""}`), "");
    out.push("## 바뀐 코드", "", "```python", (r.migrated_code || "").trimEnd(), "```", "");
    return out.join("\n");
}


// ── 안내: 못 바꾼 줄 · 설치할 패키지 · 그래프 안내 · 검사 경고 ──
function notesView(r) {
    const list = h("div", "stack");
    (r.unresolved || []).forEach((u) => {
        const c = h("div", "card"); const hd = h("div", "head"); hd.append(h("span", "chip red", "못 바꾼 줄"));
        c.append(hd, h("div", "row del", u.code || ""), h("div", "why", u.reason || "")); list.append(c);
    });
    if ((r.install_packages || []).length) {
        const c = h("div", "card"); const hd = h("div", "head"); hd.append(h("span", "chip", "설치할 패키지"));
        c.append(hd, h("div", "row plain", `pip install ${r.install_packages.join(" ")}`)); list.append(c);
    }
    (r.notes || []).forEach((n) => { const c = h("div", "card"); const hd = h("div", "head"); hd.append(h("span", "chip", "안내")); c.append(hd, h("div", "", n)); list.append(c); });
    (r.warnings || []).forEach((w) => { const c = h("div", "card"); const hd = h("div", "head"); hd.append(h("span", "chip gray", "검사 경고")); c.append(hd, h("div", "src", w)); list.append(c); });
    return list;
}


// ── 처리 과정 (진행 상자 · 답 위 기록 · 결과 탭이 같이 씀) ──
function stepRow(s) {
    const row = h("div", "step");
    const failed = /실패/.test(s.done || "");
    const ck = h("span", `ck ${failed ? "fail" : ""}`); ck.append(icon(failed ? "x" : "check"));
    const box = h("div");
    const done = h("div", "done");
    inlineCode(done, s.done || "");
    if (s.sec !== undefined && s.sec !== null) done.append(h("span", "sec", `· ${Math.round(s.sec)}초`));
    box.append(done);
    if ((s.details || []).length) {
        const ul = h("ul", "det");
        s.details.forEach((d) => { const li = h("li"); inlineCode(li, String(d)); ul.append(li); });
        box.append(ul);
    }
    row.append(ck, box);
    return row;
}

function stepsView(steps, seconds, withNote = true) {
    const list = h("div", "list");
    if (withNote) list.append(h("p", "note", "그래프가 실제로 지나간 단계예요. 실패한 회차와 다시 시도한 과정도 그대로 남아요."));
    steps.forEach((s) => list.append(stepRow(s)));
    if (seconds !== undefined && seconds !== null) list.append(h("div", "total", `전체 ${Math.round(seconds)}초 · ${steps.length}단계`));
    return list;
}

// `코드` 부분만 <code> 로
function inlineCode(parent, text) {
    String(text).split("`").forEach((part, i) => parent.append(i % 2 ? h("code", "", part) : document.createTextNode(part)));
}
