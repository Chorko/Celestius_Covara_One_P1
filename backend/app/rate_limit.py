"""
Rate limiting primitives shared across app and routers.
"""

from __future__ import annotations

import time
from typing import Any

from slowapi import Limiter
from slowapi.util import get_remote_address


def build_adaptive_rate_limit_headers(
	limiter_instance: Limiter,
	current_limit: tuple[Any, list[str]] | None,
	now_epoch: float | None = None,
) -> dict[str, str]:
	"""
	Build RFC-style rate-limit headers from the current slowapi limit state.

	Returns an empty dict when limit metadata is unavailable.
	"""
	if not current_limit:
		return {}

	try:
		limit_item, limit_scope_args = current_limit
		reset_epoch, remaining = limiter_instance.limiter.get_window_stats(
			limit_item,
			*limit_scope_args,
		)
		now_ref = now_epoch if now_epoch is not None else time.time()
		reset_seconds = max(0, int(reset_epoch - now_ref))
		window_seconds = max(1, int(limit_item.get_expiry()))

		headers = {
			"RateLimit-Limit": str(limit_item.amount),
			"RateLimit-Remaining": str(max(0, int(remaining))),
			"RateLimit-Reset": str(reset_seconds),
			"RateLimit-Policy": f"{limit_item.amount};w={window_seconds}",
		}

		if int(remaining) <= 0:
			headers["Retry-After"] = str(max(1, reset_seconds))

		return headers
	except Exception:
		return {}


limiter = Limiter(
	key_func=get_remote_address,
	headers_enabled=True,
)
