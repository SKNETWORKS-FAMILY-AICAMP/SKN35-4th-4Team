# main 배포 전환 가이드

4차 발표까지는 서버(EC2)를 **`dev` 브랜치 기준**으로 배포했습니다 (`deploy/deploy.sh`의 `git pull origin dev`). 최종본을 `main`으로 옮긴 뒤 서버도 `main` 기준으로 바꾸려면 아래 순서를 따릅니다.

- 작성자: 심성욱
- 기준: 2026-11-06 (`dev` → `main` 병합 PR #15 이후)

## 1. 지금 상태

| 항목 | 상태 |
|---|---|
| `main` | `dev` 전체가 병합됨 (PR #15) |
| 서버 배포 | `deploy/deploy.sh`가 `git pull origin dev` → 여전히 `dev` 기준 |
| 서버 저장소 | `~/SKN35-4th-4Team`, `dev` 브랜치를 보고 있을 가능성이 큼 |

## 2. 바꿀 것

### 2-1. `deploy/deploy.sh`

```bash
echo "1) 최신 코드 받기 (main)"
git fetch origin
git checkout main
git pull origin main
```

- `git checkout main`을 먼저 해야 합니다. 서버가 `dev` 브랜치에 있는 채로 `git pull origin main`만 하면 main 내용이 서버의 `dev` 브랜치에 섞입니다.

### 2-2. 문서

| 파일 | 바꿀 곳 |
|---|---|
| `README.md` 10장 실행 방법 | "dev 최신 코드 받기" → "main 최신 코드 받기" |
| `산출물/배포_가이드.md` | `git pull origin dev` 두 곳 → `main` |

## 3. 순서

| 단계 | 누가 | 할 일 |
|---|---|---|
| 1 | 팀 | 앞으로 개발은 `dev`, 배포는 `main`으로 할지 정하기 |
| 2 | 담당자 | 위 2장의 파일을 고쳐 `dev`에 PR → `dev`를 `main`에 PR |
| 3 | ② | 서버에서 한 번만 직접 실행 |
| 4 | ② | 이후에는 `bash deploy/deploy.sh` |
| 5 | 전원 | 배포 주소를 시크릿 창(또는 Ctrl+F5)으로 열어 확인 |

서버에서 한 번만 직접 실행 (3단계)

```bash
cd ~/SKN35-4th-4Team
git status                 # 서버에서 고친 파일이 없는지 확인 (.env는 git에 없으므로 그대로 남음)
git fetch origin
git checkout main
git pull origin main
docker compose up -d --build
docker compose logs --tail 30 web
```

## 4. 확인

| 확인 | 방법 |
|---|---|
| 서버가 main을 보는지 | 서버에서 `git branch --show-current` → `main` |
| 최신 코드인지 | `git log --oneline -1`이 GitHub의 main 최신 커밋과 같은지 |
| 화면이 바뀌었는지 | 배포 주소의 `/static/js/chat.js`를 직접 열어 새 코드인지 |

## 5. 되돌리기

문제가 생기면 서버에서 다시 `dev`로 돌아갑니다.

```bash
git checkout dev
git pull origin dev
docker compose up -d --build
```

## 6. 주의

- `docker compose down -v`는 쓰지 않습니다 (정적 파일 볼륨까지 지워짐).
- 서버의 `.env`는 git에 없으므로 브랜치를 바꿔도 그대로 남습니다.
- `main`과 `dev`가 갈라지지 않게, 고칠 것은 `dev`에 먼저 반영하고 `main`으로 병합합니다.
