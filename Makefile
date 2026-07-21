.PHONY: test lint eval eval-llm preflight audit

test:
	pytest -q

lint:
	ruff check .

eval:
	python3 eval/run_eval.py --rules

eval-llm:
	python3 eval/run_eval.py --rules --llm

preflight:
	python3 -m junk_cleaner.preflight

audit:
	pip-audit -r requirements-dev.txt
	npm audit --audit-level=high
