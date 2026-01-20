import argparse

from config.environment import VAULT_ROOT, VAULT_STORAGE, vault_client


def dump_vault_secrets(storage_name, key, output_file):
    """
    Dumps vault secrets into a .env file.
    ./web_app/config/dump_vault_secrets.py --storage_name inhome --key local/backend --output_file tmp.env

    Args:
        storage_name (str): The storage name to fetch secrets from.
        key (str): The key path to fetch secrets.
        output_file (str): The file to output secrets to.
    """
    secrets = vault_client.get_secrets(storage_name=storage_name, key=key)
    with open(output_file, "w") as f:
        for k, v in secrets.items():
            f.write(f"{k}={v}\n")
    print(f"Secrets dumped to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dump vault secrets into a .env file.")
    parser.add_argument(
        "--storage_name",
        type=str,
        default=VAULT_STORAGE,
        required=False,
        help="The storage name to fetch secrets from.",
    )
    parser.add_argument(
        "--key",
        type=str,
        default=VAULT_ROOT,
        required=False,
        help="The key path to fetch secrets.",
    )
    parser.add_argument(
        "--output_file",
        default="tmp.env",
        required=False,
        help="The file to output secrets to.",
    )

    args = parser.parse_args()
    dump_vault_secrets(storage_name=args.storage_name, key=args.key, output_file=args.output_file)
