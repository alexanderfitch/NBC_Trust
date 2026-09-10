.PHONY: run test test-engine test-microsite site site-check

run:
	python3 data-engine/src/pipeline.py

test: test-engine test-microsite

test-engine:
	python3 -m unittest discover -s data-engine/tests -v

test-microsite:
	python3 -m unittest discover -s microsite/tests -v

site:
	python3 microsite/build.py

site-check:
	python3 microsite/build.py --check
