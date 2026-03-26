from rest_framework import serializers

from shoplane.models import Category


class CategoryReadSerializer(serializers.ModelSerializer):
    """Output shape for category responses (read-only, includes computed fields)."""

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "is_active", "created_at", "updated_at"]


class CategoryWriteSerializer(serializers.ModelSerializer):
    """Input shape for create and update requests. Slug is excluded -- auto-generated on save."""

    class Meta:
        model = Category
        fields = ["name", "description", "is_active"]

    def validate_name(self, value):
        """Reject duplicate names, case-insensitively. Excludes the current instance on updates."""
        qs = Category.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value
