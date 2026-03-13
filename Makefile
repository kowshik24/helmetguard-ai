.PHONY: run-api run-worker lint format test

run-api:
	uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --reload

run-worker:
	python -m worker.app.main

lint:
	ruff check .

format:
	black .

test:
	pytest

benchmark:
	python scripts/benchmark.py --pred data/reports/latest/report.json
