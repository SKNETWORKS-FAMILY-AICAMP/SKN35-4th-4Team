import json
import re
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from langration.src.graph.state import MigrationState
from langration.src.prompt.classifier_prompt import classifier_prompt
from langration.src.rag.retrieval import IMPORT_MAP_PATH
from langration.src.rag.retrieval.import_lookup import lookup, parse_import_paths

load_dotenv()

ROUTES = ("migration", "search", "general")
DEFAULT_ROUTE = "general"   # LLM 출력이 세 값 밖이거나 호출이 실패하면 (팀 범위: 확실한 것만 search · migration)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 구조 판정
CODE_FENCE = re.compile(r"```.*?```", re.S)
# 문장과 따로 줄을 나눠 쓴 import 줄 (문장 속에 끼워 쓴 import 는 줄 맨 앞이 아니라서 안 걸림)
IMPORT_LINE = re.compile(r"^[ \t]*(from[ \t]+[\w.]+[ \t]+import[ \t]|import[ \t]+[\w.]+)", re.M)
# 식별자 (한글 조사가 붙어도 이름만 잡도록 ASCII 경계)
IDENTIFIER = re.compile(r"(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_]{2,})(?![A-Za-z0-9_])")
# 보통 단어 한 개짜리 이름: 대문자 하나로 시작하고 나머지가 소문자 (Agent, Input, Output ...)
PLAIN_WORD = re.compile(r"^[A-Z][a-z]+$")


def _text(message) -> str:
    return message.content if isinstance(message.content, str) else str(message.content)


def _prose(text: str) -> str:
    """코드 블록을 뺀 문장 (코드 속 이름 · 주석 지시문이 문장 판단에 섞이지 않게)"""
    return CODE_FENCE.sub(" ", text)


def has_code(text: str) -> bool:
    """프롬프트 migration 조건 (1): 코드 블록이나 줄을 나눠 쓴 import. 길이는 따지지 않는다."""
    return bool(CODE_FENCE.search(text) or IMPORT_LINE.search(text))


def old_imports(text: str) -> list[str]:
    """import 대응표에 있고 1.x 에서 경로가 바뀐 import (검색기 lookup() 재사용)"""
    hits = []
    for path in parse_import_paths(text):
        hit = lookup(path)
        if hit and hit.new and hit.new != path:
            hits.append(path)
    return hits


@lru_cache(maxsize=1)
def _legacy_names() -> frozenset[str]:
    """대응표에서 1.x 기준 langchain-classic 으로만 남은 이름 (위 docstring 의 기준으로 거름)"""
    kinds: dict[str, set[str]] = {}
    with IMPORT_MAP_PATH.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("granularity") != "symbol" or not rec["old"].startswith("langchain."):
                continue
            kinds.setdefault(rec["old"].rsplit(".", 1)[-1], set()).add(rec.get("kind"))
    return frozenset(
        name for name, k in kinds.items()
        if k == {"classic_fallback"} and not PLAIN_WORD.match(name)
    )


def legacy_names(text: str) -> list[str]:
    """코드 블록을 뺀 문장에 나온 legacy 이름"""
    names = _legacy_names()
    return [n for n in dict.fromkeys(IDENTIFIER.findall(_prose(text))) if n in names]


# 판단
def rule_route(text: str) -> tuple[str | None, str, dict]:
    """→ (확정 경로 또는 None, 이유, LLM 에 넘길 사실)"""
    facts = {"code": has_code(text), "old_imports": old_imports(text), "legacy_names": legacy_names(text)}
    if not facts["code"] and facts["legacy_names"]:
        return "search", f"R1 옛 API 이름 {facts['legacy_names'][:3]}", facts
    return None, "LLM", facts


def facts_block(facts: dict) -> str:
    """LLM 에 넘기는 사실 요약 (의도 판단은 LLM 몫, 여기서는 사실만 적는다)"""
    return (
        "[확인된 사실 — 시스템이 메시지를 검사한 결과]\n"
        f"- 메시지에 코드가 있음: {'예' if facts['code'] else '아니오'}\n"
        f"- 1.x 에서 경로가 바뀐 옛 import: {', '.join(facts['old_imports'][:5]) or '없음'}\n"
        f"- 문장에 나온 1.x 에서 langchain-classic 으로만 남은 이름: {', '.join(facts['legacy_names'][:5]) or '없음'}\n"
    )


def parse_route(raw: str) -> str | None:
    """LLM 출력 정리: ' Search.' · '"search"' · 'search\\n' → 'search'. 세 값으로 읽을 수 없으면 None (= 해석 실패)"""
    words = (raw or "").strip().strip("`'\".").lower().split()
    word = words[0].strip("`'\".,") if words else ""
    return word if word in ROUTES else None


def llm_route(text: str, facts: dict) -> tuple[str, str]:
    """→ (경로, 실패 내용). 실패 내용은 정상이면 "".
    실패해도 화면은 멈추지 않게 DEFAULT_ROUTE 로 답하고, 실패 사실은 route_error 로 따로 남긴다
    (예외를 여기서 잡기 때문에, 남기지 않으면 평가 스크립트가 실패를 '정상 general' 로 센다)."""
    try:
        response = llm.invoke([
            SystemMessage(content=classifier_prompt),
            HumanMessage(content=facts_block(facts) + "\n[사용자 메시지]\n" + text),
        ])
    except Exception as e:  # API 키 · 네트워크 · 요청 제한 등
        print(f"classifier_node llm error: {e!r}")
        return DEFAULT_ROUTE, f"llm_error: {type(e).__name__}"
    raw = _text(response)
    route = parse_route(raw)
    if route is None:
        return DEFAULT_ROUTE, f"parse_failed: {raw.strip()[:40]!r}"
    return route, ""


def classifier_node(state: MigrationState):
    text = _text(state["messages"][-1])   # 이번 질문 (대화가 쌓여도 마지막 사용자 메시지)

    route, reason, facts = rule_route(text)
    error = ""
    if route is None:
        route, error = llm_route(text, facts)
        reason = f"LLM 실패({error}) → {route}" if error else f"LLM → {route}"
        if route == "migration" and not facts["code"]:
            # R2: 코드 없이 migration → analyzer 가 질문 문장을 코드로 '변환'하는 사고 방지
            route = DEFAULT_ROUTE
            reason = "R2 코드 없음 → LLM 의 migration 을 general 로 내림"

    print(f"classifier_node : {route} ({reason})")
    return {
        "classification": route,
        "question": text if route != "general" else "",
        "route_reason": reason,
        "route_error": error,
    }