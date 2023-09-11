.PHONY: version version-full build test start stop logs deploy

version_small ?= $(shell $(MAKE) --silent version)
version_full ?= $(shell $(MAKE) --silent version-full)

version:
	@bash ./cicd/version/version.sh -g . -c

version-full:
	@bash ./cicd/version/version.sh -g . -c -m

install:
	@make -C src/conversation-api install
	@make -C src/conversation-ui install

build:
	@make -C src/conversation-api build
	@make -C src/conversation-ui build

test:
	@echo "➡️ Running TruffleHog..."
	trufflehog git file://. --since-commit main --branch HEAD --fail --no-update --only-verified

	@make -C src/conversation-api test
	@make -C src/conversation-ui test

lint:
	@make -C cicd/helm lint
	@make -C src/conversation-api lint
	@make -C src/conversation-ui lint

upgrade:
	@make -C cicd/helm upgrade
	@make -C src/conversation-api upgrade
	@make -C src/conversation-ui upgrade

start:
	docker-compose --file src/docker-compose.dev.yaml up --detach

stop:
	docker-compose --file src/docker-compose.dev.yaml down

logs:
	docker-compose logs --follow

deploy:
	@make -C cicd/helm deploy
