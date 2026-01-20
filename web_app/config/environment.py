import logging
import os

import environ
import requests
from environ import Env

logger = logging.getLogger(__name__)

# Only for initial setup when project logging setup wasn't done yet
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)-23s %(levelname)-8s %(name)s %(funcName)s:%(lineno)-7d %(message)s",
)


class HashicorpVault:
    def __init__(self, base_url: str, username: str, password: str, login_method: str):
        if login_method not in ("token", "userpass", "github"):
            raise ValueError('Auth method must be one of "token", "userpass", "github"')
        self.base_url = base_url
        self.token = None
        self.session = requests.session()
        self._vault_login(username, password, login_method)
        if self.token is not None:
            self.session.headers["X-Vault-Token"] = self.token
        else:
            self.session.headers.pop("X-Vault-Token", None)

    def is_enabled(self) -> bool:
        return self.token is not None

    def raise_if_not_enabled(self):
        if not self.is_enabled():
            raise PermissionError("Vault is not enabled or not authenticated")

    def _vault_login(self, username: str, password: str, login_method: str) -> None:
        if login_method == "token":
            self.session.headers["X-Vault-Token"] = self.token
            # NOTE: that following URL just validates token
            login_url = f"{self.base_url}/v1/auth/{login_method}/lookup-self"
            payload = {}
        elif login_method == "userpass":
            login_url = f"{self.base_url}/v1/auth/{login_method}/login/{username}"
            payload = {"password": password}
        elif login_method == "github":
            login_url = f"{self.base_url}/v1/auth/{login_method}/login"
            payload = {"token": password}
        else:
            raise ValueError(f"Invalid login_method {login_method}")
        try:
            response = requests.post(login_url, json=payload)
            try:
                response.raise_for_status()
                data = response.json()
                self.token = data.get("auth", {}).get("client_token")
                if self.token:
                    logger.debug("Authenticated successfully! Token obtained.")
                else:
                    logger.warning(
                        "Authentication succeeded, but no token was found in the response.",
                    )
            except requests.HTTPError as e:
                logger.exception(
                    "Vault raised error '%s'. Status: %s: Response: %s",
                    e,
                    response.status_code,
                    response.text,
                )
        except requests.RequestException as e:
            logger.exception(f"Vault error occurred during authentication: {e}")

    def get_secret_keys(self, storage_name: str, key: str = None) -> list:
        self.raise_if_not_enabled()
        result = self.session.get(
            f"{self.base_url}/v1/{storage_name}/metadata/{key or ''}?list=true",
        ).json()
        logger.info("Vault key list retrieved for storage %s. Result: '%s'", storage_name, result)
        return result["data"]["keys"]

    def get_secrets(self, storage_name: str, key: str) -> dict:
        self.raise_if_not_enabled()
        result = self.session.get(f"{self.base_url}/v1/{storage_name}/data/{key}").json()
        logger.debug(
            "Vault secret retrieved for key '%s' in storage '%s'. Response: '%s'",
            key,
            storage_name,
            result,
        )
        secrets = result.get("data", {}).get("data", {})
        return secrets

    def upsert_secret(self, storage_name: str, key: str, secret: dict) -> str:
        self.raise_if_not_enabled()
        result = self.session.post(f"{self.base_url}/{storage_name}/{key}", json=secret).text
        logger.debug(
            "Vault secret upserted for '%s' in storage '%s'. Response: '%s'",
            key,
            storage_name,
            result,
        )
        return result

    def remove_secret(self, storage_name: str, key: str) -> int:
        self.raise_if_not_enabled()
        result = self.session.delete(self.base_url + f"/{storage_name}/{key}")
        logger.debug(
            "Vault secret removed for '%s' in storage '%s'. Response: '%s'",
            key,
            storage_name,
            result,
        )
        return result.status_code


class SSMClient:
    def __init__(self, aws_access_key_id, aws_secret_access_key, region_name):
        import boto3

        resource = "ssm"
        self.client = boto3.client(
            resource,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )

    def get_secrets(self, ssm_path: str) -> dict:
        parameters = []
        next_token = None
        while True:
            response = self.client.get_parameters_by_path(
                Path=ssm_path,
                Recursive=True,
                NextToken=next_token if next_token else "",
                WithDecryption=True,
            )
            parameters.extend(response["Parameters"])
            next_token = response.get("NextToken")
            if not next_token:
                break

        secrets = {}
        for parameter in sorted(parameters, key=lambda x: x["Name"]):
            parameter_name = parameter["Name"].rsplit("/", 1)[-1]
            parameter_value = parameter["Value"]
            secrets[parameter_name] = parameter_value
        return secrets


# Read secrets from Hashicorp Vault
VAULT_ENABLED = os.getenv("VAULT_ENABLED", default="false").lower() == "true"
VAULT_BASE_URL = os.getenv("VAULT_BASE_URL", default="https://vault.dataforest.tech")
VAULT_LOGIN_METHOD = os.getenv("VAULT_METHOD", default="github")
VAULT_USERNAME = os.getenv("VAULT_USERNAME")
VAULT_PASSWORD = os.getenv("VAULT_PASSWORD")

VAULT_ENVIRONMENT = os.getenv("VAULT_ENVIRONMENT", default="local")
VAULT_STORAGE = os.getenv("VAULT_STORAGE", default="simplex")
VAULT_ROOT = os.getenv("VAULT_ROOT", default=f"{VAULT_ENVIRONMENT}/backend")

if VAULT_ENABLED:
    vault_client = HashicorpVault(
        base_url=VAULT_BASE_URL,
        username=VAULT_USERNAME,
        password=VAULT_PASSWORD,
        login_method=VAULT_LOGIN_METHOD,
    )
    vault_secrets = vault_client.get_secrets(storage_name=VAULT_STORAGE, key=VAULT_ROOT)
else:
    vault_client = None
    vault_secrets = {}


# Read secrets from AWS SSM
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_SSM_REGION = os.environ.get("AWS_DEFAULT_REGION")
AWS_SSM_PATH = os.environ.get("AWS_SSM_PATH")
AWS_SSM_ENABLED = os.environ.get("AWS_SSM_ENABLED", default="false").lower() == "true"

if AWS_SSM_ENABLED:
    ssm_client = SSMClient(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_SSM_REGION,
    )
    ssm_secrets = ssm_client.get_secrets(AWS_SSM_PATH)
else:
    ssm_secrets = {}


CURRENT_FILE_DIRECTORY = environ.Path(__file__) - 1
BASE_DIR = CURRENT_FILE_DIRECTORY - 1

env = Env()
# This allows to init with Vault & SSM and override with local .env version
env.read_env(env_file=os.path.join(BASE_DIR, ".env"), **vault_secrets, **ssm_secrets)


# TODO: you can use `dotenv` for local development, but it doesn't have type validation
# from dotenv import dotenv_values
#
# # Combine secrets and configs from different sources and apply to `os.environ`:
# env_config = {
#     **vault_secrets,
#     **ssm_secrets,
#     **dotenv_values(".env"),
# }
#
# for key, value in env_config.items():
#     os.environ.update({key: str(value)})
