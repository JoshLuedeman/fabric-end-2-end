# Fabric End-to-End Demo — Central Command Interface
# ===================================================
# This Makefile is the single entry point for all project operations.
# AI agents and human developers use the same targets.
#
# Usage: make <target>
#   Run `make help` (or just `make`) to see available targets.

.DEFAULT_GOAL := help
ENVIRONMENT ?= dev

.PHONY: help setup clean generate-data stream-build stream-run \
        sim-build sim-run sim-run-live \
        tf-init tf-plan tf-apply tf-destroy \
        deploy-content upload-notebooks upload-reports seed-data \
        lint plan review

help: ## Show this help message
	@echo "Fabric End-to-End Demo — available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Set ENVIRONMENT=dev|prod (default: dev)"

# --- Setup ---

setup: ## One-time dev environment setup (Python + Node.js deps)
	@echo "Installing Python dependencies..."
	pip install -r data/generators/requirements.txt
	@echo "Installing Node.js dependencies..."
	cd streaming && npm install
	@echo "Setup complete."

clean: ## Remove generated artifacts
	@echo "Cleaning..."
	@rm -rf data/generators/output/ streaming/dist/ streaming/node_modules/
	@echo "Clean complete."

# --- Data Generation ---

generate-data: ## Generate synthetic demo data (output: data/generators/output/)
	@echo "Generating synthetic data..."
	python data/generators/generate_all.py --output-dir data/generators/output
	@echo "Data generation complete."

seed-data: generate-data ## Generate data and upload to Lakehouse bronze layer
	@bash scripts/seed-data.sh $(ENVIRONMENT)

# --- Streaming ---

stream-build: ## Build the streaming event generator
	cd streaming && npm run build

stream-run: ## Run the streaming event generator locally (DRY_RUN=true)
	cd streaming && DRY_RUN=true npm start

stream-docker: ## Build streaming Docker image
	docker build -t contoso-event-generator ./streaming

# --- OLTP Simulator ---

sim-build: ## Build the OLTP simulator Docker image
	docker build -t contoso-oltp-simulator ./simulator

sim-run: ## Run the OLTP simulator locally (DRY_RUN mode, no DB required)
	cd simulator && python oltp_simulator.py --dry-run

sim-run-live: ## Run the OLTP simulator against a real database
	cd simulator && python oltp_simulator.py

# --- Terraform ---

tf-init: ## Initialize Terraform (usage: make tf-init ENVIRONMENT=dev)
	cd infra/environments/$(ENVIRONMENT) && terraform init

tf-plan: ## Terraform plan (usage: make tf-plan ENVIRONMENT=dev)
	cd infra/environments/$(ENVIRONMENT) && terraform plan -out=tfplan

tf-apply: ## Terraform apply (usage: make tf-apply ENVIRONMENT=dev)
	cd infra/environments/$(ENVIRONMENT) && terraform apply tfplan

tf-destroy: ## Terraform destroy (usage: make tf-destroy ENVIRONMENT=dev)
	cd infra/environments/$(ENVIRONMENT) && terraform destroy

# --- Content Deployment (Fabric CLI) ---

deploy-content: upload-notebooks upload-reports ## Deploy all Fabric content

upload-notebooks: ## Upload notebooks to Fabric workspace
	@bash scripts/upload-notebooks.sh $(ENVIRONMENT)

upload-reports: ## Upload Power BI reports to Fabric workspace
	@bash scripts/upload-reports.sh $(ENVIRONMENT)

# --- Full Deployment ---

deploy-all: tf-init tf-plan tf-apply deploy-content seed-data ## Full environment deployment
	@echo "=== Full deployment to $(ENVIRONMENT) complete ==="

# --- Teamwork Agent Targets ---

plan: ## Invoke planning agent (usage: make plan GOAL="description")
	@bash scripts/plan.sh "$(GOAL)"

review: ## Invoke review agent (usage: make review REF="pr-number-or-branch")
	@bash scripts/review.sh "$(REF)"

lint: ## Run linters
	@echo "Linting Terraform..."
	cd infra && terraform fmt -check -recursive
	@echo "Linting Python..."
	cd data/generators && python -m py_compile generate_all.py
	@echo "Lint complete."
