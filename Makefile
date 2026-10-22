# Assembleias: ETL em Python (backend/, uv) e site estatico Next.js (frontend/).
# `make` instala, linta e testa o backend; `make build` constroi o site.

UV      ?= uv
NPM     ?= npm
NPX     ?= npx
VENV    ?= backend/.venv
PYTHON  ?= $(CURDIR)/$(VENV)/bin/python

.PHONY: all install lint lint-strict test build run front-test clean fclean re

all: install lint test

install:
	$(UV) venv --python 3.12 $(VENV)
	$(UV) pip install --python $(PYTHON) -e "backend[dev]"
	cd frontend && $(NPM) ci

lint:
	cd backend && $(PYTHON) -m flake8 && $(PYTHON) -m mypy app

lint-strict:
	cd backend && $(PYTHON) -m mypy --strict app

test:
	cd backend && $(PYTHON) -m pytest

build:
	cd frontend && $(NPM) run build:all

# ETL das duas casas (ver README, Setup).
run:
	cd backend && $(PYTHON) -m app.etl.export_snapshot --uf RJ --all
	cd backend && $(PYTHON) -m app.etl.export_static_frontend --uf RJ
	cd backend && $(PYTHON) -m app.etl.export_snapshot --uf SP --all
	cd backend && $(PYTHON) -m app.etl.export_static_frontend --uf SP

front-test:
	cd frontend && $(NPX) playwright test

clean:
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache
	rm -rf frontend/test-results frontend/playwright-report frontend/tsconfig.tsbuildinfo

fclean: clean
	rm -rf $(VENV) frontend/node_modules frontend/.next frontend/out frontend/out-casas frontend/out-all

re: fclean install
