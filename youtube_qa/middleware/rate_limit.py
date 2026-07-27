"""
Rate limiting — SlowAPI (leaky-bucket) applied globally to all routes.

Default: 20 requests / minute per IP address.
Override via the RATE_LIMIT environment variable, e.g. "60/minute".
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import get_settings

settings = get_settings()

# Keyed by client IP; no Redis needed for single-process deployments
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])
