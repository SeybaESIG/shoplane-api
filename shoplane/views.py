"""API views for the shoplane app."""

from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health(request):
    """Return a minimal payload for uptime checks and smoke tests."""
    return Response({"service": "shoplane-api", "status": "ok"})
