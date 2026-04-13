"""
Covara One — News / Civic Disruption Ingestion Service

Polls civic disruption news from NewsAPI to support trigger families T10–T11
(zone closures, curfews, strikes, civic disruptions).

Uses the same ApiProviderPool pattern as weather_ingest and aqi_ingest.

Configuration:
  Set NEWS_API_KEY in .env to activate the NewsAPI provider.
  Without a key the pool is empty and fetch_civic_news() returns a
  graceful empty result — no crash, no runtime error.

How it works:
  1. Queries NewsAPI /v2/everything with city-specific civic disruption
     keywords (strike, curfew, closure, bandh, flood, protest).
  2. Returns normalized articles with relevance scoring.
  3. High-relevance articles feed into trigger evaluation for T10/T11.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from ..config import settings
from .api_pool import ApiProvider, ApiProviderPool

logger = logging.getLogger("covara.news_ingest")

# ── Civic disruption keyword sets per language ────────────────────────────
# These keywords are tuned for Indian gig-worker disruption scenarios.
CIVIC_KEYWORDS = [
    "strike", "bandh", "curfew", "closure", "shutdown",
    "protest", "road block", "waterlogging", "flood",
    "traffic jam", "power outage", "platform outage",
    "delivery ban", "two wheeler ban", "GRAP",
]

# City name mapping for NewsAPI queries
CITY_QUERY_NAMES = {
    "Mumbai": "Mumbai",
    "Delhi": "Delhi OR New Delhi",
    "Bangalore": "Bangalore OR Bengaluru",
    "Hyderabad": "Hyderabad",
    "Chennai": "Chennai",
    "Kolkata": "Kolkata",
    "Pune": "Pune",
    "Ahmedabad": "Ahmedabad",
}


def _build_query(city: str | None = None) -> str:
    """Build a NewsAPI query string for civic disruptions in a city."""
    keyword_group = " OR ".join(f'"{kw}"' for kw in CIVIC_KEYWORDS[:8])
    if city and city in CITY_QUERY_NAMES:
        return f"({CITY_QUERY_NAMES[city]}) AND ({keyword_group})"
    # Fallback: India-wide civic disruption search
    return f"(India) AND ({keyword_group})"


def _score_relevance(article: dict, city: str | None = None) -> float:
    """Score an article's relevance to gig-worker disruptions (0.0–1.0)."""
    text = (
        (article.get("title") or "")
        + " "
        + (article.get("description") or "")
    ).lower()

    score = 0.0

    for kw in CIVIC_KEYWORDS:
        if kw.lower() in text:
            score += 0.12

    # City match bonus
    if city and city.lower() in text:
        score += 0.15

    # Recency bonus (articles from last 6 hours)
    published = article.get("publishedAt", "")
    if published:
        try:
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
            if age_hours < 6:
                score += 0.15
            elif age_hours < 24:
                score += 0.05
        except (ValueError, TypeError):
            pass

    return min(round(score, 3), 1.0)


# ── NewsAPI Provider ─────────────────────────────────────────────────────


async def _fetch_newsapi(
    city: str | None = None,
    key: str = "",
    lookback_days: int = 3,
    page_size: int = 20,
    **_,
) -> dict:
    """Fetch civic disruption news from NewsAPI /v2/everything."""
    if not key:
        return {
            "provider": "newsapi",
            "articles": [],
            "total_results": 0,
            "error": "no_api_key",
        }

    query = _build_query(city)
    from_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime(
        "%Y-%m-%d"
    )

    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={query}"
        f"&from={from_date}"
        f"&sortBy=publishedAt"
        f"&pageSize={page_size}"
        f"&language=en"
        f"&apiKey={key}"
    )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    articles_raw = data.get("articles", [])
    total = data.get("totalResults", 0)

    # Normalize and score articles
    articles = []
    for art in articles_raw:
        relevance = _score_relevance(art, city)
        articles.append({
            "title": art.get("title"),
            "description": art.get("description"),
            "url": art.get("url"),
            "source": (art.get("source") or {}).get("name"),
            "published_at": art.get("publishedAt"),
            "relevance_score": relevance,
            "image_url": art.get("urlToImage"),
        })

    # Sort by relevance descending
    articles.sort(key=lambda a: a["relevance_score"], reverse=True)

    return {
        "provider": "newsapi",
        "city": city,
        "query": query,
        "total_results": total,
        "articles": articles,
        "high_relevance_count": sum(
            1 for a in articles if a["relevance_score"] >= 0.30
        ),
    }


# ── Build the news pool ──────────────────────────────────────────────────

news_pool = ApiProviderPool("news", cache_ttl_seconds=600, cache_maxsize=64)

# Register NewsAPI if key is available
if settings.news_api_key:
    _key = settings.news_api_key

    async def _bound_newsapi(city=None, _k=_key, **kw):
        return await _fetch_newsapi(city=city, key=_k, **kw)

    news_pool.add_provider(
        ApiProvider(name="newsapi", fetch_fn=_bound_newsapi, priority=1)
    )
    logger.info("News pool initialized with NewsAPI provider")
else:
    logger.warning(
        "NEWS_API_KEY not set — news civic disruption feed is disabled. "
        "Set NEWS_API_KEY in .env to activate T10/T11 civic triggers."
    )


# ── Public API ───────────────────────────────────────────────────────────


async def fetch_civic_news(city: str | None = None) -> dict:
    """Fetch civic disruption news for a city via the resilient pool.

    Returns a normalized response with scored articles. If no provider
    is configured, returns an empty result (never raises).
    """
    if news_pool.provider_count == 0:
        return {
            "data": {
                "provider": None,
                "city": city,
                "articles": [],
                "total_results": 0,
                "high_relevance_count": 0,
            },
            "provider": None,
            "cached": False,
            "pool": "news",
            "warning": "no_news_providers_configured",
        }

    result = await news_pool.call(city=city)
    if result.get("error"):
        logger.error(f"Civic news fetch failed: {result}")
    return result


def get_news_pool_health() -> dict:
    """Returns health status of the news provider pool."""
    return news_pool.get_health_report()
