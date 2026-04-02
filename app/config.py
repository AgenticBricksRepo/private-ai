"""Environment variable validation. Runs at import time — app refuses to start if misconfigured."""

import os

REQUIRED_ENV_VARS_ALWAYS = [
    "DATABASE_URL",
    "S3_BUCKET",
    "S3_ENDPOINT_URL",
    "AWS_REGION",
    "SECRET_KEY",
]

REQUIRED_ENV_VARS_SSO = [
    "AUTH_CLIENT_ID",
    "AUTH_CLIENT_SECRET",
    "AUTH_ISSUER_URL",
]


def validate_env():
    """Validate that all required environment variables are set.
    Called during create_app(), not at module import, so tests can set env first.
    """
    missing = [v for v in REQUIRED_ENV_VARS_ALWAYS if not os.environ.get(v)]

    # At least one model API key is required
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    if not has_anthropic and not has_openai:
        missing.append("ANTHROPIC_API_KEY or OPENAI_API_KEY (at least one)")

    auth_mode = os.environ.get("AUTH_MODE", "sso")
    if auth_mode == "sso":
        missing.extend(v for v in REQUIRED_ENV_VARS_SSO if not os.environ.get(v))

    if missing:
        raise EnvironmentError(f"Required environment variables not set: {missing}")


class Config:
    """Flask configuration loaded from environment."""

    def __init__(self):
        self.SECRET_KEY = os.environ["SECRET_KEY"]
        self.DATABASE_URL = os.environ["DATABASE_URL"]
        self.S3_BUCKET = os.environ["S3_BUCKET"]
        self.S3_ENDPOINT_URL = os.environ["S3_ENDPOINT_URL"]
        self.AWS_REGION = os.environ["AWS_REGION"]
        self.AUTH_MODE = os.environ.get("AUTH_MODE", "sso")
        self.DEV_USER_EMAIL = os.environ.get("DEV_USER_EMAIL", "dev@localhost")
        self.ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
        self.OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
        self.AUTH_CLIENT_ID = os.environ.get("AUTH_CLIENT_ID")
        self.AUTH_CLIENT_SECRET = os.environ.get("AUTH_CLIENT_SECRET")
        self.AUTH_ISSUER_URL = os.environ.get("AUTH_ISSUER_URL")
        self.TESTING = False
