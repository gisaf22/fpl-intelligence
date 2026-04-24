class DataFreshnessError(Exception):
    """Raised when fpl.db is stale or missing for the current GW."""


class BriefingValidationError(Exception):
    """Raised when briefing.json fails hard validation rules."""


class SchemaContractError(Exception):
    """Raised when a signal output violates the canonical schema."""
