"""Advisory-lock helpers for anti-stampede deduplication.

Uses PostgreSQL advisory locks keyed by a hash of the ingest parameters
to prevent multiple concurrent warm runs from duplicating work.
"""

import hashlib


def compute_lock_key(*parts: str) -> int:
    """Compute a stable 32-bit integer lock key from string parts.

    PostgreSQL advisory locks accept bigint keys. We use a 32-bit hash
    to stay comfortably in range while providing sufficient uniqueness
    for our use case (one lock per warm operation type).
    """
    combined = "|".join(parts)
    digest = hashlib.sha256(combined.encode()).hexdigest()
    return int(digest[:8], 16)
