test-process:
	python3 tests/test_process.py -vvv

test-command:
	python3 tests/test_command.py -vvv

test: test-process test-command

ruff-check:
	ruff check --unsafe-fixes pyflow.py

ruff-fix:
	ruff check --unsafe-fixes --fix pyflow.py

ruff-format:
	ruff format 
