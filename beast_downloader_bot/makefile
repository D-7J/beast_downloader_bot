.PHONY: help install test lint format run docker-build docker-up docker-down clean backup

# Default target
help:
	@echo "Persian Downloader Bot - Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make run          - Run the bot locally"
	@echo "  make docker-build - Build Docker images"
	@echo "  make docker-up    - Start with Docker Compose"
	@echo "  make docker-down  - Stop Docker Compose"
	@echo "  make clean        - Clean temporary files"
	@echo "  make backup       - Create backup"
	@echo "  make monitor      - Run monitoring dashboard"

# Install dependencies
install:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# Install development dependencies
install-dev:
	pip install pytest pytest-cov pytest-asyncio
	pip install black flake8 mypy
	pip install rich

# Run tests
test:
	pytest tests/ -v --cov=src --cov-report=html

# Run specific test
test-one:
	pytest tests/$(TEST) -v -s

# Linting
lint:
	flake8 src/ tests/ --max-line-length=120 --exclude=__pycache__
	mypy src/ --ignore-missing-imports

# Format code
format:
	black src/ tests/ scripts/

# Check formatting
check-format:
	black --check src/ tests/ scripts/

# Run the bot locally
run:
	python -m src.bot

# Run with auto-reload (development)
run-dev:
	watchmedo auto-restart --directory=./src --pattern=*.py --recursive -- python -m src.bot

# Docker commands
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart:
	docker-compose restart

# Run specific service
docker-run-service:
	docker-compose up -d $(SERVICE)

# Database operations
db-backup:
	docker-compose exec mongodb mongodump --out=/backup
	docker cp $$(docker-compose ps -q mongodb):/backup ./backups/mongo_$$(date +%Y%m%d_%H%M%S)

db-restore:
	docker cp $(BACKUP_PATH) $$(docker-compose ps -q mongodb):/restore
	docker-compose exec mongodb mongorestore /restore

# Redis operations
redis-cli:
	docker-compose exec redis redis-cli

redis-flush:
	docker-compose exec redis redis-cli FLUSHALL

# Celery operations
celery-worker:
	celery -A src.tasks.celery_app worker --loglevel=info

celery-beat:
	celery -A src.tasks.celery_app beat --loglevel=info

celery-flower:
	celery -A src.tasks.celery_app flower

# Monitoring
monitor:
	python scripts/monitor.py

# Management commands
manage:
	python scripts/manage.py $(ARGS)

# Add premium to user
add-premium:
	python scripts/manage.py user premium $(USER_ID) $(PLAN) --days $(DAYS)

# Show stats
stats:
	python scripts/manage.py stats

# Clean temporary files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf data/temp/*

# Create backup
backup:
	mkdir -p backups
	tar -czf backups/backup_$$(date +%Y%m%d_%H%M%S).tar.gz \
		--exclude='data/downloads' \
		--exclude='data/temp' \
		--exclude='logs' \
		--exclude='__pycache__' \
		--exclude='.git' \
		.

# Setup project
setup:
	cp .env.example .env
	mkdir -p data/downloads data/temp logs backups
	@echo "Setup complete! Edit .env file with your configuration."

# Generate requirements
freeze:
	pip freeze > requirements.txt

# Update dependencies
update-deps:
	pip install --upgrade -r requirements.txt

# Security check
security:
	pip install safety
	safety check

# Performance profiling
profile:
	python -m cProfile -o profile.stats -m src.bot
	python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('time').print_stats(20)"

# Generate documentation
docs:
	sphinx-build -b html docs/ docs/_build/html

# Deploy to production
deploy:
	@echo "Deploying to production..."
	ssh $(SERVER) "cd /opt/persian-downloader-bot && git pull && docker-compose down && docker-compose up -d"

# Health check
health:
	curl -f http://localhost:8443/health || exit 1

# Version info
version:
	@python -c "from src.version import __version__; print(f'Version: {__version__}')"