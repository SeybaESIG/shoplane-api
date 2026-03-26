from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Per-IP throttle for the login endpoint. Scope: 'login'."""

    scope = "login"


class RefreshRateThrottle(AnonRateThrottle):
    """Per-IP throttle for the token refresh endpoint. Scope: 'refresh'."""

    scope = "refresh"


class UserWriteRateThrottle(UserRateThrottle):
    """Per-user throttle for authenticated write operations. Scope: 'user_write'."""

    scope = "user_write"


class UserReadRateThrottle(UserRateThrottle):
    """Per-user throttle for authenticated read operations. Scope: 'user_read'."""

    scope = "user_read"
