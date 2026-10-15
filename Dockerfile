FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_PUBLIC_DEMO=true
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-demo.txt ./
RUN pip install --no-cache-dir -r requirements-demo.txt
COPY chaosai/ ./chaosai/
COPY backend/ ./backend/
COPY sample/ ./sample/
COPY config.yaml ./
COPY --from=frontend /build/dist ./frontend/dist
# Generate simulation evidence in the image; never copy local runs or credentials.
RUN python -m chaosai --sim map \
    && python -m chaosai --sim baseline --seconds 15 \
    && python -m chaosai --sim agent --rounds 3 --planner rule-based
RUN useradd --uid 10001 --create-home demo
USER demo
EXPOSE 8000
CMD ["sh", "-c", "exec python -m uvicorn backend.public_demo:app --host 0.0.0.0 --port ${PORT:-8000}"]
