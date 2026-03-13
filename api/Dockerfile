FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY api /app/api
COPY worker /app/worker
COPY shared /app/shared
COPY .env.example /app/.env.example
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
