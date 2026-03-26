from rest_framework import status
from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler as drf_exception_handler

from .responses import error_response


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        return error_response(
            message="Internal server error",
            errors=None,
            code="internal_server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail = response.data
    default_code = getattr(exc, "default_code", None)
    error_code = str(default_code) if default_code is not None else None

    if isinstance(exc, Throttled):
        # Build a human-readable message including the retry window when available.
        wait = getattr(exc, "wait", None)
        if wait is not None:
            message = f"Too many requests. Retry after {int(wait)} second(s)."
        else:
            message = "Too many requests. Please slow down."

        error_resp = error_response(
            message=message,
            errors=None,
            code="throttled",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        # The Retry-After header tells the client exactly when it may retry,
        # conforming to RFC 6585 and matching the roadmap requirement.
        if wait is not None:
            error_resp["Retry-After"] = str(int(wait))
        return error_resp

    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        message = str(detail["detail"])
        errors = None
    elif response.status_code == status.HTTP_400_BAD_REQUEST:
        message = "Validation failed"
        errors = detail
    else:
        message = "Request failed"
        errors = detail

    return error_response(
        message=message,
        errors=errors,
        code=error_code,
        status_code=response.status_code,
    )
