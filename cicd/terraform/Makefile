.PHONY: install deploy dry-run upgrade

install:
	terraform init

upgrade:
	terraform init -upgrade

deploy:
	terraform apply -auto-approve -var-file=.tfvars.json

dry-run:
	terraform plan -var-file=.tfvars.json
