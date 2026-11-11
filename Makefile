.PHONY: start stop logs backend-check frontend-check

start:
	docker compose up -d --build

stop:
	docker compose stop

logs:
	docker compose logs --tail 100 -f backend provisioner

backend-check:
	docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps -e PROBELOOP_PROVISIONER_URL= backend sh -c "ruff check . && ruff format --check . && mypy --strict -p probeloop && lint-imports && pytest"

frontend-check:
	docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps frontend-dev sh -c "npm run lint && npm run lint:fsd && npm run typecheck && npm test && npm run build"
