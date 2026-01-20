ARG INSTALL_DEV_LIBS

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl git openssh-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# install poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry' \
    POETRY_HOME='/usr/local' \
    POETRY_VERSION=1.8.2

RUN curl -sSL https://install.python-poetry.org | python3 -

RUN export PATH="$HOME/.poetry/bin:$PATH"

# set work directory
WORKDIR /web_app

# install dependencies
COPY web_app/poetry.lock web_app/pyproject.toml /web_app/

# RUN poetry lock --no-update  # NOTE: this can be used on project creation

RUN if [ "INSTALL_DEV_LIBS" = "true" ] ; then  \
    poetry install --no-interaction --no-ansi --with local  \
    ; else  \
    poetry install --no-interaction --no-ansi  \
    ; fi


# copy project files
COPY ./web_app/ /web_app

RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /web_app
USER appuser