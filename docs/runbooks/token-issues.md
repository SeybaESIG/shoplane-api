# Runbook: Token Issues

## Token lifecycle

```
Login → access token (15 min) + refresh token (7 days)
           ↓ expires
       POST /auth/refresh/ → new access token + new refresh token (old refresh blacklisted)
           ↓ logout
       POST /auth/logout/ → refresh token blacklisted, access token expires naturally
```

---

## Symptom: Users getting 401 despite being logged in

### Cause 1 — Expired access token (most common)

Access tokens expire after 15 minutes. The client must call `/auth/refresh/` before expiry.

**Client-side fix**: implement token refresh logic triggered when a `401` is received or before the access token TTL expires.

**Verify the token lifetime setting:**

```bash
docker compose exec web python -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'shoplane_api.settings'
django.setup()
from django.conf import settings
print(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'])
"
```

### Cause 2 — Blacklisted refresh token

If a refresh token was used after logout (or after rotation), it is blacklisted and the user must log in again.

**Check if a token is blacklisted:**

```bash
docker compose exec web python manage.py shell -c "
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
# Find by jti (the token's unique id, visible in the JWT payload after base64 decoding)
tokens = BlacklistedToken.objects.filter(token__jti='<jti-value>')
print('blacklisted:', tokens.exists())
"
```

### Cause 3 — Clock skew between server and client

If the server clock is out of sync by more than the token lifetime, tokens may appear expired immediately.

```bash
date                     # check server time
timedatectl status       # verify NTP sync on Linux
```

---

## Forced logout: invalidate all tokens for a user

Use this when a user's account is compromised or when credentials must be revoked immediately.

```bash
docker compose exec web python manage.py shell -c "
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='user@example.com')

tokens = OutstandingToken.objects.filter(user=user)
for token in tokens:
    BlacklistedToken.objects.get_or_create(token=token)

print(f'Blacklisted {tokens.count()} token(s) for {user.email}')
"
```

After this, the user must log in again to obtain new tokens. Their existing access tokens will expire naturally within 15 minutes (access tokens cannot be revoked — this is a known JWT trade-off).

---

## Flush the entire token blacklist

The blacklist grows over time. SimpleJWT provides a management command to clear expired entries:

```bash
docker compose exec web python manage.py flushexpiredtokens
```

Run this periodically (e.g. a weekly cron job) to keep the `token_blacklist` table from growing unbounded.

---

## Adjusting token lifetimes

Token lifetimes are set in `SIMPLE_JWT` in `shoplane_api/settings/base.py`:

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    ...
}
```

Shortening the access token lifetime increases security but requires more frequent refreshes. Lengthening it reduces API calls but increases the window of exposure if a token is stolen.
