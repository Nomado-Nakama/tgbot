deploy-no-search:
	docker compose -f docker-compose.yaml up -d --build
deploy-with-search:
	docker compose -f docker-compose.yaml -f docker-compose.vector.yaml up -d --build