.PHONY: install test test-unit test-integration lint fmt typecheck clean

install:
	pip install -e ".[dev]"

test:
	pytest --cov=template_upgrade --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	ruff check src/ tests/

fmt:
	ruff format src/ tests/

typecheck:
	mypy src/template_upgrade/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ dist/ build/ *.egg-info

doctor:
	qvm-template-upgrade doctor
