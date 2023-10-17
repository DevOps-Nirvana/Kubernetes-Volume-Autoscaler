.PHONY: deps run run-hot start lint test-local help
.DEFAULT_GOAL := help

SHELL = bash

# Install dependencies
deps:
	pip3 install -r requirements.txt

# This is our default logic for "make run" or "make start", to use the backgrounded.  This is dry-run'd to prevent it from doing anything while developing
run: deps
	@echo -e "\n----- Starting service locally -----"
	# NOTE: In here is where you can throw your secrets and such to avoid it from being committed
	touch unused-local-envs.sh
	source unused-local-envs.sh
	DRY_RUN=true \
	VERBOSE=true \
	python3 main.py

# Warning this will run it "hot" with no dry-run in place
run-hot: deps
	@echo -e "\n----- Starting service locally -----"
	# NOTE: In here is where you can throw your secrets and such to avoid it from being committed
	touch unused-local-envs.sh
	source unused-local-envs.sh
	python3 main.py

# Alternate for "run"
start: run

# Lint our code
lint: deps
	black .

test-local:
	@echo -e "TODO - Add tests"

help:
	@echo -e "Makefile options possible\n------------------------------"
	@echo -e "make deps    # Install dependencies"
	@echo -e "make run     # Run service locally"
	@echo -e "make start   # (alternate) Run service locally"
