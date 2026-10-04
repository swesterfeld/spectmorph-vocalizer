PYTHON ?= python3

.PHONY: check
check:
	$(PYTHON) -B -m unittest discover -s tests -v
