.PHONY: install test security run all

install:
	pip install -e ".[dev]"

test:
	pytest -q

security:
	bandit -r src -q && pip-audit

all: test security

run:
	onionlens "$(Q)"
