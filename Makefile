.PHONY: run test

run:
	python3 data-engine/src/pipeline.py

test:
	python3 -m unittest discover -s data-engine/tests -v
