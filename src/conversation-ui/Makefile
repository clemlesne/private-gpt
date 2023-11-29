docker := docker
version_small ?= $(shell $(MAKE) --directory ../../ --silent version)
version_full ?= $(shell $(MAKE) --directory ../../ --silent version-full)
component_name := conversation-ui
container_name := ghcr.io/clemlesne/private-gpt:$(component_name)

install:
	npm install

upgrade:
	@echo "➡️ Upgrading NPM dependencies..."
	npm update --save

test:
	@echo "➡️ Scanning for NPM outdated dependencies..."
	npm outdated

	@echo "➡️ Running NPM Lint..."
	npm run test

	@echo "➡️ Running Hadolint..."
	find . -name "Dockerfile*" -exec bash -c "echo 'File {}:' && hadolint {}" \;

lint:
	@echo "➡️ Running NPM Lint..."
	npm run lint

	@echo "➡️ Running Hadolint..."
	find . -name "Dockerfile*" -exec bash -c "echo 'File {}:' && hadolint {}" \;

start:
	VITE_VERSION=$(version_full) npm run dev

build:
	$(docker) build \
		--build-arg VERSION=$(version_full) \
		--tag $(container_name)-$(version_small) \
		--tag $(container_name)-latest \
		.
