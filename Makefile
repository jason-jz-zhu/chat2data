# Chat2Data Makefile for common tasks

.PHONY: help install setup run-backend run-frontend run clean test format lint

help:
	@echo "Chat2Data - Natural Language to SQL Framework"
	@echo ""
	@echo "Available commands:"
	@echo "  make install      Install dependencies using uv"
	@echo "  make setup        Complete setup (Docker, DB, etc.)"
	@echo "  make run          Run both backend and frontend"
	@echo "  make run-backend  Run backend server only"
	@echo "  make run-frontend Run frontend server only"
	@echo "  make clean        Clean cache and temp files"
	@echo "  make test         Run tests"
	@echo "  make format       Format code with black"
	@echo "  make lint         Lint code with ruff"

install:
	@echo "Installing dependencies with uv..."
	uv venv
	uv pip install -e .
	uv pip install -e ".[dev]"
	@echo "✅ Dependencies installed"

setup: install
	@echo "Starting Ollama..."
	docker-compose up -d ollama
	@echo "Waiting for Ollama to start..."
	@sleep 5
	@echo "Pulling Llama3 model..."
	docker exec chat2data-ollama ollama pull llama3 || echo "⚠️  Model pull failed, try manually"
	@echo "Creating sample database..."
	. .venv/bin/activate && python scripts/setup_sample_data.py
	@echo "Creating directories..."
	@mkdir -p data/chroma_db logs
	@echo "✅ Setup complete!"

run-backend:
	@echo "Starting backend server..."
	. .venv/bin/activate && cd backend && python app.py

run-frontend:
	@echo "Starting frontend server..."
	. .venv/bin/activate && cd frontend && streamlit run streamlit_app.py

run:
	@echo "Starting Chat2Data services..."
	@echo "Start backend in one terminal: make run-backend"
	@echo "Start frontend in another terminal: make run-frontend"
	@echo ""
	@echo "Or use separate terminals and run:"
	@echo "  Terminal 1: make run-backend"
	@echo "  Terminal 2: make run-frontend"

clean:
	@echo "Cleaning cache and temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.pyd" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"

test:
	@echo "Running tests..."
	. .venv/bin/activate && pytest

format:
	@echo "Formatting code with black..."
	. .venv/bin/activate && black backend/ frontend/ scripts/

lint:
	@echo "Linting code with ruff..."
	. .venv/bin/activate && ruff check backend/ frontend/ scripts/

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

reset-db:
	@echo "Resetting database..."
	rm -f data/sample_db.sqlite
	rm -rf data/chroma_db
	mkdir -p data/chroma_db
	. .venv/bin/activate && python scripts/setup_sample_data.py
	@echo "✅ Database reset"