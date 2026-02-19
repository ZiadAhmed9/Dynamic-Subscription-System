"""Custom business exception classes.

Each exception maps to a specific HTTP status code and error code
for consistent API error responses.
"""


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)


class ResourceNotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, resource_id: int | str):
        super().__init__(
            message=f"{resource} with id {resource_id} not found",
            error_code="RESOURCE_NOT_FOUND",
            status_code=404,
        )


class ValidationError(AppError):
    """Raised when input validation fails."""

    def __init__(self, message: str, details: dict | None = None):
        self.details = details or {}
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
        )


class RuleViolationError(AppError):
    """Raised when a subscription request violates plan rules."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__(
            message="Subscription request violates plan rules",
            error_code="RULE_VIOLATION",
            status_code=422,
        )


class PricingError(AppError):
    """Raised when pricing calculation encounters an unsupported configuration."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_code="PRICING_ERROR",
            status_code=422,
        )
