"""
Cache utilities for list endpoint caching.

Pattern: cache versioning. Each namespace (e.g. "products") has a version
integer stored in cache. Every cache key embeds that version. Invalidation
increments the version, making all prior keys unreachable without needing
to enumerate or delete them individually. Compatible with any Django cache
backend (Redis in production, LocMem in tests).
"""

import urllib.parse

from django.core.cache import cache


def _version_key(namespace: str) -> str:
    return f"cache_version:{namespace}"


def _get_version(namespace: str) -> int:
    return cache.get(_version_key(namespace), 0)


def build_list_cache_key(namespace: str, request) -> str:
    """
    Build a deterministic cache key for a list endpoint.
    Query params are sorted so ?a=1&b=2 and ?b=2&a=1 resolve to the same key.
    """
    version = _get_version(namespace)
    params = sorted(request.query_params.items())
    query_string = urllib.parse.urlencode(params)
    return f"{namespace}:v{version}:{query_string}"


def invalidate_list_cache(namespace: str) -> None:
    """
    Invalidate all cached pages for a namespace by bumping the version.
    All keys built before this call become unreachable.
    Errors are silenced: the cache is an optimisation layer, never a hard dependency.
    """
    version_key = _version_key(namespace)
    try:
        cache.incr(version_key)
    except ValueError:
        cache.set(version_key, 1)
    except Exception:
        pass
