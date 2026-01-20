# How to use Vault and .env

## How to start project with Vault

* create empty `.env` file in `web_app` folder (just to be able to override it later) which should never be commited;
* You need to copy `vault.env.example` to `vault.env`;
* set proper `VAULT_LOGIN_METHOD` (if it differs from `"github"`);
* change `VAULT_USERNAME` and `VAULT_PASSWORD` with your credentials to Vault storage;
* then set `VAULT_STORAGE` there with the name of your secret engine name (project name);
* and if you want to use other than `"local/backend"` secrets you need to edit `VAULT_ROOT`;

## How to override values from Value with .env

* any variable that you need override (after retrieving from Vault) can be changed within `.env` file
* just put variable there and restart containers

## How to make offline copy

run following command from bash:
```bash
./web_app/config/dump_vault_secrets.py --storage_name inhome --key local/backend --output_file tmp.env
```

# Typical structure of Vault storage can look like:

* **accounts**:
  * admin_user:
    * username
    * password
    * notes
  * shared_user:
    * username
    * password
    * notes
  * email_account:
    * username
    * password
    * email_provider
* **local**:s
  * accounts:
  * backend:
  * frontend:
* **dev**:
  * accounts:
  * backend:
  * frontend:
  * databases: (if dedicated service)
    * postgres:
    * redis:
* **staging**: (if needed)
  * accounts:
  * backend:
  * frontend:
  * databases:
    * postgres:
    * redis:
* **prod**: (if in production already)
  * accounts:
  * backend:
  * frontend:
  * databases:
    * postgres:
    * redis:
* **monitoring**:
  * credentials:
  * configs:

# Example of .env file

```bash
{
  "ENVIRONMENT": "local",

  "API_DOMAIN": "http://localhost:8000",
  "AWS_ACCESS_KEY": "",
  "AWS_BUCKET_NAME": "site_name-media",
  "AWS_REGION": "us-east-1",
  "AWS_SECRET_KEY": "",
  "AWS_USE_SSL": "True",
  "CELERY_BROKER_URL": "redis://redis:6379/0",
  "CELERY_RESULT_BACKEND": "redis://redis:6379/1",
  "CELERY_TASK_ALWAYS_EAGER": "False",
  "DEFAULT_PASSWORD": "tkNhreb9hW=Qq5A57shnKredXSnjd\\@ZW@e=tU9Nz*5wCZahvb~7<4kk~P>]FG7;]98pYETvJ:wmWTVrSra5QwTSq>9w{qVk3GD92^B",
  "EMAIL_HOST_PASSWORD": "replace-with-real-password",
  "EMAIL_HOST_USER": "dev@dataforest.ai",
  "FERNET_SECRET_KEY": "",
  "FRONT_DOMAIN": "http://localhost:3000",
  "ONBOARDING_ENABLED": "True",
  "POSTGRES_DB": "site_name",
  "POSTGRES_HOST": "db",
  "POSTGRES_PASSWORD": "qwety12351994qwerty",
  "POSTGRES_PORT": "5432",
  "POSTGRES_USER": "postgres",
  "SECRET_KEY": "django-insecure-abcdefghijklmnopqrstuvwxyz123456",
  "SENTRY_DSN": "",
  "STRIPE_ACCOUNT_ID": "",
  "STRIPE_PUBLISHABLE_KEY": "",
  "STRIPE_SECRET_KEY": "",
  "STRIPE_WEBHOOK_SECRET": "",
  "SWAGGER_URL": "api/v1/swagger/",
  "TRANSLATION_GOOGLE_SHEET_ID": "1LlTYk2uP4_psKWNgTq4r0bfYWEl2xB5GBEokZdzA1t4",
  "USE_S3": "False"
}
```
