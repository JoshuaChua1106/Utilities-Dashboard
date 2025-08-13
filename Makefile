# Utilities Tracker - Local Development Makefile

.PHONY: help setup install clean test lint format run-web run-fetch run-parse docker-build docker-run

# Default target
help:
	@echo "Utilities Tracker - Local Development Commands"
	@echo "=============================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  setup        - Initialize local development environment"
	@echo "  install      - Install Python dependencies"
	@echo "  clean        - Clean up generated files and caches"
	@echo ""
	@echo "Development:"
	@echo "  test         - Run all tests"
	@echo "  lint         - Run code linting"
	@echo "  format       - Format code with black and isort"
	@echo ""
	@echo "Application:"
	@echo "  run-web      - Start web application locally"
	@echo "  run-fetch    - Fetch invoices from email"
	@echo "  run-parse    - Parse PDFs and extract data"
	@echo ""
	@echo "Docker (Optional):"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run application in Docker"
	@echo ""
	@echo "AWS (Production Only):"
	@echo "  aws-deploy   - Deploy to AWS (requires approval)"
	@echo "  aws-destroy  - Destroy AWS resources"

# Setup local development environment
setup:
	@echo "🚀 Setting up Utilities Tracker local development environment..."
	python -m venv venv
	@echo "📦 Virtual environment created. Activate it with:"
	@echo "   source venv/bin/activate (Linux/Mac)"
	@echo "   venv\\Scripts\\activate (Windows)"
	@echo "Then run: make install"

# Install dependencies
install:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	python local_dev/init_db.py
	@echo "✅ Installation complete!"
	@echo "Next steps:"
	@echo "1. Edit config/credentials.json with your email credentials"
	@echo "2. Edit config/providers.json with your provider settings" 
	@echo "3. Run: make run-web"

# Clean up
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .tox/
	rm -rf data/*.db logs/*.log

# Run tests
test:
	python -m pytest tests/ -v --cov=. --cov-report=html --cov-report=term

# Run linting
lint:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	mypy . --ignore-missing-imports

# Format code
format:
	black . --line-length=100
	isort . --profile black

# Start web application
run-web:
	@echo "🌐 Starting web application..."
	@echo "Frontend: http://localhost:3000"
	@echo "API: http://localhost:5000"
	python web_app/backend/app.py

# Fetch invoices
run-fetch:
	@echo "📧 Fetching invoices from email..."
	python email_fetcher/fetch_invoices.py --mode=incremental

# Parse PDFs
run-parse:
	@echo "📄 Parsing PDF invoices..."
	python pdf_parser/parse_pdfs.py

# Fetch historical data (first time setup)
fetch-historical:
	@echo "📧 Fetching historical invoices (this may take a while)..."
	python email_fetcher/fetch_invoices.py --mode=historical

# Docker build
docker-build:
	docker build -t utilities-tracker:latest .
	@echo "✅ Docker image built: utilities-tracker:latest"

# Docker run
docker-run:
	docker run -p 5000:5000 -p 3000:3000 -v $(PWD)/data:/app/data utilities-tracker:latest

# Full local pipeline (fetch + parse + web)
run-full:
	@echo "🔄 Running full pipeline..."
	make run-fetch
	make run-parse
	make run-web

# Development server with auto-reload
dev:
	@echo "🛠️ Starting development server with auto-reload..."
	python web_app/backend/app.py --debug --reload

# Export data for Power BI
export-powerbi:
	@echo "📊 Exporting data for Power BI..."
	python data_storage/export_csv.py --output=data/invoices.csv
	@echo "✅ Data exported to data/invoices.csv"
	@echo "You can now connect Power BI to this file"

# Validate configuration
validate-config:
	@echo "⚙️ Validating configuration files..."
	python local_dev/validate_config.py

# Reset database (caution!)
reset-db:
	@echo "⚠️ WARNING: This will delete all data!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ]
	rm -f data/invoices.db
	python local_dev/init_db.py
	@echo "✅ Database reset complete"

# AWS deployment (production only, requires approval)
aws-deploy:
	@echo "🚨 AWS DEPLOYMENT REQUIRES EXPLICIT APPROVAL"
	@echo "This will deploy to AWS and incur costs."
	@echo "Ensure local testing is complete first."
	@read -p "Have you received approval to deploy to AWS? (y/N): " confirm && [ "$$confirm" = "y" ]
	cd infrastructure && cdk deploy --all
	python aws_setup/configure_services.py
	@echo "✅ AWS deployment complete"

# AWS destroy (cleanup resources)
aws-destroy:
	@echo "🧹 Destroying AWS resources..."
	@read -p "Are you sure you want to destroy all AWS resources? (y/N): " confirm && [ "$$confirm" = "y" ]
	cd infrastructure && cdk destroy --all
	@echo "✅ AWS resources destroyed"

# Show current status
status:
	@echo "📊 Utilities Tracker Status"
	@echo "=========================="
	@echo -n "Database: "
	@test -f data/invoices.db && echo "✅ Initialized" || echo "❌ Not found"
	@echo -n "Configuration: "
	@test -f config/credentials.json && echo "✅ Found" || echo "❌ Missing credentials.json"
	@echo -n "Virtual Environment: "
	@test -d venv && echo "✅ Ready" || echo "❌ Run 'make setup'"
	@echo ""
	@if [ -f data/invoices.db ]; then \
		echo "Recent invoices:"; \
		sqlite3 data/invoices.db "SELECT COUNT(*) as total_invoices FROM invoices;" | sed 's/^/  Total: /'; \
		sqlite3 data/invoices.db "SELECT provider_name, COUNT(*) as count FROM invoices GROUP BY provider_name;" | sed 's/^/  /'; \
	fi