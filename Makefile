.PHONY: help start stop logs clean setup addtoml app_logs redis_logs api_logs
# Default target
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# Development
setup: ## Install Python dependencies
	uv sync

addtoml:
	uv add -r requirements.txt

# Service management
start: ## Start all services
	docker compose up --build -d

stop: ## Stop all services
	docker-compose down

logs: ## Show service logs
	docker compose logs -f

clean:
	docker compose down -v
	docker system prune -f

app_logs:
	docker compose logs -f app

redis_logs:
	docker compose logs -f redis

api_logs:
	docker compose logs -f api