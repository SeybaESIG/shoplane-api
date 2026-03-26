from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenVerifyView

from .api.responses import success_response
from .api.throttles import LoginRateThrottle, RefreshRateThrottle

User = get_user_model()


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class RegisterResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class RefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class RefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class JWTLogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class EnvelopeSerializer(serializers.Serializer):
    """Base envelope matching success_response shape."""
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    data = serializers.DictField()


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=RegisterSerializer,
        responses={201: EnvelopeSerializer},
        summary="Register a new user",
        tags=["auth"],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return success_response(
            message="Registration successful",
            data={
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            status_code=status.HTTP_201_CREATED,
        )


class JWTLoginView(APIView):
    permission_classes = [AllowAny]
    # Tight per-IP throttle to limit brute-force credential attacks.
    throttle_classes = [LoginRateThrottle]

    @extend_schema(
        request=LoginRequestSerializer,
        responses={200: EnvelopeSerializer},
        summary="Obtain JWT access + refresh tokens",
        tags=["auth"],
    )
    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc

        return success_response(
            message="Login successful",
            data=serializer.validated_data,
            status_code=status.HTTP_200_OK,
        )


class JWTRefreshView(APIView):
    permission_classes = [AllowAny]
    # Per-IP throttle to prevent refresh token enumeration and replay abuse.
    throttle_classes = [RefreshRateThrottle]

    @extend_schema(
        request=RefreshRequestSerializer,
        responses={200: EnvelopeSerializer},
        summary="Refresh an access token",
        tags=["auth"],
    )
    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc

        return success_response(
            message="Token refreshed successfully",
            data=serializer.validated_data,
            status_code=status.HTTP_200_OK,
        )


class JWTVerifyView(TokenVerifyView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Verify a token is still valid",
        tags=["auth"],
    )
    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)
        return success_response(
            message="Token is valid",
            data={},
            status_code=status.HTTP_200_OK,
        )


class JWTLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=JWTLogoutSerializer,
        responses={200: EnvelopeSerializer},
        summary="Blacklist a refresh token (logout)",
        tags=["auth"],
    )
    def post(self, request):
        serializer = JWTLogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh"]
        token = RefreshToken(refresh_token)
        token.blacklist()

        return success_response(
            message="Logout successful",
            data={},
            status_code=status.HTTP_200_OK,
        )
