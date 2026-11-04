FROM python:3.12-slim

# 로그가 바로 출력되게하고 .pyc 파일 생성 안 함
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# mysqlclient 빌드 도구
RUN apt-get update \
    && apt-get install -y --no-install-recommends pkg-config build-essential default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# uv설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# package install
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# 프로젝트 코드 복사
COPY . .

# .venv 안의 python, gunicorn을 바로 쓰도록 PATH 등록
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# 컨테이너 시작 시: DB 테이블 생성 -> static 모으기-> gunicorn 실행
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --threads 4 --timeout 180"]
