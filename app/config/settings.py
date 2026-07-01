"""
Application settings.

Loads configuration from .env file.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:

    GITHUB_OWNER = os.getenv("GITHUB_OWNER")

    GITHUB_REPO = os.getenv("GITHUB_REPO")

    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

    GITHUB_BASE_BRANCH = os.getenv(
        "GITHUB_BASE_BRANCH",
        "main"
    )


settings = Settings()