# =============================================================================
# Stage 1: Build React Frontend
# =============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/ws2_client

# Install frontend dependencies
COPY ws2_client/package*.json ./
RUN npm ci

# Copy source and build static bundle
COPY ws2_client/ ./
RUN npm run build

# =============================================================================
# Stage 2: Python Backend Runtime
# =============================================================================
FROM python:3.11-slim
WORKDIR /app

# Install build essentials for numpy/scipy/pyroomacoustics
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY contracts/ ./contracts/
COPY ws1_backend/ ./ws1_backend/
COPY ws3_dsp/ ./ws3_dsp/
COPY ws4_eval/ ./ws4_eval/
COPY tests/ ./tests/
COPY run_demo.py Makefile ./

# Copy built frontend assets to static directory
COPY --from=frontend-builder /app/ws2_client/dist ./static

EXPOSE 8000 8001

ENV PORT=8000
ENV ASR_ENGINE=mock

CMD ["python", "ws1_backend/main.py", "--host", "0.0.0.0", "--port", "8000"]
