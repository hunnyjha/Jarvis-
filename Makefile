.PHONY: install dev prod test migrate clean logs shell-backend shell-frontend help

# ── Variables ─────────────────────────────────────────────────
DOCKER_COMPOSE := docker compose
DOCKER_COMPOSE_PROD := docker compose -f docker-compose.prod.yml
BACKEND_SERVICE := backend
FRONTEND_SERVICE := frontend

help: ## Show this help message
	@echo "JARVIS AI Operating System — Make Commands"
	@echo "==========================================="
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install all dependencies (Python + Node)
	@echo "Installing backend dependencies..."
	cd backend && pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "Copying .env.example to .env (if not exists)..."
	cp -n .env.example .env || true

dev: ## Start all services in development mode
	@echo "Starting JARVIS in development mode..."
	$(DOCKER_COMPOSE) up --build -d
	@echo "Waiting for services to be healthy..."
	$(DOCKER_COMPOSE) wait postgres redis chromadb || true
	@echo "Running database migrations..."
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) alembic upgrade head
	@echo ""
	@echo "JARVIS is running!"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

prod: ## Start all services in production mode
	@echo "Starting JARVIS in production mode..."
	$(DOCKER_COMPOSE_PROD) up --build -d
	@echo "Running database migrations..."
	$(DOCKER_COMPOSE_PROD) exec $(BACKEND_SERVICE) alembic upgrade head
	@echo "JARVIS production is running!"

stop: ## Stop all services
	$(DOCKER_COMPOSE) down

stop-prod: ## Stop production services
	$(DOCKER_COMPOSE_PROD) down

test: ## Run all tests
	@echo "Running backend tests..."
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) pytest tests/ -v --tb=short --cov=app --cov-report=term-missing
	@echo "Running frontend tests..."
	$(DOCKER_COMPOSE) exec $(FRONTEND_SERVICE) npm test -- --watchAll=false

test-backend: ## Run backend tests only
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

test-frontend: ## Run frontend tests only
	$(DOCKER_COMPOSE) exec $(FRONTEND_SERVICE) npm test -- --watchAll=false

migrate: ## Run database migrations
	@echo "Running Alembic migrations..."
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) alembic upgrade head
	@echo "Migrations complete."

migrate-create: ## Create a new migration (usage: make migrate-create MSG="description")
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) alembic revision --autogenerate -m "$(MSG)"

migrate-downgrade: ## Downgrade last migration
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) alembic downgrade -1

migrate-history: ## Show migration history
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) alembic history

clean: ## Stop services and remove volumes (DESTRUCTIVE)
	@echo "WARNING: This will delete all data volumes!"
	@read -p "Are you sure? [y/N] " ans && [ "$$ans" = "y" ] || exit 1
	$(DOCKER_COMPOSE) down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete."

logs: ## Tail logs from all services
	$(DOCKER_COMPOSE) logs -f --tail=100

logs-backend: ## Tail backend logs
	$(DOCKER_COMPOSE) logs -f --tail=100 $(BACKEND_SERVICE)

logs-frontend: ## Tail frontend logs
	$(DOCKER_COMPOSE) logs -f --tail=100 $(FRONTEND_SERVICE)

logs-db: ## Tail database logs
	$(DOCKER_COMPOSE) logs -f --tail=100 postgres

shell-backend: ## Open shell in backend container
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) /bin/bash

shell-frontend: ## Open shell in frontend container
	$(DOCKER_COMPOSE) exec $(FRONTEND_SERVICE) /bin/sh

shell-db: ## Open psql in postgres container
	$(DOCKER_COMPOSE) exec postgres psql -U $${POSTGRES_USER:-jarvis} -d $${POSTGRES_DB:-jarvis_db}

shell-redis: ## Open redis-cli in redis container
	$(DOCKER_COMPOSE) exec redis redis-cli -a $${REDIS_PASSWORD:-redis_secret}

ps: ## Show running containers
	$(DOCKER_COMPOSE) ps

build: ## Build all Docker images
	$(DOCKER_COMPOSE) build --no-cache

rebuild: ## Force rebuild all Docker images
	$(DOCKER_COMPOSE) build --no-cache --pull

format: ## Format code (backend + frontend)
	@echo "Formatting backend..."
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) black app/ tests/
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) isort app/ tests/
	@echo "Formatting frontend..."
	$(DOCKER_COMPOSE) exec $(FRONTEND_SERVICE) npm run format

lint: ## Lint code (backend + frontend)
	@echo "Linting backend..."
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) flake8 app/ tests/
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) mypy app/
	@echo "Linting frontend..."
	$(DOCKER_COMPOSE) exec $(FRONTEND_SERVICE) npm run lint

setup: ## Initial project setup (first time)
	@bash scripts/setup.sh

seed: ## Seed database with the admin user + default collections
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) python -m app.db.seed
