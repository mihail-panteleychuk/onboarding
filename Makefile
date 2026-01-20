source = .
line_length = 99
flake8 = cd web_app && poetry run flake8 --config=.flake8 --statistics
black = cd web_app && poetry run black -S -l $(line_length)
isort = cd web_app && poetry run isort --settings-file .isort.cfg -l $(line_length)

service_name = django

VAULT_ADDR=https://vault.dataforest.tech
ENGINE_NAME=inhome
SECRET_PATH=develop/backend

.PHONY: vault
vault:
	@GITHUB_TOKEN=$${GITHUB_TOKEN:-$$(test -f .github_token && cat .github_token)}; \
	if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Enter your GitHub Personal Access Token: " && \
		read -s GITHUB_TOKEN; \
	fi; \
	export VAULT_ADDR=$(VAULT_ADDR) && \
	VAULT_TOKEN=$$(vault login -method=github token=$$GITHUB_TOKEN -format=json | jq -r '.auth.client_token') && \
	echo "Fetching secrets from Vault at $(ENGINE_NAME)/$(SECRET_PATH)..." && \
	vault kv get -mount=${ENGINE_NAME} -format=json ${SECRET_PATH} | jq -r '.data.data | to_entries | map("\(.key)=\(.value)") | .[]' > .env && \
	echo ".env file generated successfully."

.PHONY: vault-clean
vault-clean:
	@echo "Cleaning Vault-related files..."
	rm -f .env


.PHONY: lint
lint:
	cd web_app && poetry run pre-commit run --all-files

.PHONY: format
format:
	$(isort) $(source)
	$(black) $(source)


.PHONY: install
install:
	cd web_app && poetry install --only-root


.PHONY: install-dev
install-dev:
	cd web_app && poetry install --with local
	cd web_app && poetry run pre-commit install


.PHONY: uninstall-dev
uninstall-dev:
	cd web_app && poetry run pre-commit uninstall


# build project in docker

.PHONY: build
build:
	docker compose build

.PHONY: up
up:
	docker compose up --build -d

.PHONY: down
down:
	docker compose down

.PHONY: restart-local
restart:
	docker compose restart

.PHONY: logs
logs:
	docker compose logs -f

# execute django-admin commands inside running docker

.PHONY: exec
exec:
	docker compose exec -it $(service_name) $(cmd)

.PHONY: bash
bash:
	make exec cmd="bash"

.PHONY: manage
manage:
	make exec cmd="python manage.py $(cmd)"

.PHONY: shell
shell:
	make manage cmd="shell"

.PHONY: migrations
migrations:
	make manage cmd="makemigrations"

.PHONY: migrate
migrate:
	make manage cmd="migrate"

.PHONY: static
static:
	make manage cmd="collectstatic"

.PHONY: backup
backup:
	docker compose exec -t db pg_dumpall -c -U postgres > dump_`date +%Y-%m-%d"_"%H_%M_%S`.sql

.PHONY: lock
lock:
	make exec cmd="poetry lock --no-update"
