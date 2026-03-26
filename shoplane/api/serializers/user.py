from rest_framework import serializers

from shoplane.models import User


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Read-only output shape for the authenticated user's profile.
    Sensitive fields (password, is_staff, is_superuser) are excluded entirely.
    """

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "address", "role", "is_active", "created_at"]
        read_only_fields = fields


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Input shape for profile updates.
    Only personal fields are writable. Role, is_active, and password are not touched here.
    """

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "address"]

    def validate_first_name(self, value):
        """Prevent empty first name from being submitted."""
        if not value.strip():
            raise serializers.ValidationError("First name cannot be blank.")
        return value

    def validate_last_name(self, value):
        """Prevent empty last name from being submitted."""
        if not value.strip():
            raise serializers.ValidationError("Last name cannot be blank.")
        return value

    def validate_email(self, value):
        """Reject duplicate emails case-insensitively, excluding the current user."""
        qs = User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()
