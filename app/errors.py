"""Custom exception classes."""


class OrchestratorBudgetError(Exception):
    """Raised when the orchestrator exceeds its token or tool call budget."""


class ToolNotFoundError(Exception):
    """Raised when a tool call references an unregistered tool."""


class SchemaValidationError(Exception):
    """Raised when tool input fails schema validation."""
