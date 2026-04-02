"""All named constants. No magic values anywhere else in the codebase."""

from enum import StrEnum


class SupportedModel(StrEnum):
    CLAUDE_SONNET = "claude-sonnet-4-6"
    GPT_4O = "gpt-4o"


# Context and budget limits
MAX_CONTEXT_TOKENS = 190_000
MAX_TOOL_CALLS_PER_SESSION = 20
FOLDER_TIER1_MAX_TOKENS = 180_000
FOLDER_TIER2_THRESHOLD = 50  # docs

# Headless agent execution
HEADLESS_RUN_TIMEOUT_SECONDS = 3600

# Auth
SESSION_TOKEN_EXPIRY_SECONDS = 86_400

# Tool executor
TOOL_EXPECTED_ERROR_CODES = {400, 401, 403, 404, 408, 422, 429}

# Session recordings
RECORDING_RETENTION_MIN_DAYS = 1
RECORDING_RETENTION_MAX_DAYS = 3650

# Eval
EVAL_MODEL = SupportedModel.CLAUDE_SONNET

# Token estimation (words-to-tokens rough ratio)
TOKENS_PER_WORD = 1.3
