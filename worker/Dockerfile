FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY api /app/api
COPY worker /app/worker
COPY shared /app/shared
COPY .env.example /app/.env.example
RUN pip install --no-cache-dir .

CMD ["python", "-m", "worker.app.main"]
