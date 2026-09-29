.PHONY: run test test-engine test-microsite site site-check deploy

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

# Production build, staged under /succession/ to match site.json's path_prefix,
# then pushed to Cloudflare (wrangler.jsonc). Never deploys a --local build.
deploy:
	rm -rf microsite/dist microsite/deploy
	python3 microsite/build.py
	mkdir -p microsite/deploy
	cp -R microsite/dist microsite/deploy/succession
	printf '/ /succession/ 302\n' > microsite/deploy/_redirects
	npx wrangler deploy
