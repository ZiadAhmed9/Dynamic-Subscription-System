"""Consistent API response helpers.

Returns plain dicts (not Flask Response objects) because Flask-RESTX
handles JSON serialisation automatically.
"""


def success_response(data, status_code: int = 200):
    """Return a standardised success dict with HTTP status code.

    Args:
        data: Serialisable payload.
        status_code: HTTP status code (default 200).
    """
    return {"status": "success", "data": data}, status_code


def error_response(
    message: str,
    error_code: str = "INTERNAL_ERROR",
    status_code: int = 500,
    details=None,
):
    """Return a standardised error dict with HTTP status code."""
    body = {
        "status": "error",
        "error_code": error_code,
        "message": message,
    }
    if details:
        body["details"] = details
    return body, status_code
