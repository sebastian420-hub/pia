.PHONY: up down build test lint seed clean

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

test:
	docker exec seismic_agent python scripts/validate_system.py

validate:
	docker exec seismic_agent pytest tests/integration/test_signal_path.py -v -s

lint:
	ruff check .
	black --check .

seed-geo:
	powershell.exe -ExecutionPolicy Bypass -File scripts/seed_geo.ps1

release:
	python scripts/release.py $(version)

clean:
	docker compose down -v
	rm -rf **/__pycache__
	rm -rf .pytest_cache
