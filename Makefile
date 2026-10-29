# Bouncer: one-command setup and run targets. See README.md.
SHELL := /bin/bash
COLIMA_SOCK := $(HOME)/.colima/default/docker.sock
export DOCKER_HOST ?= $(if $(wildcard $(COLIMA_SOCK)),unix://$(COLIMA_SOCK),)

.PHONY: setup sandbox api web test demo check-models clean

setup: sandbox
	cd backend && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt
	cd frontend && npm ci
	python3 demo/build_tinyparse.py data/repos/tinyparse

# Builds the sandbox image. A throwaway DOCKER_CONFIG avoids broken credential helpers when pulling the public base image.
sandbox:
	mkdir -p .docker-config && [ -f .docker-config/config.json ] || echo '{}' > .docker-config/config.json
	DOCKER_CONFIG="$(CURDIR)/.docker-config" docker build -t bouncer-sandbox:1 sandbox

api:
	cd backend && .venv/bin/uvicorn bouncer.api:app --host 127.0.0.1 --port 8000

web:
	cd frontend && npm run dev -- --port 3000

test:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm run lint && npx tsc --noEmit

demo:
	cd backend && .venv/bin/python tests/run_demo.py

check-models:
	cd backend && .venv/bin/python scripts/check_models.py

clean:
	rm -rf data/runs data/*.sqlite3 data/test-*
