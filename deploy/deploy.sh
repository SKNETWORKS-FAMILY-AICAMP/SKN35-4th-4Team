# 빌드부터 실행까지 자동화하는 파일 (EC2 에서 실행)
# 사용법(서버): bash deploy/deploy.sh
# 미리 준비: 저장소 폴더에 .env (OPENAI · CHROMA · TIDB 값), 보안 그룹 80 포트 열기
set -e

cd ~/SKN35-4th-4Team

echo "1) 최신 코드 받기"
git pull origin dev

echo "2) web(Django + Gunicorn) · nginx 빌드하고 실행 (docker-compose.yml)"
docker compose up -d --build

echo "3) 상태"
docker compose ps

echo "4) 시작 로그 (migrate → collectstatic → gunicorn)"
sleep 5
docker compose logs --tail 30 web
