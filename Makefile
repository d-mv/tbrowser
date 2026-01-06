# Makefile for tbrowser

.PHONY: help dev run build clean

help:
	@echo "Available commands:"
	@echo "  make dev    - Run the app in development mode"
	@echo "  make run    - Run the app in production mode"
	@echo "  make build  - Rebuild the Docker image"

dev:
	docker compose -f docker-compose.dev.yml run --rm app python -m src.app

run:
	docker compose -f docker-compose.yml run --rm app

build:
	docker compose -f docker-compose.dev.yml build

clean:
	docker compose -f docker-compose.dev.yml down --remove-orphans
	docker compose -f docker-compose.yml down --remove-orphans