import json
import re
import sys
 
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langration.src.graph.state import MigrationState
from langration.src.prompt.analyzer_prompt import analyzer_prompt
from langration.src.rag.import_map import LATEST_VERSION
from langration.src.rag.import_map.version_resolve import normalize_version
 
load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 질문 안의 ``` ... ``` 코드 블록 (python · py · Python · python3 · 언어 표시 없음 등 모두)
CODE_BLOCK = re.compile(r"```[\w+-]*[ \t]*\n(.*?)```", re.DOTALL)
# 코드 블록 없이 줄을 나눠 쓴 import 줄 (classifier_node.has_code 와 같은 기준)
IMPORT_LINE = re.compile(r"^[ \t]*(from[ \t]+[\w.]+[ \t]+import[ \t]|import[ \t]+[\w.]+)", re.M)
# LLM 응답 전체를 감싼 ```json ... ``` 코드펜스
JSON_FENCE = re.compile(r"^\s*```(?:json)?[ \t]*\n(.*?)\n?```\s*$", re.DOTALL)


def parse_json(text: str) -> dict:
    m = JSON_FENCE.match(text)
    data = json.loads(m.group(1) if m else text)
    return data if isinstance(data, dict) else {}
 
def fallback_code(question: str) -> str:
    """LLM 이 old_code 를 못 돌려줬을 때 질문에서 직접 코드를 꺼낸다.
    코드 블록 → 첫 import 줄부터 끝까지 → 없으면 "" (질문 문장 전체를 코드로 쓰지 않는다: r03 처럼 문장을 '변환'하는 사고 방지)"""
    m = CODE_BLOCK.search(question)
    if m:
        return m.group(1).strip()
    m = IMPORT_LINE.search(question)
    return question[m.start():].strip() if m else ""

# LLM이 old_code를 ```python ... ``` 으로 감싸서 돌려준 경우 펜스를 벗기는 거 
def strip_code_fence(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        m = CODE_BLOCK.search(code)
        if m:
            return m.group(1).strip("\n")
    return code

# analyzer가 읽은 목표 버전 → 대표 버전. 비었거나 해석·지원 불가("unknown", "1.x", "0.4" 등)면 최신
def resolve_target_version(text) -> str:
    if not isinstance(text, str) or text.strip().lower() in ("", "unknown", "null", "none"):
        return LATEST_VERSION
    try:
        return normalize_version(text)
    except ValueError as e:
        print(f"[analyzer] 목표 버전 해석 실패 → 최신 {LATEST_VERSION} 기준: {e}", file=sys.stderr)
        return LATEST_VERSION

def analyzer_node(state: MigrationState):
    question = state["question"]

    response = llm.invoke(
        [
            SystemMessage(content=analyzer_prompt),
            HumanMessage(content=state["question"]),
        ]
    )

    print(f'analyzer_node response :\n{response.content}')

    try:
        result = parse_json(response.content)
    except json.JSONDecodeError:
        print("[analyzer] JSON 파싱 실패 → 질문의 코드 블록을 그대로 사용합니다", file=sys.stderr)
        print(f"[analyzer] LLM 원문(앞 300자): {response.content[:300]!r}", file=sys.stderr)
        result = {}
 
    old_code = strip_code_fence(result.get("old_code") or "") or fallback_code(question)
    analysis = result.get("analysis") or {}
    target_version = resolve_target_version(analysis.get("target_version") if isinstance(analysis, dict) else None)

    return { 'old_code': old_code, 'analysis': analysis, 'target_version': target_version }