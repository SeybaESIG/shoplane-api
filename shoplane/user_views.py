from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .api.responses import success_response
from .api.serializers import UserProfileSerializer, UserProfileUpdateSerializer


class MeView(APIView):
    """
    Handles the authenticated user's own profile.
    Users can only read and update their own data -- no cross-user access.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: UserProfileSerializer},
        summary="Get own profile",
        tags=["users"],
    )
    def get(self, request):
        """Return the profile of the currently authenticated user."""
        serializer = UserProfileSerializer(request.user)
        return success_response(
            message="Profile retrieved successfully",
            data=serializer.data,
        )

    @extend_schema(
        request=UserProfileUpdateSerializer,
        responses={200: UserProfileSerializer},
        summary="Update own profile",
        tags=["users"],
    )
    def patch(self, request):
        """
        Partially update the authenticated user's profile.
        Role, password, and account status fields are ignored even if submitted.
        """
        serializer = UserProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return success_response(
            message="Profile updated successfully",
            data=UserProfileSerializer(user).data,
        )
