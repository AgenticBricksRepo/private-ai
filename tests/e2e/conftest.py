"""E2E test fixtures — Playwright with live Flask server."""

import os
import threading
import time

import pytest


@pytest.fixture(scope="session")
def live_server():
    """Start Flask on a background thread for E2E tests."""
    os.environ.update({
        "DATABASE_URL": "postgresql://private_ai:private_ai@localhost:5432/private_ai",
        "S3_BUCKET": "private-ai",
        "S3_ENDPOINT_URL": "http://localhost:9000",
        "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "minioadmin",
        "AWS_SECRET_ACCESS_KEY": "minioadmin",
        "SECRET_KEY": "test-secret-key",
        "AUTH_MODE": "dev",
        "ANTHROPIC_API_KEY": "test-key",
        "OPENAI_API_KEY": "test-key",
    })

    from app import create_app
    app = create_app(testing=True)

    server = threading.Thread(
        target=lambda: app.run(port=5099, use_reloader=False),
        daemon=True,
    )
    server.start()
    time.sleep(2)  # Wait for startup
    yield "http://localhost:5099"
