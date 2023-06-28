.PHONY: version version-full build test start stop logs deploy

version_small ?= $(shell $(MAKE) --silent version)
version_full ?= $(shell $(MAKE) --silent version-full)

version:
	@bash ./cicd/version/version.sh -g . -c

version-full:
	@bash ./cicd/version/version.sh -g . -c -m

build:
	@make -C src/conversation-api build
	@make -C src/conversation-ui build

test:
	@make -C src/conversation-api test
	@make -C src/conversation-ui test

lint:
	@make -C src/conversation-api lint
	@make -C src/conversation-ui lint

start:
	docker-compose up -d

stop:
	docker-compose down

logs:
	docker-compose logs --follow

deploy:
	@make -C cicd/helm deploy
