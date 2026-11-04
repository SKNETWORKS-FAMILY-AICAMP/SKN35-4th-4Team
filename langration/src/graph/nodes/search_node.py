from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from langration.src.graph.nodes.retriever_node import get_retriever_engine
from langration.src.graph.nodes.rewriter_node import _cut_doc_text
from langration.src.graph.state import MigrationState
from langration.src.prompt.search_prompt import search_prompt, search_user_template

load_dotenv()

SEARCH_K = 6
# 문서 질의응답 검색 설정 (eval/ragas 평가로 정함, 2026-11-04)
# - name_lookup: "Chroma는 어디서 import해요?" 처럼 이름만 물어도 import 대응표를 찾는다
# - era_weight: 코드 변환용 기본값(0.3 문서 ×0.8)은 "StuffDocumentsChain 대신 뭐 써요?" 같은 질문에서
#   정답인 0.3 마이그레이션 가이드를 6위 밖으로 밀어낸다 → search 는 0.9 로 약하게만 1.x 를 우선
SEARCH_RETRIEVE = dict(name_lookup=True, era_weight={"1.x": 1.0, "0.3": 0.9})
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

def format_context(evidences: list[dict]) -> str:
    """근거 목록 → 프롬프트 CONTEXT 블록. 머리글은 "[번호 | source | version]" 형식."""
    if not evidences:
        return "(no results)"

    blocks = []
    for i, e in enumerate(evidences, start=1):
        head = f"[{i} | {e.get('source')} | {e.get('era') or 'unknown'}]"
        location = " > ".join(filter(None, [e.get("title"), e.get("section")]))
        if location:
            head += f" {location}"
        blocks.append(f"{head}\n{_cut_doc_text(e.get('text') or '')}")

    return "\n\n---\n\n".join(blocks)


def search_node(state: MigrationState):
    question = state["messages"][-1].content.strip()
    print(question)
    evidences = [e.to_dict() for e in get_retriever_engine().retrieve(question, k=SEARCH_K, **SEARCH_RETRIEVE)]
    print(f'search_node evidences : {[e["evidence_id"] for e in evidences]}')

    response = llm.invoke(
        [
            SystemMessage(content=search_prompt),
            HumanMessage(content=search_user_template.format(
                context=format_context(evidences),
                question=question,
            )),
        ]
    )

    print(f'search_node response :\n{response}')

    return { 'messages': AIMessage(content=response.content) }

# if __name__ == "__main__":
#     import sys
#     from langchain_core.messages import HumanMessage

#     question = " ".join(sys.argv[1:]) or "랭체인이랑 랭그래프 차이가 뭐야?"
#     result = search_node({"messages": [HumanMessage(content=question)], "classification": "langchain"})
#     print("\n===== answer =====")
#     print(result["messages"].content)