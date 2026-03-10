# Stage 1: Frontend build
FROM node:20-alpine AS frontend
WORKDIR /app/web/frontend
COPY web/frontend/package*.json ./
RUN npm ci
COPY web/frontend/ ./
RUN npm run build

# Stage 2: Python backend + tools
FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    openjdk-17-jre-headless curl git tar \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY web/ ./web/
COPY issuebot/ ./issuebot/
COPY config/ ./config/
COPY decompiler/ ./decompiler/
COPY tools/ ./tools/
COPY CLAUDE.md .
COPY .claude/ ./.claude/

# Copy frontend build from stage 1
COPY --from=frontend /app/web/frontend/dist ./web/frontend/dist

# Data volumes
VOLUME ["/app/tasks", "/app/packages", "/app/logs"]

# Environment
ENV ISSUEBOT_ROOT=/app

EXPOSE 8000

CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
