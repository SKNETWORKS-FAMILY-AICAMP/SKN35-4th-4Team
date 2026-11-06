from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langration.src.graph.state import MigrationState
from langgraph.graph import StateGraph, START, END
from langration.src.graph.nodes.classifier_node import classifier_node
from langration.src.graph.nodes.general_node import general_node
from langration.src.graph.nodes.search_node import search_node
from langration.src.graph.migration import migration

# 대화 맥락 유지 (10-15): 같은 세션(thread_id) 안의 앞 대화를 기억한다.
# - compile(checkpointer=MemorySaver()) 로 thread_id 별 state(messages 등)를 서버 메모리에 남긴다.
# - 화면(src/ui/client.py)이 대화마다 config={"configurable": {"thread_id": "아이디:세션"}} 을 넘긴다.
# - thread_id 없이 부르는 코드(app.py, eval 등)는 DEFAULT_THREAD 하나를 같이 쓴다.
DEFAULT_THREAD = "default"
HISTORY_TURNS = 12       # general 답변에 붙일 앞 대화 메시지 수
HISTORY_CHARS = 300      # 메시지 하나당 최대 글자 (코드가 길어도 프롬프트가 넘치지 않게)

# 기억된 state 에서 질문마다 새로 시작해야 하는 값 (앞 질문의 변환 결과 · 재시도 횟수가 남지 않게)
TURN_RESET = {
    "old_code": "", "analysis": None, "target_version": None, "new_code": "", "changes": [],
    "install_packages": [], "verify_result": None, "attempt": 0, "rewrite_notes": [], "unresolved": [],
    "evidences": [], "shown_evidence_ids": None, "rewrite_failed": False, "route_reason": "", "route_error": "",
    "exclude_ids": None,   # merge_ids reducer 에 None = 비우기 (앞 질문에서 제외한 근거가 다음 변환에 남지 않게)
}


ROUTES = ("migration", "search", "general")


def prompt_classification(state: MigrationState):
    """조건 분기 키. classifier_node 가 이미 세 값으로 정리하지만, 다른 코드가 state 를 넣어도 KeyError 가 안 나게 한 번 더 막는다."""
    route = state.get("classification")
    return route if route in ROUTES else "general"


def _text(m) -> str:
    return m.content if isinstance(m.content, str) else str(m.content)


def classifier_turn(state: MigrationState):
    """classifier_node 로 분류하고 질문별 값을 비운다.
    (11-04: classifier_node 가 마지막 메시지를 question 으로 잡도록 고쳐져서, 여기서 다시 맞추던 코드는 뺐다)"""
    return {**TURN_RESET, **classifier_node(state)}


def general_with_history(state: MigrationState):
    """general_node 는 마지막 메시지만 LLM 에 보낸다. 앞 대화를 '이전 대화'로 묶어 마지막 메시지에 붙여서 넘긴다
    (general_node · 프롬프트는 그대로 두고 맥락만 전달)."""
    msgs = state["messages"]
    history = msgs[:-1][-HISTORY_TURNS:]
    if not history:
        return general_node(state)

    def short(m):
        t = _text(m)
        return t if len(t) <= HISTORY_CHARS else t[:HISTORY_CHARS] + " …"

    lines = [f"{'사용자' if m.type == 'human' else '챗봇'}: {short(m)}" for m in history]
    merged = HumanMessage(content="[이전 대화] 이 대화에서 앞서 사용자와 나눈 내용입니다. 지금 질문에 필요하면 참고해서 답하세요.\n"
                                  + "\n".join(lines) + "\n\n[지금 질문]\n" + _text(msgs[-1]))
    return general_node({**state, "messages": [*msgs[:-1], merged]})


def supervisor():
    builder = StateGraph(MigrationState)

    builder.add_node('classifier', classifier_turn)
    builder.add_node('migration', migration())
    builder.add_node('search', search_node)
    builder.add_node('general', general_with_history)

    builder.add_edge(START, 'classifier')
    builder.add_conditional_edges(
        'classifier',
        prompt_classification,
        {
            'migration': 'migration',
            'search': 'search',
            'general': 'general'
        }
    )
    builder.add_edge('migration', END)
    builder.add_edge('search', END)
    builder.add_edge('general', END)

    app = builder.compile(checkpointer=MemorySaver())

    # thread_id 를 넘기지 않아도(app.py 등) 오류 없이 돌도록 기본 thread 를 묶어 둔다. 넘기면 그 값이 우선.
    return app.with_config(configurable={"thread_id": DEFAULT_THREAD})
