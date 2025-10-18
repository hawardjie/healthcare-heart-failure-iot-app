.PHONY: help setup up down logs clean test install-deps

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

setup: ## Initial Mac setup - install dependencies
	@echo "🔧 Setting up Mac environment..."
	@command -v brew >/dev/null 2>&1 || { echo "Installing Homebrew..."; /bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; }
	@echo "📦 Installing dependencies..."
	@brew list docker >/dev/null 2>&1 || brew install --cask docker
	@brew list python@3.11 >/dev/null 2>&1 || brew install python@3.11
	@brew list node >/dev/null 2>&1 || brew install node
	@brew list postgresql >/dev/null 2>&1 || brew install postgresql
	@echo "🐍 Setting up Python environment..."
	@python3.11 -m venv venv
	@./venv/bin/pip install --upgrade pip
	@echo "✅ Setup complete! Run 'make install-deps' next."

install-deps: ## Install all Python and Node dependencies
	@echo "📦 Installing Python dependencies..."
	@./venv/bin/pip install -r simulator/requirements.txt
	@./venv/bin/pip install -r router_local/requirements.txt
	@./venv/bin/pip install -r ml_service/requirements.txt
	@./venv/bin/pip install -r tests/requirements.txt
	@echo "✅ Dependencies installed!"

env: ## Create .env file from template
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✅ Created .env file. Edit it with your settings."; \
	else \
		echo "⚠️  .env already exists. Skipping."; \
	fi

up: env ## Start all services with Docker Compose
	@echo "🚀 Starting Heart Failure IoT Platform (local dev)..."
	@docker compose up -d
	@echo ""
	@echo "✅ Services started!"
	@echo ""
	@echo "📊 Access points:"
	@echo "  EMQX Dashboard:  http://localhost:18083 (admin/public)"
	@echo "  TimescaleDB:     localhost:5432 (iot_admin/local_dev_password)"
	@echo "  ML Service:      http://localhost:8000"
	@echo "  LocalStack:      http://localhost:4566"
	@echo ""
	@echo "📡 MQTT broker ready at: localhost:1883"
	@echo "🔍 View logs: make logs"

down: ## Stop all services
	@echo "🛑 Stopping services..."
	@docker compose down

logs: ## Tail logs from all services
	@docker compose logs -f

logs-router: ## Tail router service logs
	@docker compose logs -f router

logs-simulator: ## Tail simulator logs
	@docker compose logs -f simulator

logs-ml: ## Tail ML service logs
	@docker compose logs -f ml_service

restart: ## Restart all services
	@echo "🔄 Restarting services..."
	@docker compose restart

ps: ## Show running containers
	@docker compose ps

clean: ## Stop services and remove volumes
	@echo "🧹 Cleaning up..."
	@docker compose down -v
	@rm -rf .localstack/
	@echo "✅ Cleanup complete!"

test-unit: ## Run unit tests
	@echo "🧪 Running unit tests..."
	@./venv/bin/pytest tests/unit -v

test-integration: ## Run integration tests (requires services running)
	@echo "🧪 Running integration tests..."
	@./venv/bin/pytest tests/integration -v

test: ## Run all tests
	@echo "🧪 Running all tests..."
	@./venv/bin/pytest tests/ -v

db-shell: ## Connect to TimescaleDB with psql
	@docker exec -it hf-timescaledb psql -U iot_admin -d heart_failure_iot

db-reset: ## Reset TimescaleDB schema
	@echo "⚠️  Resetting database..."
	@docker exec -i hf-timescaledb psql -U iot_admin -d heart_failure_iot < config/timescaledb/init.sql
	@echo "✅ Database reset complete!"

mqtt-sub: ## Subscribe to all telemetry topics (requires mosquitto-clients)
	@echo "📡 Subscribing to tenants/#..."
	@mosquitto_sub -h localhost -p 1883 -t 'tenants/#' -v

mqtt-test: ## Publish test message to MQTT broker
	@echo "📤 Publishing test message..."
	@mosquitto_pub -h localhost -p 1883 -t 'tenants/clinic-alpha/devices/TEST-001/telemetry' \
		-m '{"timestamp":"'$$(date -u +%Y-%m-%dT%H:%M:%SZ)'","deviceId":"TEST-001","tenantId":"clinic-alpha","pap_systolic":28,"pap_diastolic":12,"heart_rate":72,"signal_quality":0.95}'

validate: ## Validate Docker Compose config
	@docker compose config >/dev/null && echo "✅ docker-compose.yml is valid"

format-python: ## Format Python code with black
	@./venv/bin/black simulator/ router_local/ ml_service/ tests/

lint-python: ## Lint Python code
	@./venv/bin/flake8 simulator/ router_local/ ml_service/ tests/

docs: ## Generate architecture diagrams (requires graphviz)
	@echo "📚 Generating documentation..."
	@cd docs && ./generate_diagrams.sh

.DEFAULT_GOAL := help
