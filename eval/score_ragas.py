# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "ragas==0.4.3",
#     "langchain-community==0.4.1",  # ragas 0.4.3 이 0.4.2 에서 지워진 vertexai 모듈을 import 함
#     "openai>=1.40",
#     "python-dotenv>=1",
# ]
# ///
"""RAGAS 채점 (문서 질의응답 · search / e2e 모드).

eval/run_ragas.py 가 저장한 답(결과 폴더의 raw_ragas[_e2e].jsonl)을 읽어 채점만 한다.
ragas 는 팀 프로젝트(uv.lock)와 버전이 부딪혀서 프로젝트에 넣지 않고, 이 파일 맨 위 의존성으로 따로 띄운다.

    uv run --script eval/score_ragas.py                 # 채점 모델 gpt-4o
    uv run --script eval/score_ragas.py --judge gpt-4o-mini
    uv run --script eval/score_ragas.py --rescore       # 저장된 점수 버리고 다시 채점
    uv run --script eval/score_ragas.py --mode e2e      # run_ragas.py --mode e2e 결과 채점 (실제 화면 기준)
    uv run --script eval/score_ragas.py --set gpt       # 다른 질문 세트 (ragas_questions_gpt.json · results/gpt/)

저장: 결과 폴더의 ragas_scores[_e2e].jsonl (질문×채점모델별 점수, 다시 실행하면 이어서) · ragas_summary[_e2e].json · ragas_scorecard[_e2e].md
결과 폴더: 기본 세트는 eval/results/, --set <이름> 은 eval/results/<이름>/ (SET_DIRS 에 있으면 그 폴더. gpt2 → eval/results/RAGAS_gpt2-questions/)
e2e 에서 general 경로로 간 질문은 찾은 문서가 없으므로 answer_relevancy · factual_correctness 만 매긴다.

지표
- 챗봇 (문서에 답이 있는 질문): faithfulness · answer_relevancy · context_precision · context_recall · factual_correctness
- 일반 LLM (같은 질문): answer_relevancy · factual_correctness  (찾은 문서가 없으니 문서 지표는 없음)
- LLM 없이: hit@6 (정답 조각이 찾은 6개 안에 있나, gold_ids 가 있는 세트만) · 분류 결과 · 문서에 없는 질문에 '모른다'고 답했나
  (문항 수는 세트마다 다르다. 기본 세트는 답 있음 21 · 없음 3, gpt2 는 답 있음 26 · 없음 4)
"""
import argparse
import asyncio
import json
import re
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "eval" / "results"
# 결과 폴더 이름이 세트 이름과 다른 경우 (run_ragas.py 에도 같은 표가 있음)
SET_DIRS = {"gpt2": "RAGAS_gpt2-questions"}
load_dotenv(ROOT / ".env")

BOT_METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "factual_correctness"]
LLM_METRICS = ["answer_relevancy", "factual_correctness"]
LABEL = {"faithfulness": "근거 충실도 (환각 없음)", "answer_relevancy": "질문에 맞는 답",
         "context_precision": "찾은 문서 정밀도", "context_recall": "찾은 문서 재현율", "factual_correctness": "정답과 사실 일치"}
ABSTAIN = re.compile(r"확인되지 않|확인할 수 없|정보가 없|정보는 없|찾을 수 없|포함되어 있지 않|나와 있지 않|알 수 없|알지 못|"
                     r"존재하지 않|없는 옵션|지원하지 않|언급이 없|언급되어 있지 않|언급되지 않")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def hit_at_k(q: dict, r: dict) -> bool | None:
    if not q["gold_ids"]:
        return None
    got = {e["evidence_id"] for e in r.get("retrieved", [])}
    news = {e.get("new") for e in r.get("retrieved", [])}
    return bool(got & set(q["gold_ids"])) or bool(news & set(q.get("gold_new", [])))


def build_metrics(judge: str):
    from openai import AsyncOpenAI
    from ragas.embeddings import OpenAIEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (AnswerRelevancy, ContextPrecision, ContextRecall, FactualCorrectness,
                                           Faithfulness)

    client = AsyncOpenAI()
    llm = llm_factory(judge, client=client, temperature=0)
    emb = OpenAIEmbeddings(client=client, model="text-embedding-3-small")
    return {
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=emb),
        "context_precision": ContextPrecision(llm=llm),
        "context_recall": ContextRecall(llm=llm),
        "factual_correctness": FactualCorrectness(llm=llm),
    }


async def score_one(m: dict, name: str, q: dict, answer: str, contexts: list[str]) -> float | None:
    kw = {"faithfulness": dict(user_input=q["question"], response=answer, retrieved_contexts=contexts),
          "answer_relevancy": dict(user_input=q["question"], response=answer),
          "context_precision": dict(user_input=q["question"], reference=q["reference"], retrieved_contexts=contexts),
          "context_recall": dict(user_input=q["question"], retrieved_contexts=contexts, reference=q["reference"]),
          "factual_correctness": dict(response=answer, reference=q["reference"])}[name]
    for attempt in range(3):
        try:
            res = await m[name].ascore(**kw)
            return None if res.value is None else round(float(res.value), 4)
        except Exception as exc:  # 채점 모델 응답 형식 오류 등은 두 번 더 시도
            err = f"{type(exc).__name__}: {exc}"
            await asyncio.sleep(2 * (attempt + 1))
    print(f"    ! {q['id']} {name}: {err[:160]}")
    return None


def suffix(mode: str) -> str:
    return "" if mode == "search" else f"_{mode}"


async def score_all(qs: dict, raw: dict, judge: str, rescore: bool, mode: str) -> list[dict]:
    path = RES / f"ragas_scores{suffix(mode)}.jsonl"
    old = [s for s in load_jsonl(path) if s["judge"] == judge and not rescore]
    have = {s["id"] for s in old}
    todo = [qid for qid in raw if qid not in have and not raw[qid].get("error")]
    print(f"[score_ragas] 채점 모델 {judge} · {len(todo)}개 채점 (저장된 {len(have)}개 재사용)")
    if not todo:
        return old
    m = build_metrics(judge)
    sem = asyncio.Semaphore(4)

    async def one(qid: str) -> dict:
        q, r = qs[qid], raw[qid]
        async with sem:
            t0 = time.time()
            has_ctx = bool(r.get("contexts"))
            if q.get("unanswerable"):
                bot_names = ["faithfulness", "answer_relevancy"] if has_ctx else ["answer_relevancy"]
            else:
                bot_names = BOT_METRICS if has_ctx else ["answer_relevancy", "factual_correctness"]
            llm_names = [] if q.get("unanswerable") else LLM_METRICS
            bot = await asyncio.gather(*(score_one(m, n, q, r["bot_answer"], r["contexts"]) for n in bot_names))
            llm = await asyncio.gather(*(score_one(m, n, q, r["llm_answer"], []) for n in llm_names))
            rec = {"id": qid, "judge": judge, "bot": dict(zip(bot_names, bot)), "llm": dict(zip(llm_names, llm))}
            print(f"  {qid} {round(time.time() - t0)}s bot={rec['bot']} llm={rec['llm']}")
            return rec

    new = await asyncio.gather(*(one(qid) for qid in todo))
    keep = [s for s in load_jsonl(path) if not (s["judge"] == judge and (rescore or s["id"] in todo))]
    with path.open("w", encoding="utf-8") as f:
        for s in keep + list(new):
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    return old + list(new)


def mean(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def fmt(x) -> str:
    return "-" if x is None else f"{x:.2f}"


def summarize(qs: dict, raw: dict, scores: list[dict], judge: str, mode: str) -> dict:
    by = {s["id"]: s for s in scores}
    ans = [qid for qid in raw if not qs[qid].get("unanswerable")]
    una = [qid for qid in raw if qs[qid].get("unanswerable")]
    rows = []
    for qid in raw:
        q, r, s = qs[qid], raw[qid], by.get(qid, {"bot": {}, "llm": {}})
        rows.append({"id": qid, "type": q["type"], "difficulty": q["difficulty"], "route": r.get("route"),
                     "hit": hit_at_k(q, r), "bot": s["bot"], "llm": s["llm"],
                     "bot_abstain": bool(ABSTAIN.search(r.get("bot_answer", ""))) if q.get("unanswerable") else None,
                     "llm_abstain": bool(ABSTAIN.search(r.get("llm_answer", ""))) if q.get("unanswerable") else None,
                     "retrieved": [e["evidence_id"] for e in r.get("retrieved", [])], "gold": q["gold_ids"]})
    R = {x["id"]: x for x in rows}
    overall = {"bot": {n: mean([R[i]["bot"].get(n) for i in ans]) for n in BOT_METRICS},
               "llm": {n: mean([R[i]["llm"].get(n) for i in ans]) for n in LLM_METRICS}}
    types = {}
    for t in dict.fromkeys(qs[i]["type"] for i in ans):
        ids = [i for i in ans if qs[i]["type"] == t]
        types[t] = {"n": len(ids), "hit": mean([None if R[i]["hit"] is None else float(R[i]["hit"]) for i in ids]),
                    **{f"bot_{n}": mean([R[i]["bot"].get(n) for i in ids]) for n in BOT_METRICS},
                    "llm_factual_correctness": mean([R[i]["llm"].get("factual_correctness") for i in ids])}
    routes = {}
    for x in rows:
        routes[x["route"]] = routes.get(x["route"], 0) + 1
    return {"run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "judge": judge, "mode": mode, "n": len(rows), "answerable": len(ans),
            "overall": overall, "hit_at_6": mean([None if R[i]["hit"] is None else float(R[i]["hit"]) for i in ans]), "by_type": types,
            "routes": routes, "unanswerable": {i: {"bot": R[i]["bot_abstain"], "llm": R[i]["llm_abstain"]} for i in una},
            "rows": rows}


def scorecard(s: dict) -> str:
    o = s["overall"]
    how = ("챗봇 = 모든 질문을 search 경로(검색 6개 → search_prompt)로 보낸 답 (검색·답변 부품 평가)" if s["mode"] == "search" else
           "챗봇 = 실제 화면처럼 그래프 전체(분류 → 경로)의 최종 답. 문서 지표는 search·migration 으로 간 질문만, "
           "general 로 간 질문은 답 관련성·사실 일치만 매김")
    L = [f"# RAGAS 평가 결과 · {s['mode']} ({s['run_at']} · 답 gpt-4o-mini · 채점 {s['judge']})", "",
         f"문서 질의응답 질문 {s['n']}개 (문서에 답 있음 {s['answerable']} · 없음 {s['n'] - s['answerable']}). "
         f"{how}. 일반 LLM = 시스템 프롬프트 없는 gpt-4o-mini.", "",
         "## 전체 (문서에 답이 있는 질문)", "", "| 지표 | 우리 챗봇 | 일반 LLM |", "|---|---|---|"]
    for n in BOT_METRICS:
        L.append(f"| {LABEL[n]} `{n}` | {fmt(o['bot'][n])} | {fmt(o['llm'].get(n))} |")
    L.append(f"| 정답 조각이 검색 6개 안에 (LLM 없이) `hit@6` | {fmt(s['hit_at_6'])} | - |")
    L += ["", "## 유형별 (챗봇)", "", "| 유형 | 개수 | hit@6 | 충실도 | 답 관련성 | 문서 정밀도 | 문서 재현율 | 사실 일치 | 일반 LLM 사실 일치 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for t, v in s["by_type"].items():
        L.append(f"| {t} | {v['n']} | {fmt(v['hit'])} | {fmt(v['bot_faithfulness'])} | {fmt(v['bot_answer_relevancy'])} | "
                 f"{fmt(v['bot_context_precision'])} | {fmt(v['bot_context_recall'])} | {fmt(v['bot_factual_correctness'])} | "
                 f"{fmt(v['llm_factual_correctness'])} |")
    L += ["", "## 문서에 없는 질문 · '모른다'고 답했나 (LLM 없이 문구로 확인)", "", "| 질문 | 우리 챗봇 | 일반 LLM | 챗봇 충실도 |", "|---|---|---|---|"]
    rows = {x["id"]: x for x in s["rows"]}
    for i, v in s["unanswerable"].items():
        L.append(f"| {i} | {'✅' if v['bot'] else '❌'} | {'✅' if v['llm'] else '❌'} | {fmt(rows[i]['bot'].get('faithfulness'))} |")
    L += ["", "## 분류 결과 (실제 화면에서 search 경로로 가는가)", "",
          " · ".join(f"{k}: {v}개" for k, v in s["routes"].items()), "",
          "search 가 아닌 질문은 실제 화면에서는 이 답이 아니라 general/migration 경로의 답을 받는다.", "",
          "## 질문별", "", "| id | 유형 | 분류 | hit@6 | 충실도 | 답 관련성 | 문서 정밀도 | 문서 재현율 | 사실 일치 | 일반 LLM 사실 일치 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for x in s["rows"]:
        b = x["bot"]
        L.append(f"| {x['id']} | {x['type']} | {x['route']} | {'-' if x['hit'] is None else ('✅' if x['hit'] else '❌')} | "
                 f"{fmt(b.get('faithfulness'))} | {fmt(b.get('answer_relevancy'))} | {fmt(b.get('context_precision'))} | "
                 f"{fmt(b.get('context_recall'))} | {fmt(b.get('factual_correctness'))} | {fmt(x['llm'].get('factual_correctness'))} |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default="gpt-4o")
    ap.add_argument("--rescore", action="store_true")
    ap.add_argument("--mode", choices=["search", "e2e"], default="search")
    ap.add_argument("--set", default="", help="질문 세트 이름. gpt → eval/ragas_questions_gpt.json, 결과는 eval/results/gpt/")
    args = ap.parse_args()

    global RES
    qfile = ROOT / "eval" / (f"ragas_questions_{args.set}.json" if args.set else "ragas_questions.json")
    if args.set:
        RES = RES / SET_DIRS.get(args.set, args.set)

    qs = {q["id"]: q for q in json.loads(qfile.read_text(encoding="utf-8"))}
    raw = {r["id"]: r for r in load_jsonl(RES / f"raw_ragas{suffix(args.mode)}.jsonl")}
    raw = {qid: raw[qid] for qid in qs if qid in raw}  # 질문 파일 순서
    scores = asyncio.run(score_all(qs, raw, args.judge, args.rescore, args.mode))
    s = summarize(qs, raw, scores, args.judge, args.mode)
    sfx = suffix(args.mode)
    (RES / f"ragas_summary{sfx}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    (RES / f"ragas_scorecard{sfx}.md").write_text(scorecard(s), encoding="utf-8")
    print(f"→ {RES / f'ragas_scorecard{sfx}.md'}")


if __name__ == "__main__":
    main()
