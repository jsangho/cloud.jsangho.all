FROM python:3.13-slim
WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=10

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libxcb1 \
    libxext6 \
    libsm6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# build context가 저장소 루트이므로 uv 프로젝트 파일도 루트 기준으로 COPY한다.
COPY pyproject.toml uv.lock ./
# .venv를 만들지 않고 시스템 파이썬(/usr/local)에 직접 설치한다 — docker-compose가
# 런타임에 저장소 전체를 /app에 바인드 마운트하므로, /app 아래에 .venv를 두면
# 마운트가 이미지 빌드 시점의 .venv를 그대로 가려버려 사라진다.
ENV UV_PROJECT_ENVIRONMENT=/usr/local
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

COPY fastapi/ fastapi/
WORKDIR /app/fastapi

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
