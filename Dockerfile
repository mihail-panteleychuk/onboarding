FROM python:3.10.12


# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1


COPY ./poetry.lock ./pyproject.toml ./site_name/ /srv/www/site_name/

RUN apt-get update && apt-get install -y \
gettext

# install poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry' \
    POETRY_HOME='/usr/local' \
    POETRY_VERSION=1.8.2

RUN curl -sSL https://install.python-poetry.org | python3 -

RUN export PATH="$HOME/.poetry/bin:$PATH"


# install dependencies

WORKDIR /srv/www/site_name

RUN poetry install --no-interaction --no-ansi
