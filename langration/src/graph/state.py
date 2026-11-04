from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def merge_ids(left: list[str] | None, right: list[str] | None) -> list[str]:
    """재시도마다 verifier가 돌려주는 exclude_ids를 덮어쓰지 않고 누적한다(중복 제거).

    right 가 None 이면 비운다 (새 질문 시작 · supervisor.TURN_RESET 에서 None 을 넣음).
    11-05: 체크포인터(MemorySaver)로 대화를 기억하면서, 앞 질문에서 제외한 근거가 같은 대화의
    다음 변환에도 계속 제외되던 문제가 있었다. 합집합 reducer 라 [] 를 넣어도 지워지지 않아 None 을 '비우기' 신호로 쓴다.
    """
    if right is None:
        return []
    return sorted(set(left or []) | set(right))


class MigrationState(TypedDict):
    # ── 공통 (최상위 그래프)
    messages: Annotated[list[BaseMessage], add_messages]
    classification: str             # migration | search | general (classifier_node 가 세 값으로 정리해서 넣음)
    question: str                   # 이번 사용자 메시지 원문. general 이면 "" (classifier_node)
    route_reason: NotRequired[str]  # 분류 이유: "R1 옛 API 이름 [...]", "R2 코드 없음 ...", "LLM → search" 등. 화면 진행 표시 · 평가 로그용
    route_error: NotRequired[str]   # 분류 LLM 실패 내용 ("" = 정상, "llm_error: AuthenticationError", "parse_failed: '...'"). 실패해도 경로는 general

    # ── migration 하위 그래프 (analyzer → retriever → rewriter → verifier)
    old_code: NotRequired[str]      # 사용자가 질문한 코드. 코드가 없으면 "" → migration.py 가 no_code 로 보냄
    analysis: NotRequired[dict | str]      # 분석 결과 (analyzer는 dict로 넣음)
    target_version: NotRequired[str] # 목표 langchain 대표 버전 (예: "0.2.17"). 질문에 버전 언급 없으면 최신. normalize_version()으로 맞춘 값
    new_code: NotRequired[str]
    evidence_id: NotRequired[str]   # (11-05 확인) 지금 어느 노드도 state 키로 읽거나 쓰지 않음. 근거 ID 는 evidences[*]["evidence_id"] 에 있다
    changes: NotRequired[list[dict]] # Rewriter가 구조화 출력으로 생성한 근거 ID가 포함된 변경 목록 저장
    install_packages: NotRequired[list[str]] # 새 코드가 import하는 langchain 계열 pip 패키지 목록
    verify_result: NotRequired[dict | None] # Verifier 검사 결과 (passed, errors, warnings, summary). errors는 다음 시도의 피드백으로 쓰임. 새 질문 시작 때 None
    attempt: NotRequired[int] # verifier를 거친 횟수 verifier가 1씩 올리고 MAX_ATTEMPTS에 닿으면 종료
    rewrite_notes: NotRequired[list[str]] # 사용자에게 전달할 안내 사항을 LLM이 작성하여 저장
    unresolved: NotRequired[list[dict]] # 제시된 근거만으로는 확신할 수 없을 때 -> 바꾸지 못하고 원문 그대로 둔 코드, 이유
    exclude_ids: NotRequired[Annotated[list[str], merge_ids]] # 재시도할 때 틀린 근거가 누적되도록 merge_ids reducer. None 을 넣으면 비움
    evidences: NotRequired[list[dict]] # Retriever가 찾은 근거 목록 (이번 코드에 매칭된 대응표 항목 + 문서 청크, Evidence.to_dict() 형태)
    shown_evidence_ids: NotRequired[list[str] | None] # Rewriter 프롬프트에 실제로 삽입된 근거 id. None = 아직 없음(verifier 는 None 이면 전체 근거로 대조)
    rewrite_failed: NotRequired[bool] # LLM 호출이 실패했을 때 통과로 처리되지 않도록 플래그 추가