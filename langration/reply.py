"""답 글 만들기 (3차 streamlit_app.py 의 extract_code · summary 를 옮긴 것).

코드 변환 결과(result)에는 글로 된 답이 없어서, 대화에 보여 주고 DB(chat_history.answer)에 저장할 요약 문장을 만든다.
"""

import re

from langration.src.ui.versions import ALL_WITH_NEW

ORDER = ALL_WITH_NEW


def extract_code(text: str) -> str:
    """메시지에서 코드 부분만. ``` 블록이 있으면 그 안, 없으면 전체."""
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.S)
    return "\n".join(blocks) if blocks else text


def summary(result: dict) -> str:
    v = result["verification"]
    note = f"\n\n_{result['note']}_" if result.get("note") else ""
    if result.get("mode") == "graph":                       # 팀 그래프 결과
        n, left = len(result["changes"]), len(result.get("unresolved") or [])
        head = f"{n}군데를 고쳤어요." if n else "바꿀 부분을 찾지 못했어요."
        tail = f" 근거가 부족한 {left}줄은 그대로 두었어요." if left else ""
        check = (f" 검사는 {v['attempts']}회 만에 통과했어요." if v["success"] else
                 f" 다만 {v['attempts']}회 시도 후에도 검사를 통과하지 못했어요.")
        return head + tail + check + " 오른쪽에서 바뀐 줄과 근거를 보세요."
    if not v["success"]:                                     # 임시 결과 (그래프를 못 쓸 때)
        return v["message"] + note
    changes = result["changes"]
    if not changes:
        return f"바꿀 import가 없어요. 쓰인 기능이 LangChain {result['target_version']}에도 그대로 있어요."
    classic = [c for c in changes if c["kind"] == "classic_fallback"]
    lcel = [c for c in classic if "StrOutputParser" in c["new"]]
    missing = [c for c in changes if c["kind"] == "unresolved"]
    extra = ""
    if lcel:
        extra += f" 1.x에서 없어진 기능 {len(lcel)}개는 최신 방식(LCEL)으로 바꿨어요."
    if len(classic) > len(lcel):
        extra += f" {len(classic) - len(lcel)}개는 옛 창고(classic) 위치와 대안을 같이 안내해요."
    if missing:
        extra += f" {len(missing)}개는 {result['target_version']}에 같은 기능이 없어서 그대로 두었어요."
    detected = (result.get("detected") or {}).get("candidates") or [None]
    src = result.get("source_version") or detected[-1]
    back = src in ORDER and result["target_version"] in ORDER and ORDER.index(result["target_version"]) < ORDER.index(src)
    head = f"LangChain {result['target_version']}로 되돌리면서 " if back else ""
    return (f"{head}import {len(changes)}줄을 찾아 고쳤어요.{extra} 검증은 {v['attempts']}회 만에 통과했어요. "
            "오른쪽에서 자세히 보세요." + note)
