import os
from pathlib import Path

import environ

# Get the base directory (web_app/)
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()

# Read .env file from web_app directory
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file=str(env_file), overwrite=True)
