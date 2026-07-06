FROM python:3.13-slim

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=10

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
