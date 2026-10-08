# FrameGenius CPU image — kingscottishDEV N.A.S
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FRAMEGENIUS_HOME=/app \
    FRAMEGENIUS_AUTH=0

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-liberation \
        fonts-dejavu-core \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p outputs/videos outputs/scripts outputs/logs outputs/thumbnails outputs/tasks data \
    && chmod +x scripts/*.sh || true

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=8s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/api/v1/health || exit 1

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8080"]
