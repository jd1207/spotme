# multi-stage build: node for frontend, python for backend
FROM node:20-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl \
    && rm -rf /var/lib/apt/lists/*

# install claude code cli
RUN curl -fsSL https://claude.ai/install.sh | sh 2>/dev/null || \
    npm install -g @anthropic-ai/claude-code 2>/dev/null || true

# python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[whoop]" 2>/dev/null || pip install --no-cache-dir -e .

# copy backend
COPY server/ server/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY .env.example .env

# copy built frontend from first stage
COPY --from=frontend /build/frontend/dist frontend/dist

# data directory
RUN mkdir -p /data videos
ENV DATABASE_URL=sqlite:////data/spotme.db
ENV VIDEO_DIR=/app/videos

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
