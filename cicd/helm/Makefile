.PHONY: deploy
namespace ?= private-gpt
instance ?= default

deploy:
	helm upgrade \
		--atomic \
		--dependency-update \
		--install \
		--namespace $(namespace) \
		--timeout 5m \
		--values .values.yaml \
		--wait \
		$(instance) private-gpt

dry-run:
	helm upgrade \
		--atomic \
		--dependency-update \
		--dry-run \
		--install \
		--namespace $(namespace) \
		--timeout 5m \
		--values .values.yaml \
		--wait \
		$(instance) private-gpt
