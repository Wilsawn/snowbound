# make setup   install everything into .venv (Python 3.12, via uv)
# make doctor  check tools + data are ready
# make test    run the tests
.PHONY: setup doctor test
setup:
	uv sync
doctor:
	uv run python scripts/doctor.py
test:
	uv run pytest -q
