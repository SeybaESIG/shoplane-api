import os

from .base import *  # noqa: F401,F403

DJANGO_ENV = os.getenv("DJANGO_ENV", "dev").lower()

if DJANGO_ENV == "prod":
    from .prod import *  # noqa: F401,F403
elif DJANGO_ENV == "staging":
    from .staging import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
