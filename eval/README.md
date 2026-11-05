# 챗봇 평가 (eval)

LangChain 마이그레이션 챗봇이 일반 LLM보다 실제로 나은지 재는 평가 도구입니다. 비교 대상은 시스템 프롬프트 없는 `gpt-4o-mini`(temperature 0)이고, 챗봇의 두 가지 기능을 따로 평가합니다.

| | 코드 변환 평가 | 문서 질의응답 평가 (RAGAS) |
|---|---|---|
| **묻는 것** | 옛 코드를 제대로 바꿔 주는가 | 문서를 찾아 정확히 답하는가 |
| **답 모으기** | `run_eval.py` | `run_ragas.py` |
| **채점** | `score.py` (코드로 채점, LLM 호출 없음) | `score_ragas.py` (RAGAS, 채점 모델 기본 `gpt-4o`) |
| **질문** | `questions.json` 36개 + `route_probes.json` 14개 | `ragas_questions*.json` 세트별 24~30개 |
| **현재 결과** | 없음 ([아래](#이전-결과) 참고) | `results/RAGAS_gpt2-questions/` |

답 모으기와 채점을 나눠 두었으므로, 챗봇을 다시 돌리지 않고 채점만 다시 할 수 있습니다.

## 최근 결과

**2026-11-05, 문서 질의응답 평가, 질문 세트 `gpt2`** (30개: 문서에 답 있음 26 · 없음 4)

문서에 답이 있는 질문의 평균이며, 괄호 안은 점수가 있는 질문 수입니다.

| 지표 | 챗봇 search | 챗봇 e2e | 일반 LLM (search / e2e 채점) |
|---|---:|---:|---:|
| 사실 일치 `factual_correctness` | 0.497 (26) | 0.478 (26) | 0.305 / 0.317 (26) |
| 답 관련성 `answer_relevancy` | 0.505 (26) | 0.498 (26) | 0.535 / 0.535 (26) |
| 근거 충실도 `faithfulness` | 0.829 (25) | 0.885 (21) | - |
| 문서 정밀도 `context_precision` | 0.630 (26) | 0.601 (21) | - |
| 문서 재현율 `context_recall` | 0.692 (26) | 0.690 (21) | - |

- **search**: 모든 질문을 search 경로로 보낸 결과로, 문서 검색과 근거 답변의 품질만 봅니다.
- **e2e**: 실제 화면처럼 그래프 전체를 거친 결과로, 분류기가 고른 경로의 최종 답을 봅니다.
- **일반 LLM의 두 값**: 같은 답을 search · e2e 채점에서 각각 매긴 점수입니다.
- **표본 수**: e2e의 문서 지표는 general로 간 5개가 빠져 21개입니다. search의 근거 충실도는 h27의 점수가 없어 25개입니다.

**읽는 법**

- **사실 일치**는 챗봇이 일반 LLM보다 높습니다 (0.478~0.497 대 0.305~0.317). **답 관련성**은 일반 LLM이 조금 높습니다.
- **문서에 없는 질문 4개**는 문구 검사에서 챗봇 4개 모두 '모른다'로 판정됐고, 일반 LLM은 한 개도 그렇게 판정되지 않았습니다. 이 판정의 한계는 [아래](#결과의-한계)를 참고하세요.
- **분류 결과**는 search 24개, general 6개입니다. general로 간 6개 중 5개(h23 · h24 · h25 · h27 · h29)는 문서에 답이 있는 질문입니다.
- **hit@6**은 재지 못했습니다. 이 세트에는 정답 조각 id(`gold_ids`)가 없습니다.

**search와 e2e를 비교할 때**

위 표는 표본이 달라 직접 비교할 수 없습니다. 두 모드 모두 search 경로로 답한, 답 있는 질문 21개만 비교하면 다음과 같습니다.

| 지표 (같은 21개) | search | e2e |
|---|---:|---:|
| 사실 일치 | 0.532 | 0.508 |
| 답 관련성 | 0.527 | 0.533 |
| 근거 충실도 | 0.805 | 0.885 |
| 문서 정밀도 | 0.617 | 0.601 |
| 문서 재현율 | 0.690 | 0.690 |

이 차이를 분류기 영향이나 품질 차이로 해석하지 마세요. 21개 모두 찾은 문서가 같은데 답이 같은 것은 4개뿐이고, 글자까지 같은 답도 채점할 때마다 점수가 달라집니다 (근거 충실도 h08 0.50 / 0.70, h09 0.75 / 1.00, h19 0.75 / 1.00).

자세한 표는 같은 폴더의 `ragas_scorecard.md`(search)와 `ragas_scorecard_e2e.md`(e2e)에 있습니다.

### 결과의 한계

- `gpt2` 세트의 정답(`reference`)은 ChatGPT가 썼고, 사람이 공식 문서와 대조했다는 기록이 없습니다. 사실 일치 점수는 이 정답에 의존합니다. 대조할 때는 질문마다 첨부된 `evidence_quote`와 `source_url`을 쓰면 됩니다.
- 질문 하나 단위의 점수는 채점 편차가 ±0.3 정도이므로 평균으로 비교합니다. 채점 모델도 `gpt-4o` 하나뿐입니다.
- '모른다' 판정은 답에 "확인할 수 없습니다" 같은 문구가 있는지만 봅니다. 답의 나머지 내용은 검사하지 않으므로 4/4를 완전한 정답으로 읽으면 안 됩니다. 예를 들어 h05는 '모른다'로 판정됐지만, 이어서 0.3 가이드에 나오는 `langchain-cli`를 v1 마이그레이션 도구처럼 안내합니다. 근거 충실도도 1.00으로 나와 이 문제를 잡아내지 못합니다.
- 한국어 답을 영어 프롬프트 기반 지표로 재기 때문에 `answer_relevancy`는 두 시스템 모두 낮게 나오는 경향이 있습니다. 절대값보다 비교에 씁니다.
- '모른다'고 답한 경우 `faithfulness`와 `answer_relevancy`가 낮게 나옵니다. 그래서 문서에 없는 질문은 평균에서 빼고 문구 검사로 따로 봅니다.

### 이전 결과

작업 폴더에는 가장 최근 검증 결과만 둡니다. **코드 변환 평가 결과는 지금 없으므로, 수치가 필요하면 `run_eval.py`부터 다시 실행해야 합니다.** 마지막 결과(2026-11-04)는 `run_eval.py`의 thread_id 문제를 고치기 전에 잰 값입니다.

이전 결과는 git 이력에서 볼 수 있습니다.

```bash
git show 892cf6d:eval/results/scorecard.md          # 코드 변환 평가 (2026-11-04)
git show 892cf6d:eval/results/gpt/ragas_scorecard.md   # RAGAS, gpt 세트 (2026-11-04)
```

## 폴더 구조

```
eval/
├─ run_eval.py · score.py          코드 변환 평가: 답 모으기 · 채점
├─ run_ragas.py · score_ragas.py   문서 질의응답 평가: 답 모으기 · 채점
├─ build_questions.py              questions.json 생성
├─ check_questions.py              questions.json 검사
├─ questions.json                  코드 변환 질문 36개
├─ route_probes.json               분류 확인 질문 14개
├─ ragas_questions*.json           문서 질의응답 질문 세트 3개
└─ results/
   └─ RAGAS_gpt2-questions/
      ├─ raw_ragas[_e2e].jsonl       챗봇 · 일반 LLM의 답, 찾은 문서, 분류 결과
      ├─ ragas_scores[_e2e].jsonl    질문별 점수
      ├─ ragas_summary[_e2e].json    집계
      ├─ ragas_scorecard[_e2e].md    사람이 읽는 결과표
      └─ run_log.txt                 실행 로그
```

파일 이름에 `_e2e`가 붙으면 e2e 모드, 없으면 search 모드 결과입니다.

## 실행하기

**준비**: 프로젝트 루트의 `.env`에 아래 키가 있어야 합니다.

| 키 | 필요한 스크립트 |
|---|---|
| `OPENAI_API_KEY` | `run_eval.py`, `run_ragas.py`, `score_ragas.py` |
| `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE` | `run_eval.py`, `run_ragas.py` (벡터 검색) |

`score.py`는 저장된 답만 읽어 채점하며 LLM을 호출하지 않습니다.

### 문서 질의응답 평가

e2e의 일반 LLM 답은 search 결과를 재사용하므로 **search를 먼저** 실행합니다.

```bash
# 답 모으기
uv run python eval/run_ragas.py --set gpt2
uv run python eval/run_ragas.py --set gpt2 --mode e2e

# 채점
uv run --script eval/score_ragas.py --set gpt2
uv run --script eval/score_ragas.py --set gpt2 --mode e2e
```

| 옵션 | 스크립트 | 뜻 |
|---|---|---|
| `--set <이름>` | 둘 다 | 질문 세트 `ragas_questions_<이름>.json`. 생략하면 `ragas_questions.json` |
| `--mode search\|e2e` | 둘 다 | 평가 방식 (기본 search) |
| `--only r01,r02` | `run_ragas.py` | 일부 질문만 실행 |
| `--fresh` | `run_ragas.py` | 저장된 답을 지우고 처음부터 실행 |
| `--judge <모델>` | `score_ragas.py` | 채점 모델 변경 (기본 `gpt-4o`) |
| `--rescore` | `score_ragas.py` | 저장된 점수를 버리고 다시 채점 |

`score_ragas.py`는 `uv run --script`로 실행합니다. ragas가 팀 `uv.lock`과 버전이 충돌해서, 파일 맨 위에 적힌 의존성으로 환경을 따로 띄웁니다.

**지표**

| 지표 | 챗봇 | 일반 LLM | 뜻 |
|---|---|---|---|
| `factual_correctness` | O | O | 정답과 사실이 일치하는가 |
| `answer_relevancy` | O | O | 질문에 맞는 답인가 |
| `faithfulness` | O | | 답이 찾은 문서에 근거하는가 (환각이 없는가) |
| `context_precision` | O | | 찾은 문서가 정확한가 |
| `context_recall` | O | | 필요한 문서를 찾았는가 |
| `hit@6` | O | | 정답 조각이 찾은 6개 안에 있는가 (LLM 없이 계산, `gold_ids` 필요) |

### 코드 변환 평가

```bash
uv run python eval/run_eval.py     # 챗봇 · 일반 LLM · 분류 3회 (질문 50개, 약 30분)
uv run python eval/score.py        # 채점 → results/summary.json, results/scorecard.md
```

`run_eval.py`의 옵션은 `--only q01,q02`(일부만), `--systems bot,llm,route`(대상 선택), `--fresh`(처음부터)입니다. 결과는 `results/` 바로 아래에 저장되며, 저장 위치를 바꾸는 옵션은 없습니다.

**채점 기준**

- **비교 평가**: 챗봇과 일반 LLM의 답에 같은 공통 8항목을 적용합니다. 8개를 모두 통과해야 '공통 기준 통과'입니다.
  - 항목은 문법, 옛 import 없음, import 실제 존재, 정의 안 된 이름 없음, 결과값 보존, 남은 import 없음, 정답 import 포함, 코드를 실제로 바꿈입니다.
  - 목표가 1.x가 아닌 버전 오가기 질문은 이 중 5개(문법, 정의 안 된 이름, 결과값 보존, 정답 import, 코드 변경)만 봅니다.
- **자체 평가**: 팀이 프롬프트와 코드에 정한 규칙을 실행 기록으로 확인해 21항목, 100점 만점으로 매깁니다. 영역은 분류, 분석, 근거, 고쳐 쓰기, 검증, 답변, 안정성이고, 항목별 목표와 미달 질문 번호가 함께 나옵니다.

### 다시 실행할 때

- 답 모으기는 질문이 끝날 때마다 저장합니다. 중간에 끊겨도 다시 실행하면 끝난 질문은 건너뜁니다.
- `score_ragas.py`도 저장된 점수를 이어서 씁니다. 답을 새로 모았다면 `--rescore`를 붙이세요.
- `--set gpt2`에 `--fresh`나 `--rescore`를 쓰면 `RAGAS_gpt2-questions/`의 기록을 덮어씁니다. **문서 질의응답의 새 검증은 새 폴더에 저장하세요** (아래 참고).

### 새 검증을 추가할 때

이 절차는 `--set`을 쓰는 문서 질의응답 평가에만 해당합니다. 코드 변환 평가와 `--set` 없이 실행한 기본 세트는 결과가 `results/` 바로 아래에 저장되므로, 다시 실행할 때 이전 결과가 있으면 먼저 옮겨 두세요.

1. 질문 파일을 `eval/ragas_questions_<이름>.json`으로 저장합니다.
2. 결과 폴더 이름을 `평가종류_질문세트` 형식으로 정합니다. 예: `RAGAS_gpt3-questions`
3. `run_ragas.py`와 `score_ragas.py` **두 파일 모두**의 `SET_DIRS`에 `"<이름>": "<폴더 이름>"`을 추가합니다.

`SET_DIRS`에 없는 세트의 결과는 `results/<이름>/`에 저장됩니다.

## 질문 세트

| 파일 | 개수 | ID | 구성 | 정답 조각 id (`gold_ids`) |
|---|---:|---|---|---|
| `questions.json` | 36 | q01~q36 | 1.x로 올리기 30 · 버전 오가기 6 | 해당 없음 |
| `route_probes.json` | 14 | p01~p14 | LangChain 지식 5 · 일반 5 · 지시문 섞기 2 · 코드 변환 2 | 해당 없음 |
| `ragas_questions.json` | 24 | r01~r24 | 답 있음 21 · 없음 3 | 있음 |
| `ragas_questions_gpt.json` | 30 | g01~g30 | ChatGPT 작성, 답 있음 27 · 없음 3 | 없음 |
| `ragas_questions_gpt2.json` | 30 | h01~h30 | ChatGPT 작성, 답 있음 26 · 없음 4 | 없음 |

### 코드 변환 질문 (`questions.json`)

실제 사용자가 보낼 법한 자연어 요청과 옛 LangChain 코드를 묶은 질문입니다. 난이도는 쉬움 7 · 중간 19 · 어려움 10입니다.

| 필드 | 뜻 |
|---|---|
| `id` · `type` · `difficulty` | 질문 번호 · 유형 · 난이도 |
| `source_version` · `target_version` | 지금 코드 버전 → 바꿀 버전 |
| `request` | 사용자 요청 문장 (에러 메시지를 붙인 요청, 일부만 바꿔 달라는 요청 등) |
| `code` | 옛 코드 |
| `expected_imports` | 좋은 답이면 들어 있어야 할 import |
| `checks` | 사람이 볼 점검 항목 (예: `.run( 없음 → invoke`, 대화 기억 유지) |

| 유형 | 개수 | 내용 |
|---|---:|---|
| import 경로 · 문서 로더 · 분할기 · 임베딩 · 벡터스토어 | 각 3 | 경로만 바뀐 경우부터 패키지 설치 안내까지 |
| LLMChain → LCEL · 체인 조합 · RAG | 각 3 | 없어진 체인을 `\|`로 다시 짜기 |
| 메모리 · 에이전트 · 도구 | 각 3 | 체크포인터, `create_agent`로 구조 바꾸기 |
| 출력 파서 · 실무 상황 | 각 3 | 구조화 출력, 에러 메시지 설명, 전역 설정, 못 바꾸는 부분 안내 |
| 버전 오가기 | 6 | 1.x에서 0.x로 되돌리기, 0.x 버전 간 이동. 목표 버전에 없는 기능은 못 바꾼다고 표시하고 대안 제시 |

옛 버전끼리(0.0.300 ↔ 0.3.30)는 자주 쓰는 import 경로가 거의 같습니다. 위치가 크게 바뀌는 것은 1.x ↔ 옛 버전 사이와, 나중에 생기거나 없어진 기능입니다.

**수정과 검사**: 질문을 고칠 때는 `build_questions.py`를 고쳐서 다시 생성합니다.

```bash
python eval/build_questions.py
python eval/check_questions.py --py <LangChain 1.x가 설치된 python> --map data/processed/import_map.jsonl --symbols data/raw/symbols
```

검사 항목은 다음과 같습니다.

- 옛 코드가 1.x에서 실제로 깨지는가
- 기대 import가 1.x에서 되는가 (패키지가 없으면 `data/raw/symbols`로 확인)
- 옛 경로가 대응표에 있는가
- 목표가 0.x인 질문은 옛 경로가 목표 버전에 없고 기대 경로가 있는가

마지막 검사는 2026-10-14에 LangChain 1.4.4로 실행했고 36/36 통과했습니다.

화면의 **확인용 예제**(`static/data/examples.json`)는 q01~q30의 사본입니다. `build_questions.py`가 함께 갱신하지 않으므로, 질문을 고치면 이 파일도 맞춰 주세요.

### 문서 질의응답 질문 (`ragas_questions*.json`)

| 필드 | 뜻 |
|---|---|
| `id` · `type` · `difficulty` | 질문 번호 · 유형 · 난이도 |
| `question` | 질문 |
| `reference` | 정답 (사실 일치 채점의 기준) |
| `gold_ids` | 정답이 들어 있는 조각 id. 비어 있으면 hit@6을 재지 않음 |
| `unanswerable` | 문서에 답이 없는 질문 표시 |
| `source_url` · `evidence_quote` | 정답의 출처와 근거 문장 (`gpt`는 `source_url`만, `gpt2`는 둘 다) |
