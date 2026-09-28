.PHONY: install test lint check smoke catalog

install:
	.cicd/install.sh

test:
	.cicd/test.sh

lint:
	.cicd/lint.sh

check: test lint

smoke:
	.cicd/smoke.sh

catalog:
	.cicd/catalog.sh
