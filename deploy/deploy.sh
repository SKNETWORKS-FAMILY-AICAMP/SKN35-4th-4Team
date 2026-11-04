# 빌드부터 실행까지 자동화하는 파일
# 사용법(서버): bash deploy/deploy.sh
set -e

cd ~/SKN35-4th-4Team

echo "1) 최신 코드 받기"
git pull origin dev

echo "2) Docker 이미지 빌드"
docker build -t skn35-4th-web .

echo "3) 기존 컨테이너 삭제 (없으면 건너뜀)"
docker rm -f 4thproject_web 2>/dev/null || true

echo "4) 새 컨테이너 실행"
docker run -d \
  --name 4thproject_web \
  --env-file .env \
  -v /home/ubuntu/SKN35-4th-4Team/staticfiles:/app/staticfiles \
  -p 127.0.0.1:8000:8000 \
  --restart always \
  skn35-4th-web

echo "5) 시작 로그 (migrate → collectstatic → gunicorn)"
sleep 5
docker logs --tail 30 4thproject_web
