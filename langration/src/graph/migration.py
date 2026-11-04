from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
 
from langration.src.graph.nodes.analyzer_node import analyzer_node
from langration.src.graph.nodes.retriever_node import retriever_node
from langration.src.graph.nodes.rewriter_node import rewriter_node
from langration.src.graph.nodes.verifier_node import route_after_verify, verifier_node
from langration.src.graph.state import MigrationState

NO_CODE_REPLY = ("바꿀 코드를 찾지 못했어요. 옛 LangChain 코드를 ``` 코드 블록으로 붙여 넣고, "
                 "목표 버전(예: 1.x)과 함께 다시 요청해 주세요. 버전 변경 사항이 궁금한 거라면 질문으로 물어봐 주셔도 돼요.")
 
 
def route_after_analyze(state: MigrationState) -> str:
    """분류기가 migration 으로 보냈는데 코드가 없으면(분류기 규칙을 빠져나온 경우) 변환하지 않고 안내로 끝낸다."""
    return "convert" if (state.get("old_code") or "").strip() else "no_code"

def no_code_node(state: MigrationState):
    return {"messages": AIMessage(content=NO_CODE_REPLY)}

def migration():
    builder = StateGraph(MigrationState)

    builder.add_node("analyzer", analyzer_node)
    builder.add_node("no_code", no_code_node)
    builder.add_node("retriever", retriever_node)
    builder.add_node("rewriter", rewriter_node)
    builder.add_node("verifier", verifier_node)

    builder.add_edge(START, "analyzer")
    builder.add_conditional_edges("analyzer", route_after_analyze, {"convert": "retriever", "no_code": "no_code"})
    builder.add_edge("no_code", END)
    builder.add_edge("retriever", "rewriter")
    builder.add_edge("rewriter", "verifier")

    # 검증 결과에 따른 분기: 
    # 실패면 retriever로 되돌아가 근거를 다시 찾기 
    # 근거와 상관없는 오류만 검색 없이 rewriter로 바로 다시 고치기
    builder.add_conditional_edges(
        "verifier", 
        route_after_verify,
        {"retry": "retriever", "rewrite": "rewriter", "done": END})

    app = builder.compile()
    
    return app