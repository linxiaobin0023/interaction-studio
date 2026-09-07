.PHONY: api-install api-dev composite dataset-plan-verify dataset-seals-verify benchmark-prepare db-check db-migrate db-rollback development-landmarks development-snapshot g0-verify landmark-install landmark-models landmarks lint preflight product-master readiness test manifest-verify up down

api-install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -c apps/api/constraints.lock -e 'apps/api[dev]'

api-dev:
	.venv/bin/uvicorn interaction_studio_api.main:app --app-dir apps/api/src --reload --host 0.0.0.0 --port 8000

.PHONY: web-install web-dev web-check web-build
web-install:
	npm ci --prefix apps/web --no-audit --no-fund

web-dev:
	npm run dev --prefix apps/web

web-check:
	npm run check --prefix apps/web
	npm run test --prefix apps/web

web-build:
	npm run build --prefix apps/web

lint:
	.venv/bin/ruff check apps/api tools workers/landmarks

test:
	.venv/bin/pytest -c apps/api/pyproject.toml

db-migrate:
	.venv/bin/alembic upgrade head

db-check:
	.venv/bin/alembic check

db-rollback:
	.venv/bin/alembic downgrade -1

manifest-verify:
	python3 tools/validate_asset_manifest.py mock_assets/v0/metadata/asset_manifest.json

dataset-plan-verify:
	.venv/bin/python tools/validate_dataset_plan.py datasets/registry/v1/dataset-plan.json

dataset-seals-verify:
	.venv/bin/python tools/admit_dataset.py datasets/development/v1 --verify-seal
	.venv/bin/python tools/admit_dataset.py datasets/validation/v1 --verify-seal

benchmark-prepare:
	.venv/bin/python tools/prepare_g2_benchmark.py --output docs/benchmarks/g2-input-plan-v1.json

.PHONY: local-preview
local-preview:
	.venv/bin/python tools/run_local_preview.py --case-id $(or $(CASE_ID),DEV_MOUTH_001)

product-master:
	.venv/bin/python workers/product_master/render.py workers/product_master/product-master-v1.json --output-dir assets/production/product_master/v1/renders --size 512 --manifest assets/production/product_master/v1/render-manifest.json

development-snapshot:
	.venv/bin/python tools/build_dataset_snapshot.py datasets/development/v1/case-index.json --dataset-root datasets/development/v1 --output datasets/development/v1/snapshot-manifest.json

development-landmarks: development-snapshot landmark-install landmark-models
	workers/landmarks/.venv/bin/python workers/landmarks/analyze.py datasets/development/v1/snapshot-manifest.json --asset-root datasets/development/v1 --model-dir .cache/landmark-models --output datasets/development/v1/evidence/landmarks.json

g0-verify: dataset-plan-verify
	cd docs/gates && sha256sum -c G0-result-v1.sha256
	.venv/bin/python tools/verify_gate_result.py docs/gates/G0-result-v1.json

readiness:
	.venv/bin/python tools/run_readiness.py mock_assets/v0/metadata/asset_manifest.json

landmark-install:
	python3 -m venv workers/landmarks/.venv
	workers/landmarks/.venv/bin/pip install -r workers/landmarks/requirements.lock

landmark-models:
	python3 tools/fetch_landmark_models.py

landmarks: landmark-install landmark-models
	workers/landmarks/.venv/bin/python workers/landmarks/analyze.py mock_assets/v0/metadata/asset_manifest.json --asset-root mock_assets/v0 --model-dir .cache/landmark-models --output docs/preflight/mock-v0-landmarks.json

composite: landmarks
	.venv/bin/python tools/run_composite_spike.py mock_assets/v0/metadata/asset_manifest.json --landmarks docs/preflight/mock-v0-landmarks.json --output-dir docs/preflight/composites --report docs/preflight/mock-v0-composites.json

preflight: composite
	.venv/bin/python tools/run_preflight_spike.py mock_assets/v0/metadata/asset_manifest.json --landmarks docs/preflight/mock-v0-landmarks.json --composites docs/preflight/mock-v0-composites.json --anatomy docs/preflight/mock-v0-hand-anatomy-review.json

up:
	docker compose up --build

down:
	docker compose down

.PHONY: studio-worker
studio-worker:
	.venv/bin/python -m interaction_studio_api.studio_worker

.PHONY: local-install studio-smoke
local-install:
	python3 tools/install_local_studio.py

studio-smoke:
	.venv/bin/python tools/smoke_studio_container.py
