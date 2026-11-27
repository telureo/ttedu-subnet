"""Messages signed with Bittensor keys when talking to the platform (spec §3.4, §10.3, §12.5).

Signed requests: the caller signs each request with its hotkey. The signature covers
the method, the path with its query, a timestamp, a single-use nonce, and the body
hash, so a copied request cannot be replayed or altered. A coldkey signature over the
same payload is added for the rare actions that need the owner's approval.

Tutor authorization: a miner signs `authorization_message` with its coldkey and its
hotkey. It is plain text, never a transaction, so the signature cannot move funds.
"""
import hashlib
from datetime import datetime, timezone

PREFIX = "edu-request-v1"
MAX_CLOCK_SKEW_SECONDS = 60

HOTKEY_HEADER = "X-Edu-Hotkey"
TIMESTAMP_HEADER = "X-Edu-Timestamp"
NONCE_HEADER = "X-Edu-Nonce"
SIGNATURE_HEADER = "X-Edu-Signature"
COLDKEY_HEADER = "X-Edu-Coldkey"
COLDKEY_SIGNATURE_HEADER = "X-Edu-Coldkey-Signature"

AUTHORIZATION_PURPOSE = "authorize_tutor_affiliation"
AUTHORIZATION_VERSION = "1"


def request_payload(method: str, path: str, timestamp: int, nonce: str, body: bytes) -> bytes:
    """The exact bytes that are signed. `path` includes the query string, if any."""
    return "\n".join([PREFIX, method.upper(), path, str(timestamp), nonce,
                      hashlib.sha256(body).hexdigest()]).encode()


def _utc(t: datetime) -> str:
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError(f"naive datetime {t!r}. Use timezone-aware UTC times.")
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def authorization_message(*, platform_domain: str, network_id: str, subnet_id: int, miner_hotkey: str,
                          miner_coldkey: str, tutor_account_id: str, code: str,
                          issued_at: datetime, expires_at: datetime) -> str:
    """The plain-text message the coldkey and hotkey both sign to authorize one tutor."""
    fields = [
        ("purpose", AUTHORIZATION_PURPOSE),
        ("platform_domain", platform_domain),
        ("network_id", network_id),
        ("subnet_id", str(subnet_id)),
        ("miner_hotkey", miner_hotkey),
        ("miner_coldkey", miner_coldkey),
        ("tutor_account_id", tutor_account_id),
        ("code", code),
        ("issued_at", _utc(issued_at)),
        ("expires_at", _utc(expires_at)),
        ("authorization_version", AUTHORIZATION_VERSION),
    ]
    for key, value in fields:
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key} must be a single line")
    return "\n".join(f"{key}: {value}" for key, value in fields)
