from rest_framework.response import Response


def success_response(*, data=None, message="Request successful", meta=None, status_code=200):
    payload = {
        "success": True,
        "message": message,
        "data": data,
    }
    if meta is not None:
        payload["meta"] = meta
    return Response(payload, status=status_code)


def error_response(*, message, errors=None, code=None, status_code=400):
    return Response(
        {
            "success": False,
            "message": message,
            "errors": errors,
            "code": code,
        },
        status=status_code,
    )
