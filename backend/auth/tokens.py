"""API-token issue + verify.

Tokens are random 32-byte URL-safe strings stored only as a SHA-256
hash on the User row. The client sends them via the
`Authorization: Bearer <token>` header.

This is intentionally simple — no JWT, no refresh flow, no signing
keys to rotate. For a self-hosted firm tool that's enough. Upgrading
to OIDC happens behind the same FastAPI dependency, so callers
don't change.

Backwards compatibility: requests without a token still resolve to a
"public" user identity carrying `user_id="public"` so dev / demo
flows keep working. The middleware tracks whether a request was
authenticated so RBAC can be enforced where it matters.
"""
from __future__ import annotations

import hashlib
import secrets


def issue_token() -> tuple[str, str]:
    """Generate (token, sha256_hash). Persist the hash; return the token to the user once."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, stored_hash: str) -> bool:
    if not token or not stored_hash:
        return False
    return secrets.compare_digest(hash_token(token), stored_hash)
