.PHONY: install test lint check smoke catalog catalog-publish

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

catalog-publish:
	.cicd/publish-catalog.sh
