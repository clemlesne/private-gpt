.PHONY: deploy dry-run
namespace ?= private-gpt
instance ?= default

deploy:
	helm upgrade \
		--atomic \
		--install \
		--namespace $(namespace) \
		--timeout 5m \
		--values .values.yaml \
		--wait \
		$(instance) private-gpt

upgrade:
	@echo "➡️ Upgrading Helm..."
	helm dependency update \
		--skip-refresh \
		private-gpt

lint:
	@echo "➡️ Running Helm..."
	helm lint \
		--strict \
		--values .values.yaml \
		private-gpt

dry-run:
	helm upgrade \
		--atomic \
		--dry-run \
		--install \
		--namespace $(namespace) \
		--timeout 5m \
		--values .values.yaml \
		--wait \
		$(instance) private-gpt
