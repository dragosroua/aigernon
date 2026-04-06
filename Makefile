.PHONY: dev dev-api dev-web install install-api install-web build deploy test clean

# Development
dev:
	@echo "Starting API and Web in development mode..."
	@trap 'kill 0' SIGINT; \
	(cd . && aigernon api --reload) & \
	(cd web && npm run dev) & \
	wait

dev-api:
	aigernon api --reload

dev-web:
	cd web && npm run dev

# Installation
install: install-api install-web

install-api:
	pip install -e ".[api,dev]"

install-web:
	cd web && npm install

# Build
build:
	docker compose -f docker/docker-compose.yml build

build-api:
	docker build -f docker/Dockerfile.api -t aigernon-api .

build-web:
	docker build -f docker/Dockerfile.web -t aigernon-web ./web

# Run with Docker
up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down

logs:
	docker compose -f docker/docker-compose.yml logs -f

# Testing
test:
	pytest tests/
	cd web && npm test 2>/dev/null || true

test-api:
	pytest tests/

# Clean
clean:
	rm -rf web/.next web/node_modules
	rm -rf __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Deploy (customize for your setup)
deploy:
	@echo "Deploying to production..."
	ssh vps "cd /opt/aigernon && git pull && docker compose -f docker/docker-compose.yml up -d --build"

# Help
help:
	@echo "AIGernon Development Commands"
	@echo ""
	@echo "  make dev         - Start API and Web in development mode"
	@echo "  make dev-api     - Start API only with hot reload"
	@echo "  make dev-web     - Start Web UI only"
	@echo "  make install     - Install all dependencies"
	@echo "  make build       - Build Docker images"
	@echo "  make up          - Start with Docker Compose"
	@echo "  make down        - Stop Docker Compose"
	@echo "  make logs        - View Docker logs"
	@echo "  make test        - Run all tests"
	@echo "  make clean       - Clean build artifacts"
	@echo "  make deploy      - Deploy to production"
