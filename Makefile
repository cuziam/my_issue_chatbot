.PHONY: dev install build start docker-up docker-down

install:  ## Install all dependencies
	pip install -r requirements.txt
	cd web/frontend && npm install

dev:  ## Start development servers (backend + frontend)
	@echo "Starting backend on :8000..."
	uvicorn web.backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir web &
	@echo "Starting frontend on :5173..."
	cd web/frontend && npm run dev

build:  ## Build frontend for production
	cd web/frontend && npm run build

start:  ## Start production server
	uvicorn web.backend.main:app --host 0.0.0.0 --port 8000

docker-up:  ## Build and start Docker containers
	docker compose up --build -d

docker-down:  ## Stop Docker containers
	docker compose down
