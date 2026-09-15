.PHONY: up down build test unit-test lint seed clean

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

test:
	docker exec seismic_agent python scripts/validate_system.py

unit-test:
	pytest tests/unit -q

validate:
	docker exec seismic_agent pytest -m integration tests/integration/test_signal_path.py -v -s

lint:
	ruff check src tests

seed-geo:
	powershell.exe -ExecutionPolicy Bypass -File scripts/seed_geo.ps1

release:
	python scripts/release.py $(version)

clean:
	docker compose down -v
	rm -rf **/__pycache__
	rm -rf .pytest_cache
