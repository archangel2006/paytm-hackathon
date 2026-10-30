PYTHON ?= python

.PHONY: help setup seed dev tunnel test e2e sim check

help:
	@echo "Available commands:"
	@echo "  make setup   - Install dependencies and copy environment files"
	@echo "  make seed    - Build the seeded database and pristine copy"
	@echo "  make dev     - Run the FastAPI server on port 8000"
	@echo "  make test    - Run server unit tests"
	@echo "  make e2e     - Run end-to-end acceptance tests"
	@echo "  make sim     - Run simulation and display metrics report"
	@echo "  make check   - Run ownership boundary verification"

setup:
	$(PYTHON) -m pip install -e .
	@test -f .env || cp .env.example .env
	@test -f server/.env || cp server/.env.example server/.env

seed:
	$(PYTHON) -m server.db.seed

dev:
	$(PYTHON) -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

tunnel:
	@echo "To tunnel WhatsApp webhook: cloudflared tunnel --url http://localhost:8000 or ngrok http 8000"

test:
	$(PYTHON) -m pytest server/tests

e2e:
	$(PYTHON) -m pytest e2e

sim:
	$(PYTHON) -m server.simulation.report

check:
	$(PYTHON) scripts/check_ownership.py

