.PHONY: deploy

deploy:
	test -n "$(NAMESPACE)"  # $$NAMESPACE

	helm upgrade \
		--atomic \
		--dependency-update \
		--install \
		--namespace $(NAMESPACE) \
		--timeout 5m \
		--values .values.yaml \
		--wait \
		default private-gpt
