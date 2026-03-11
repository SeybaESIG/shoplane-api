import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_database_connection_allows_simple_query():
    user_model = get_user_model()

    assert user_model.objects.count() == 0
