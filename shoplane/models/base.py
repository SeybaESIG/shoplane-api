from django.db import models
from django.utils.text import slugify


def generate_unique_slug(instance, model_class, source_value, fallback):
    """Generate a unique slug by appending an incrementing suffix if needed."""
    base_slug = slugify(source_value) or fallback
    candidate = base_slug
    counter = 2
    while model_class.objects.filter(slug=candidate).exclude(pk=instance.pk).exists():
        candidate = f"{base_slug}-{counter}"
        counter += 1
    return candidate


class TimeStampedModel(models.Model):
    """Shared timestamps for core domain entities."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
