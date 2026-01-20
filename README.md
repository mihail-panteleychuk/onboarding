InHome API
==========

## TABLE OF CONTENT:

1. [**MAIN DEPENDENCIES**](#main-dependencies)
1. [**Start Project**](#start-project)
1. [**DEPENDENCIES MANAGEMENT**](#dependencies-management)
1. [**Initial Database Start Up**](#initial-database-start-up)
1. [**Create Django SuperUser**](#create-django-superuser)
1. [**DJANGO APPLICATIONS DESCRIPTION**](#django-applications-description)
1. [**Postman Api documentation and Swagger**](#postman-api-documentation-and-swagger)
1. [**Make Comands**](#make-comands)
1. [**Pre-commit**](#pre-commit)



## **MAIN DEPENDENCIES**
* [Python 3.10](https://www.python.org/downloads/release/python-3100/)
* [poetry==1.8.2](https://python-poetry.org/)
* [Django==4.0](https://docs.djangoproject.com/en/4.0/)
* [djangorestframework==3.12.4](https://www.django-rest-framework.org/)
* [djangorestframework-simplejwt==4.6.0](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/)
* check full list in [pyproject.toml](./pyproject.toml)

* * *
* * *

## **Start Project:**

### To run project as docker service
1.  Rename folders from `site_name` to necessary name

1.  Rename project name in [pyproject.toml](./pyproject.toml)

2.  Install [docker & docker-compose]((https://docs.docker.com/compose/install/))

3.  Build docker containers:
    *   LOCAL:
        ```bash
        make build-local
        ```
    *   REMOTE:
        ```bash
        make build
        ```

4.  **[NO NEED FOR LOCAL]** Configuration nginx and ssl certificates in docker
    * [LINK TO DOCS](https://pentacent.medium.com/nginx-and-lets-encrypt-with-docker-in-less-than-5-minutes-b4b8a60d3a71)

5.  Set up finished 👍



### If you want to run project outside the DockerContainer and contribute this repo:

1.  Install [docker & docker-compose]((https://docs.docker.com/compose/install/))

2.  [install poetry](https://python-poetry.org/docs/#installation)

3.  Install dependencies.
Check details for make commands in [Make Comands](#make-comands) section
    * REMOTE:
        ```bash
        make install
        ```
    * LOCAL:
        ```bash
        make install-dev
        ```
4.  Run the project
    ```bash
    poetry run python manage.py runserver
    ```

* * *

* * *


## **DEPENDENCIES MANAGEMENT**

### Dependencies installation
Run command
```bash
make install
```
OR for local development
```bash
make install-dev
```
to install few additional packages for code formatting / testing / pre-commmit-hook configuration

### Dependencies updating
Just follow up with the [poetry docs](https://python-poetry.org/docs/cli):

* [poetry add](https://python-poetry.org/docs/cli/#add)
* [poetry remove](https://python-poetry.org/docs/cli/#remove)
* [poetry update](https://python-poetry.org/docs/cli/#update)

* * *
* * *


### **Initial Database Start Up**

If you need to set-up new database, you should follow next steps:

__NOTE__: All the above commands expecting that project is already running in docker container

1.  Run migrations for empty DB initialization:

    *   Check if any migrations should be generated and create them
        ```bash
            docker exec -it django python3 manage.py makemigrations
        ```
        OR use a shortcut
        ```bash
            make django command='makemigrations'
        ```
    *   [OPTIONAL] Merge multiple leaf migrations into one if such exists
        ```bash
            docker exec -it django python3 manage.py makemigrations --merge
        ```
        OR use a shortcut
        ```bash
            make django command='makemigrations --merge'
        ```
    *   Apply migrations to create empty database
        ```bash
            docker exec -it django python3 manage.py migrate
        ```
        OR use a shortcut
        ```bash
            make django command='migrate'
        ```

3.  run django-command for fill up [`Country` Table ](dropship/user/models.py#L264):
    ```bash
        docker exec -it django python3 manage.py add_countries
    ```
    OR use a shortcut
    ```bash
        make django command='add_countries'
    ```

* * *
* * *

### **Create Django SuperUser:**

1.  Run command:
    ```bash
        docker exec -it django python3 manage.py add_admin_user
    ```
    OR use a shortcut
    ```bash
        make django command='add_admin_user'
    ```

3.  Follow the instructions in console

* * *

* * *


### **Postman Api documentation and Swagger**
Project could be fully imported as postman API Documentation and Postman Collection.

To import API to Postmen - follow steps below:

1.  Export collection json-file for postmen import by url - /api/api.json
2.  Got to postman
3.  Press Import => File
4.  Select previously downloaded file
5.  Follow the insturctions in Postman

* * *

* * *

### **DJANGO APPLICATIONS DESCRIPTION**

**user**

*   General application with customers data and techichal tables such as: CompanyDetails, Country, ConfrimCode.

**authentication**

*   Application with sign-up/in logic, social auth, social-accounts management

*   Logic of creating new customer with email verification
*   Logic of reseting password in case if customer forgot it. Confirmation emails.
*   Handling different situation such as: email already exists, credentials incorrect, etc
*   Connecting/disconecting social accounts from customer profile
*   Generating/Refreshing JWT token pair (Access/Refresh) to grant user access
*   Supported socials: Google, Facebook, Apple

**admin\_panel**

*   General application for Admin user operations. To get access to views customer must be with ADMIN/MANAGER role.
*   Customer managements

*   _Retrieve list of customers and their general data_
*   _Filtering, ordering and searching customers_
*   _Updating customer information_
*   _Creating new customers with email confirmation or not_

**config**

*   Base Django config directory with \`settings.py\`, \`wsgi.py\`, etc.

**core**

*   Application with some general features such as middlewares, BaseModel, Exception handler, etc.

1.  \`LangBasedOnUserSettingsMiddleware\` - Middleware for detecting language of responses by user selected language.
2.  \`RequestLogMiddleware\` - Middleware for logging all information about requests and their responses.
3.  \`rest\_framework\_custom\_exception\_handler\` - function to unify all error responses to structure {'message': {'detail': ""}}
4.  \`BaseUuidModel\` - base parent model for almost all project models. Provide UUID as primary-key, add datetime field of objects create and last\_update actions.
5.  \`utils.py\` - provide some general function for sending different emails. Added for DRY.

**dashboard**

*   Almost empty application used as basic page for redirect after user sucessfull registration/onboarding steps
*   Provide one endpoint which returns up-to-date user info.

**payments**

*   Application that contains all the logic to interact with Stripe(Payment Service)
*   [Stripe API Docs](https://stripe.com/docs/api)
*   All general functions are providen in \`utils.py\`
*   \`views.py\` - provide:

1.  \`CreateCardView\` - creating card as payment method for customer and attach it in payment service
2.  \`CreateSubscriptionView\` - create subscription for cusotmer and process paymment. Card could be passed also like to \`CreateCardView\`
3.  \`UpdateSubscriptionView\` - subscription management operations like : downgrade/upgrade (shceduled), cancel, renew cancel schedule subscription
4.  \`InvoiceViewSet\` - Payment history for user(list of invoices, and thier details)
5.  \`StripeWebhookView\` - Processing webhooks from stripe such as: payment success/failed, subscription update, etc.

**subscription**

*   Application that store Subscription and available Plan objects.
*   Provide basic endpoint for retrieveing list of plans. Also provide active susbcription or list of subscription history by user

* * *

* * *

**POSSIBLE FRAGMENTATION** **Disable onboarding and activate user account after email confirmation (password creating)**

*   You need to change environment variable \`ONBOARDING\_ENABLED\`:

1.  True - flag 'onboarding finished' is setting to \`True\` after user create subscription and finish checkout.s
2.  False - flag 'onboarding finished' is setting to \`True\` after user sign-up by socail or confirm password.

**Disable social auth**

1.  Remove:

*   all \`socail/\` urls in application \`authentication\`
*   classes \`AppleOAuth2\`, \`AppleTokenView\`, \`GoogleTokenView\`, \`FacebookTokenView\` from views.py in application \`authentication\`
*   social fields from user model and their serializers in \`user\` app

**Diable subscriptions and onboarding**

*   Remove applications \`subscription\` and \`payments\` from project and INSTALLED\_APPS in \`settings.py\`
*   Remove serializing subscription field in \`FullUserInfoSerializer\`
*   Clean environment file and \`settings.py\` from stripe keys
*   Set up environment variable \`ONBOARDING\_ENABLED\` to _False_

* * *

* * *

**Make Comands** This project has few prepared commands for that should make your life a bit easier.

1.  make install

*   Installing all listed in "./dropship/requirements.txt" dependencies

3.  make install-dev

*   Doing same as \`make install\` but addding few additional packages for local development like: pre-commit, flake8, isort, etc. These packages are necessary for local auto formatting and keeping code beautiful

5.  make uninstall-dev

*   Removing all packages that were installed by previous command.

7.  make lint

*   Checking whole project for code styling, and outputs problems to terminal

9.  make format

*   Trying to automatically fix discovered problems. You can double check applied changes with git.

#### After all segmentations described below - clean \`requirements.txt\` from unused packages

* * *

* * *

* * *

* * *
### **Make Comands**

This project has few prepared commands for that should make your life a bit easier.

1.  Installing all listed in [pyproject.toml](./pyproject.toml) dependencies
```bash
    make install
```

2.  Doing same as `make install` but addding few additional packages for local development like: pre-commit, flake8, isort, etc. These packages are necessary for local auto formatting and keeping code beautiful
```bash
    make install-dev
```
3.  Disabling pre-commit hooks
```bash
    make uninstall-dev
```
4.  Checking whole project for code styling, and outputs problems to terminal
```bash
    make lint
```

5.  Trying to automatically fix discovered problems. You can double check applied changes with git before commiting.
```bash
    make format
```

5.  Building the project inside docker containers
    * For **REMOTE** build
    ```bash
        make build
    ```

    * For **LOCAL** build
    ```bash
        make build-local
    ```

5.  Restart running docker containers
    * For **REMOTE** build
    ```bash
        make restart
    ```

    * For **LOCAL** build
    ```bash
        make restart-local
    ```

6.  Running django command inside docker container. Used to not type long commands in terminal.
    * Just use this
        ```bash
            make django command={some_command}
        ```
    * instead of this
        ```bash
            docker exec -it django python manage.py {some_command}
        ```
* * *

* * *

### **Pre-commit**

For local development prepared pre-commit module, that handles additional formatting and code style problems.

To enable it just run **make install-dev** command. After that it will automatically process all files added to commit, and makes refactor changes, so you should double check output and new changes in files.

**It will block commit action until all problems will be solved**

* * *

* * *
