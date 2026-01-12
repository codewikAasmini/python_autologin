import os
from dotenv import load_dotenv

load_dotenv()

def get_env(key):
    value = os.getenv(key)
    if not value:
        raise Exception(f"Missing env variable: {key}")
    return value