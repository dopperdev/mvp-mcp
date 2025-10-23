.PHONY: help install dev build up down logs test clean

help: ## Show this help message
	@echo "MCP Security Gateway - Make Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

dev: ## Run in development mode
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

build: ## Build Docker image
	docker-compose build

up: ## Start all services with Docker Compose
	docker-compose up -d

down: ## Stop all services
	docker-compose down

logs: ## View logs
	docker-compose logs -f gateway

logs-all: ## View all service logs
	docker-compose logs -f

ps: ## Show running containers
	docker-compose ps

restart: ## Restart all services
	docker-compose restart

test: ## Run tests
	pytest -v

test-security: ## Run security tests only
	pytest src/tests/test_security.py -v

test-integration: ## Run integration tests
	pytest src/tests/test_integration.py -v

test-coverage: ## Run tests with coverage
	pytest --cov=src --cov-report=html --cov-report=term

shell: ## Open shell in gateway container
	docker-compose exec gateway /bin/bash

db-shell: ## Open PostgreSQL shell
	docker-compose exec postgres psql -U mcp_user -d mcp_gateway

redis-shell: ## Open Redis shell
	docker-compose exec redis redis-cli

clean: ## Clean up containers and volumes
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage

reset: clean up ## Reset and restart everything

init-db: ## Initialize database tables
	docker-compose exec gateway python -c "from src.database import init_db; init_db()"

create-user: ## Create a new user (interactive)
	@read -p "Username: " username; \
	read -p "Email: " email; \
	read -s -p "Password: " password; \
	echo ""; \
	curl -X POST http://localhost:8000/auth/register \
		-H "Content-Type: application/json" \
		-d "{\"username\":\"$$username\",\"email\":\"$$email\",\"password\":\"$$password\",\"is_admin\":false}"

login: ## Login and get JWT token
	@curl -X POST http://localhost:8000/auth/login \
		-H "Content-Type: application/json" \
		-d '{"username":"admin","password":"admin"}' | jq -r '.access_token'

health: ## Check service health
	@curl -s http://localhost:8000/health | jq .

metrics: ## View Prometheus metrics
	@curl -s http://localhost:8000/metrics

backup-db: ## Backup database
	docker-compose exec -T postgres pg_dump -U mcp_user mcp_gateway > backup_$(shell date +%Y%m%d_%H%M%S).sql

restore-db: ## Restore database from backup (set BACKUP_FILE=filename)
	@if [ -z "$(BACKUP_FILE)" ]; then echo "Usage: make restore-db BACKUP_FILE=backup.sql"; exit 1; fi
	docker-compose exec -T postgres psql -U mcp_user mcp_gateway < $(BACKUP_FILE)

lint: ## Run code linting
	flake8 src/ --max-line-length=100 --ignore=E501,W503 || true
	black --check src/ || true

format: ## Format code
	black src/
	isort src/

docker-clean: ## Clean Docker resources
	docker system prune -af --volumes
