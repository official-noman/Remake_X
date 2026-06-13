.PHONY: dev prod migrate test logs sync-now shell

dev:
	docker-compose up --build

prod:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

migrate:
	docker-compose exec web python manage.py migrate --no-input

test:
	docker-compose exec web pytest

logs:
	docker-compose logs -f

sync-now:
	curl -X POST -H "Content-Type: application/json" -d '{"sync_type": "full"}' http://localhost:8000/api/v1/odoo-sync/sync/trigger/

shell:
	docker-compose exec web python manage.py shell
