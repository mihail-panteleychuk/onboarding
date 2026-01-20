source = site_name
line_length = 99
flake8 = poetry run flake8 --config=.flake8 --statistics
black = poetry run black -S -l $(line_length)
isort = poetry run isort --settings-file .isort.cfg -l $(line_length)

container_name = django

.PHONY: lint
lint:
	poetry run pre-commit run --all-files

.PHONY: format
format:
	$(isort) $(source)
	$(black) $(source)


.PHONY: install
install:
	poetry install --only-root


.PHONY: install-dev
install-dev:
	poetry install --with local
	poetry run pre-commit install


.PHONY: uninstall-dev
uninstall-dev:
	poetry run pre-commit uninstall


# build project in docker

.PHONY: build
build:
	docker-compose -f docker-compose.yml up --build -d

.PHONY: restart
restart:
	docker-compose -f docker-compose.yml restart

# local build project in docker
.PHONY: build-local
build-local:
	docker-compose -f local.docker-compose.yml up --build -d


.PHONY: restart-local
restart-local:
	docker-compose -f local.docker-compose.yml restart


# execute django-admin commands inside running docker

.PHONY: django
# shortcut for executiong django-admin commands inside docker container
# shortcut expects a `command` argument to be passed.
# Ex: `make django command=collectstatic`
django:
	docker exec -it $(container_name) python manage.py $(command)
