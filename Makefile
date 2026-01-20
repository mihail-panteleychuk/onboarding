source = site_name
line_length = 99
flake8 = flake8 --max-line-length=$(line_length) --ignore=F405,F403,W503 --statistics
black  = black -S -l $(line_length)
isort  = isort --gitignore --profile black -l $(line_length)

.PHONY: lint
lint:
	$(flake8) --exit-zero $(source)
	$(isort) --check-only $(source)
	$(black) --check $(source)

.PHONY: format
format:
	$(isort) $(source)
	$(black) $(source)


.PHONY: install
install:
	pip install --upgrade pip
	pip install -r site_name/requirements.txt


.PHONY: install-dev
install-dev:
	pip install --upgrade pip isort black flake8 pre-commit
	pip install -r site_name/requirements.txt
	pre-commit install

.PHONY: uninstall-dev
uninstall-dev:
	pre-commit uninstall
	pip uninstall -r site_name/requirements.txt -y
	pip uninstall isort black flake8 pre-commit -y
