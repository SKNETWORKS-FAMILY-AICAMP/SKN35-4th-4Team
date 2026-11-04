"""RAGAS용 답 모으기 (문서 질의응답).

같은 질문을 우리 챗봇과 일반 LLM에 보내고, 챗봇이 실제로 본 문서 조각(contexts)과 답을 저장한다.
채점은 하지 않는다. 채점은 eval/score_ragas.py (프로젝트와 분리된 환경)에서 한다.

    uv run python eval/run_ragas.py                  # search 경로 평가 (component)
    uv run python eval/run_ragas.py --mode e2e       # 실제 화면처럼 그래프 전체 (분류 → 경로)
    uv run python eval/run_ragas.py --only r01       # 일부만
    uv run python eval/run_ragas.py --fresh          # 저장된 답 지우고 처음부터
    uv run python eval/run_ragas.py --set gpt        # 다른 질문 세트 (ragas_questions_gpt.json → results/gpt/)

두 모드는 묻는 것이 다르다.
- search (component): "문서 검색 + 근거 답변 부품이 얼마나 좋은가". 모든 질문을 search 경로로 보내 검색·답변 품질만 본다.
  search_node 는 찾은 문서를 state 에 남기지 않으므로 같은 함수(검색기 · format_context · search_prompt)를 그대로 불러 contexts 를 함께 저장.
- e2e: "사용자가 실제로 받는 답이 얼마나 좋은가". supervisor 그래프 전체를 돌려 분류기가 고른 경로의 최종 답을 저장.
  search 로 간 질문만 contexts 가 있고(같은 검색을 한 번 더 불러 기록), general · migration 으로 간 질문은 문서 없이 답한 것이다.

저장: eval/results/raw_ragas.jsonl · raw_ragas_e2e.jsonl (질문 하나 끝날 때마다 한 줄, 다시 실행하면 이어서)
일반 LLM: 같은 gpt-4o-mini, temperature 0, 시스템 프롬프트 없이 질문 그대로 (e2e 는 search 모드에서 받은 답을 재사용).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

RES = ROOT / "eval" / "results"


def question_set(name: str) -> tuple[Path, Path]:
    """질문 세트 이름 → (질문 파일, 결과 폴더). 기본 세트는 이름 없음."""
    if not name:
        return ROOT / "eval" / "ragas_questions.json", RES
    return ROOT / "eval" / f"ragas_questions_{name}.json", RES / name


def out_paths(res: Path) -> dict[str, Path]:
    return {"search": res / "raw_ragas.jsonl", "e2e": res / "raw_ragas_e2e.jsonl"}
MODEL = "gpt-4o-mini"


def load_jsonl(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {(r := json.loads(l))["id"]: r for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def search_evidences(engine, question: str) -> list[dict]:
    from langration.src.graph.nodes.search_node import SEARCH_K, SEARCH_RETRIEVE

    return [e.to_dict() for e in engine.retrieve(question, k=SEARCH_K, **SEARCH_RETRIEVE)]


def context_texts(evidences: list[dict]) -> list[str]:
    """프롬프트에 들어간 모양 그대로 조각마다 한 문자열 (RAGAS retrieved_contexts)."""
    from langration.src.graph.nodes.search_node import format_context

    return [format_context([e]).replace("[1 |", f"[{i} |", 1) for i, e in enumerate(evidences, start=1)]


def slim(evidences: list[dict]) -> list[dict]:
    return [{k: e.get(k) for k in ("evidence_id", "source", "title", "section", "new", "match")} for e in evidences]


def plain_answer(plain_llm, q: dict, rec: dict, reuse: dict) -> None:
    t0 = time.time()
    if q["id"] in reuse and reuse[q["id"]].get("llm_answer"):
        rec["llm_answer"], rec["llm_sec"] = reuse[q["id"]]["llm_answer"], reuse[q["id"]].get("llm_sec")
        return
    try:
        rec["llm_answer"] = plain_llm.invoke(q["question"]).content
    except Exception as exc:
        rec["error"] = (rec["error"] or "") + f" llm: {type(exc).__name__}: {exc}"
    rec["llm_sec"] = round(time.time() - t0, 1)


def run_search(q: dict, engine, bot_llm) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage

    from langration.src.graph.nodes.classifier_node import classifier_node
    from langration.src.graph.nodes.search_node import format_context
    from langration.src.prompt.search_prompt import search_prompt, search_user_template

    rec = {"id": q["id"], "mode": "search", "error": None}
    try:
        label = classifier_node({"question": q["question"], "messages": [HumanMessage(content=q["question"])]})
        rec["route"] = label.get("classification")
    except Exception as exc:  # 분류 실패는 기록만
        rec["route"] = f"error: {type(exc).__name__}"

    t0 = time.time()
    try:
        evidences = search_evidences(engine, q["question"])
        reply = bot_llm.invoke([
            SystemMessage(content=search_prompt),
            HumanMessage(content=search_user_template.format(context=format_context(evidences), question=q["question"])),
        ])
        rec.update(bot_answer=reply.content, contexts=context_texts(evidences), retrieved=slim(evidences))
    except Exception as exc:
        rec["error"] = f"bot: {type(exc).__name__}: {exc}"
    rec["bot_sec"] = round(time.time() - t0, 1)
    return rec


def run_e2e(q: dict, engine, graph) -> dict:
    from langchain_core.messages import HumanMessage

    rec = {"id": q["id"], "mode": "e2e", "error": None}
    t0 = time.time()
    try:
        # 질문마다 thread 를 따로 (같은 thread 면 앞 질문이 '이전 대화'로 붙는다)
        state = graph.invoke({"messages": [HumanMessage(content=q["question"])]},
                             config={"configurable": {"thread_id": f"ragas-e2e-{q['id']}-{time.time()}"}})
        rec["route"] = state.get("classification")
        rec["bot_answer"] = next((m.content for m in reversed(state.get("messages", [])) if m.type == "ai"), "")
        if not rec["bot_answer"] and rec["route"] == "migration":
            # migration 경로는 답을 메시지가 아니라 state(new_code · changes)에 담고 화면이 그려 준다 → 같은 내용을 글로
            parts = [f"- {c.get('reason')}" for c in state.get("changes") or [] if c.get("reason")]
            parts += [f"- 못 바꾼 부분: {u}" for u in state.get("unresolved") or []]
            rec["bot_answer"] = ("바뀐 코드:\n```python\n" + (state.get("new_code") or "") + "\n```\n" + "\n".join(parts)).strip()
        if rec["route"] == "search":
            evidences = search_evidences(engine, q["question"])
            rec.update(contexts=context_texts(evidences), retrieved=slim(evidences))
        elif rec["route"] == "migration":
            evs = state.get("evidences") or []
            rec.update(contexts=context_texts(evs), retrieved=slim(evs))
        else:
            rec.update(contexts=[], retrieved=[])
    except Exception as exc:
        rec["error"] = f"bot: {type(exc).__name__}: {exc}"
    rec["bot_sec"] = round(time.time() - t0, 1)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["search", "e2e"], default="search")
    ap.add_argument("--only", help="쉼표로 구분한 질문 id")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--set", default="", help="질문 세트 이름. gpt → eval/ragas_questions_gpt.json, 결과는 eval/results/gpt/")
    args = ap.parse_args()

    from langchain_openai import ChatOpenAI

    from langration.src.graph.nodes.retriever_node import get_retriever_engine

    qfile, res = question_set(args.set)
    OUT = out_paths(res)
    out = OUT[args.mode]
    qs = json.loads(qfile.read_text(encoding="utf-8"))
    if args.only:
        keep = set(args.only.split(","))
        qs = [q for q in qs if q["id"] in keep]
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.fresh and out.exists():
        out.unlink()
    skip = set(load_jsonl(out))
    todo = [q for q in qs if q["id"] not in skip]
    print(f"[ragas:{args.mode}] {qfile.name} → {out.relative_to(ROOT)}")
    print(f"[ragas:{args.mode}] {len(todo)}개 실행 (이미 끝난 {len(qs) - len(todo)}개 건너뜀)")

    engine = get_retriever_engine()
    plain_llm = ChatOpenAI(model=MODEL, temperature=0)
    reuse = load_jsonl(OUT["search"]) if args.mode == "e2e" else {}
    if args.mode == "e2e":
        from langration.src.graph.supervisor import supervisor

        graph = supervisor()
    else:
        bot_llm = ChatOpenAI(model=MODEL, temperature=0)

    for i, q in enumerate(todo, start=1):
        rec = run_e2e(q, engine, graph) if args.mode == "e2e" else run_search(q, engine, bot_llm)
        plain_answer(plain_llm, q, rec, reuse)
        rec["run_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        print(f"  [ragas:{args.mode}] {i}/{len(todo)} {q['id']} route={rec.get('route')} bot {rec['bot_sec']}s"
              f" {rec['error'] or ''}")


if __name__ == "__main__":
    main()
