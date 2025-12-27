# Makefile for AnimePlayer (macOS / Linux)
# Usage:
#   make build      - Build all applications
#   make clean      - Clean build artifacts
#   make rebuild    - Clean and rebuild
#   make vlc        - Build only VLC player
#   make mpv        - Build only MPV player
#   make browser    - Build only Mini Browser
#   make main       - Build only main app
#   make lite       - Build only Lite version
#   make post-build - Run post-build only

SHELL := /bin/bash

# Python and PyInstaller
PYTHON := python3
PYINSTALLER := pyinstaller
PIP := pip3

# Directories
PROJECT_DIR := $(shell pwd)
BUILD_DIR := $(PROJECT_DIR)/make_bin
DIST_DIR := $(PROJECT_DIR)/dist
SPEC_FILE := $(BUILD_DIR)/main.spec

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

.PHONY: all build clean rebuild help install-deps check-deps \
        vlc mpv browser main lite sync post-build

# Default target
all: build sync

# Help
help:
	@echo "$(GREEN)AnimePlayer Build System$(NC)"
	@echo ""
	@echo "$(YELLOW)Usage:$(NC)"
	@echo "  make all          - Build everything (main + sync)"
	@echo "  make build        - Build main applications"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make rebuild      - Clean and rebuild everything"
	@echo "  make install-deps - Install Python dependencies"
	@echo ""
	@echo "$(YELLOW)Individual builds:$(NC)"
	@echo "  make vlc          - Build VLC player only"
	@echo "  make mpv          - Build MPV player only"
	@echo "  make browser      - Build Mini Browser only"
	@echo "  make main         - Build main AnimePlayer only"
	@echo "  make lite         - Build AnimePlayer Lite only"
	@echo "  make sync         - Build PlayerDBSync utilities"
	@echo ""
	@echo "$(YELLOW)Other:$(NC)"
	@echo "  make post-build   - Run post-build operations"
	@echo "  make check-deps   - Check if dependencies are installed"

# Check dependencies
check-deps:
	@echo "$(YELLOW)Checking dependencies...$(NC)"
	@$(PYTHON) --version || (echo "$(RED)Python not found!$(NC)" && exit 1)
	@$(PYTHON) -c "import PyInstaller" || (echo "$(RED)PyInstaller not installed!$(NC)" && exit 1)
	@echo "$(GREEN)All dependencies OK$(NC)"

# Install dependencies
install-deps:
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	$(PIP) install -r requirements.txt
	$(PIP) install pyinstaller
	@echo "$(GREEN)Dependencies installed$(NC)"

# Full build
build: check-deps
	@echo "$(GREEN)Starting full build...$(NC)"
	@mkdir -p $(DIST_DIR)
	$(PYINSTALLER) --noconfirm --clean $(SPEC_FILE)
	@echo "$(GREEN)Build completed!$(NC)"

# Clean build artifacts
clean:
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	rm -rf $(DIST_DIR)/*
	rm -rf $(PROJECT_DIR)/build
	rm -rf $(PROJECT_DIR)/make_bin/__pycache__
	rm -rf $(PROJECT_DIR)/**/__pycache__
	find $(PROJECT_DIR) -name "*.pyc" -delete
	find $(PROJECT_DIR) -name "*.pyo" -delete
	@echo "$(GREEN)Clean completed$(NC)"

# Rebuild (clean + build)
rebuild: clean build

# Individual component builds using separate spec files
vlc: check-deps
	@echo "$(YELLOW)Building VLC Player...$(NC)"
	$(PYINSTALLER) --noconfirm $(BUILD_DIR)/specs/vlc_player.spec
	@echo "$(GREEN)VLC Player built$(NC)"

mpv: check-deps
	@echo "$(YELLOW)Building MPV Player...$(NC)"
	$(PYINSTALLER) --noconfirm $(BUILD_DIR)/specs/mpv_player.spec
	@echo "$(GREEN)MPV Player built$(NC)"

browser: check-deps
	@echo "$(YELLOW)Building Mini Browser...$(NC)"
	$(PYINSTALLER) --noconfirm $(BUILD_DIR)/specs/mini_browser.spec
	@echo "$(GREEN)Mini Browser built$(NC)"

main: check-deps
	@echo "$(YELLOW)Building Main AnimePlayer...$(NC)"
	$(PYINSTALLER) --noconfirm $(BUILD_DIR)/specs/main_app.spec
	@echo "$(GREEN)Main AnimePlayer built$(NC)"

lite: check-deps
	@echo "$(YELLOW)Building AnimePlayer Lite...$(NC)"
	$(PYINSTALLER) --noconfirm $(BUILD_DIR)/specs/lite_app.spec
	@echo "$(GREEN)AnimePlayer Lite built$(NC)"

sync: check-deps
	@echo "$(YELLOW)Building PlayerDBSync utilities...$(NC)"
	$(PYINSTALLER) --noconfirm $(BUILD_DIR)/specs/db_sync.spec
	@echo "$(GREEN)PlayerDBSync built$(NC)"

# Run post-build only
post-build:
	@echo "$(YELLOW)Running post-build operations...$(NC)"
	$(PYTHON) -m make_bin.post_build
	@echo "$(GREEN)Post-build completed$(NC)"

# Create distribution archive
dist: build
	@echo "$(YELLOW)Creating distribution archive...$(NC)"
	cd $(DIST_DIR) && tar -czvf AnimePlayer-$(shell date +%Y%m%d).tar.gz AnimePlayer/
	@echo "$(GREEN)Archive created: $(DIST_DIR)/AnimePlayer-$(shell date +%Y%m%d).tar.gz$(NC)"

# Development build (faster, with console)
dev: check-deps
	@echo "$(YELLOW)Development build (with console)...$(NC)"
	$(PYINSTALLER) --noconfirm --clean \
		--console \
		--name AnimePlayer-dev \
		main.py
	@echo "$(GREEN)Dev build completed$(NC)"

# Run tests
test:
	@echo "$(YELLOW)Running tests...$(NC)"
	$(PYTHON) -m pytest tests/ -v
	@echo "$(GREEN)Tests completed$(NC)"

# Lint code
lint:
	@echo "$(YELLOW)Running linter...$(NC)"
	$(PYTHON) -m flake8 app/ core/ utils/ --max-line-length=120
	@echo "$(GREEN)Lint completed$(NC)"