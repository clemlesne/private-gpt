docker := docker
version_small ?= $(shell $(MAKE) --directory ../../ --silent version)
version_full ?= $(shell $(MAKE) --directory ../../ --silent version-full)
component_name := conversation-api
container_name := ghcr.io/clemlesne/private-gpt:$(component_name)

install:
	python3 -m pip install -r requirements.txt

upgrade:
	@echo "➡️ Upgrading pip..."
	python3 -m pip install --upgrade pip

	@echo "➡️ Upgrading Python dependencies..."
	pur -r requirements.txt

test:
	@echo "➡️ Running Black..."
	python3 -m black --check .

	@echo "➡️ Running Hadolint..."
	find . -name "Dockerfile*" -exec bash -c "echo 'File {}:' && hadolint {}" \;

lint:
	@echo "➡️ Running Black..."
	python3 -m black .

	@echo "➡️ Running Hadolint..."
	find . -name "Dockerfile*" -exec bash -c "echo 'File {}:' && hadolint {}" \;

start:
	VERSION=$(version_full) python3 -m uvicorn main:api \
		--header x-version:$${VERSION} \
		--no-server-header \
		--port 8081 \
		--proxy-headers \
		--reload

build:
	$(docker) build \
		--build-arg VERSION=$(version_full) \
		--tag $(container_name)-$(version_small) \
		--tag $(container_name)-latest \
		.
