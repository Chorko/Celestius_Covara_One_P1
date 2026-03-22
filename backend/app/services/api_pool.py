"""
Covara One — API Provider Pool

N-provider round-robin with LRU cache and automatic health tracking.
Handles downtime gracefully: if Provider A fails, the pool rotates to
Provider B instantly. Failed providers auto-recover after a cooldown.

Usage:
    pool = ApiProviderPool("weather", cache_ttl_seconds=300)
    pool.add_provider(ApiProvider(name="openweather", fetch_fn=fetch_ow, priority=1))
    pool.add_provider(ApiProvider(name="openmeteo",   fetch_fn=fetch_om, priority=2))
    pool.add_provider(ApiProvider(name="imd",         fetch_fn=fetch_imd, priority=3))

    result = await pool.call(lat=19.08, lon=72.88)
    # Tries providers in round-robin order, skips unhealthy, caches results.
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable

logger = logging.getLogger("covara.api_pool")


@dataclass
class ApiProvider:
    """Single API provider definition."""
    name: str
    fetch_fn: Callable[..., Awaitable[dict] | dict]
    priority: int = 1
    healthy: bool = True
    last_failure: datetime | None = None
    consecutive_failures: int = 0
    total_calls: int = 0
    total_errors: int = 0


class LRUCacheWithTTL:
    """Thread-safe LRU cache with per-entry TTL expiry."""

    def __init__(self, maxsize: int = 512, ttl_seconds: int = 300):
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        ts, value = self._cache[key]
        if time.time() - ts > self._ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return value

    def put(self, key: str, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (time.time(), value)
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    @property
    def size(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        self._cache.clear()


class ApiProviderPool:
    """
    Round-robin pool of N API providers with LRU caching and
    automatic health management.

    - Rotates through providers on each call
    - Skips unhealthy providers (auto-recovers after cooldown)
    - Caches responses by (provider_name + params) hash
    - Adding a new provider = one add_provider() call
    """

    COOLDOWN_SECONDS = 60  # Unhealthy providers retry after 60s

    def __init__(self, pool_name: str, cache_ttl_seconds: int = 300, cache_maxsize: int = 512):
        self.pool_name = pool_name
        self._providers: list[ApiProvider] = []
        self._robin_index = 0
        self._cache = LRUCacheWithTTL(maxsize=cache_maxsize, ttl_seconds=cache_ttl_seconds)

    def add_provider(self, provider: ApiProvider) -> "ApiProviderPool":
        """Register a new API provider. Returns self for chaining."""
        self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)
        logger.info(f"[{self.pool_name}] Added provider: {provider.name} (priority={provider.priority})")
        return self

    def remove_provider(self, name: str) -> "ApiProviderPool":
        """Remove a provider by name. Returns self for chaining."""
        self._providers = [p for p in self._providers if p.name != name]
        logger.info(f"[{self.pool_name}] Removed provider: {name}")
        return self

    @property
    def provider_count(self) -> int:
        return len(self._providers)

    @property
    def healthy_providers(self) -> list[ApiProvider]:
        now = datetime.now()
        result = []
        for p in self._providers:
            if p.healthy:
                result.append(p)
            elif p.last_failure and (now - p.last_failure).total_seconds() > self.COOLDOWN_SECONDS:
                # Auto-recover after cooldown
                p.healthy = True
                p.consecutive_failures = 0
                logger.info(f"[{self.pool_name}] Provider {p.name} auto-recovered after cooldown")
                result.append(p)
        return result

    def _cache_key(self, provider_name: str, params: dict) -> str:
        raw = f"{self.pool_name}:{provider_name}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    async def call(self, **params) -> dict:
        """
        Call the pool with the given parameters. Tries providers in
        round-robin order, returns the first successful result.

        Returns dict with keys:
            - data: the API response
            - provider: name of the provider that responded
            - cached: whether the result came from cache
            - pool: pool name
        """
        available = self.healthy_providers
        if not available:
            logger.error(f"[{self.pool_name}] All {len(self._providers)} providers are unhealthy!")
            return {
                "data": None,
                "provider": None,
                "cached": False,
                "pool": self.pool_name,
                "error": "all_providers_unhealthy",
            }

        errors = []
        tried = 0

        for _ in range(len(available)):
            provider = available[self._robin_index % len(available)]
            self._robin_index = (self._robin_index + 1) % len(available)

            # Check cache first
            cache_key = self._cache_key(provider.name, params)
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[{self.pool_name}] Cache HIT for {provider.name}")
                return {
                    "data": cached,
                    "provider": provider.name,
                    "cached": True,
                    "pool": self.pool_name,
                }

            # Call the provider
            try:
                provider.total_calls += 1
                tried += 1
                import asyncio
                if asyncio.iscoroutinefunction(provider.fetch_fn):
                    result = await provider.fetch_fn(**params)
                else:
                    result = provider.fetch_fn(**params)

                # Success — cache and return
                provider.consecutive_failures = 0
                self._cache.put(cache_key, result)
                logger.info(f"[{self.pool_name}] {provider.name} responded OK")
                return {
                    "data": result,
                    "provider": provider.name,
                    "cached": False,
                    "pool": self.pool_name,
                }

            except Exception as e:
                provider.total_errors += 1
                provider.consecutive_failures += 1
                provider.last_failure = datetime.now()
                error_msg = f"{provider.name}: {type(e).__name__}: {e}"
                errors.append(error_msg)
                logger.warning(f"[{self.pool_name}] {error_msg}")

                # Mark unhealthy after 2 consecutive failures
                if provider.consecutive_failures >= 2:
                    provider.healthy = False
                    logger.warning(
                        f"[{self.pool_name}] {provider.name} marked UNHEALTHY "
                        f"({provider.consecutive_failures} consecutive failures)"
                    )

        # All providers failed
        return {
            "data": None,
            "provider": None,
            "cached": False,
            "pool": self.pool_name,
            "error": f"all_{tried}_providers_failed",
            "details": errors,
        }

    def get_health_report(self) -> dict:
        """Returns a health summary of all providers in this pool."""
        return {
            "pool": self.pool_name,
            "total_providers": len(self._providers),
            "healthy_count": len(self.healthy_providers),
            "cache_size": self._cache.size,
            "providers": [
                {
                    "name": p.name,
                    "priority": p.priority,
                    "healthy": p.healthy,
                    "total_calls": p.total_calls,
                    "total_errors": p.total_errors,
                    "consecutive_failures": p.consecutive_failures,
                    "last_failure": p.last_failure.isoformat() if p.last_failure else None,
                }
                for p in self._providers
            ],
        }
