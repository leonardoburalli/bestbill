.PHONY: install test lint check smoke frontend catalog catalog-publish openapi api-local frontend-dev

install:
	.cicd/install.sh

test:
	.cicd/test.sh

lint:
	.cicd/lint.sh

check: test lint

frontend:
	.cicd/frontend.sh

smoke:
	.cicd/smoke.sh

catalog:
	.cicd/catalog.sh

catalog-publish:
	.cicd/publish-catalog.sh

openapi:
	uv run python scripts/export_openapi.py

# Local API on the downloaded catalogue (gh release download catalog-latest -D catalog-latest)
api-local:
	BESTBILL_CATALOG_PATH=catalog-latest/catalog.sqlite uv run uvicorn bestbill.api.main:app --port 8000 --reload

# Front end against the local API (run `make api-local` in another terminal)
frontend-dev:
	cd frontend && BESTBILL_API_PROXY=http://localhost:8000 bun run dev
