"""API views for the shoplane app."""

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from .api.responses import success_response


@extend_schema(
    responses={200: inline_serializer(
        name="HealthResponse",
        fields={
            "success": serializers.BooleanField(default=True),
            "message": serializers.CharField(),
            "data": inline_serializer(
                name="HealthData",
                fields={
                    "service": serializers.CharField(),
                    "status": serializers.CharField(),
                },
            ),
        },
    )},
    summary="Health check",
    tags=["health"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Return a minimal payload for uptime checks and smoke tests."""
    return success_response(
        message="Health check successful",
        data={"service": "shoplane-api", "status": "ok"},
    )
