"""
Covara One — Civic Disruption Ingestion Service

Polls GDELT Project APIs for protest, curfew, bandh, and strike events
in Indian cities. Creates T10 (ZONE_CLOSURE) and T11 (CURFEW) trigger
events when civic disruptions are detected.

GDELT is free and requires no API key.
"""

from __future__ import annotations

import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger("covara.disruption_ingest")

# ── Keywords that map to trigger codes ──────────────────────────────
DISRUPTION_KEYWORDS = {
    "curfew": {"trigger_code": "CURFEW", "trigger_family": "closure", "severity_band": "claim"},
    "bandh": {"trigger_code": "ZONE_CLOSURE", "trigger_family": "closure", "severity_band": "claim"},
    "protest": {"trigger_code": "ZONE_CLOSURE", "trigger_family": "closure", "severity_band": "watch"},
    "strike": {"trigger_code": "ZONE_CLOSURE", "trigger_family": "closure", "severity_band": "watch"},
    "road blockade": {"trigger_code": "ZONE_CLOSURE", "trigger_family": "closure", "severity_band": "claim"},
    "flood": {"trigger_code": "WATERLOGGING", "trigger_family": "access", "severity_band": "claim"},
}


async def fetch_gdelt_disruptions(city: str, max_records: int = 10) -> list[dict]:
    """
    Search GDELT DOC API for recent disruption articles mentioning the city.
    Returns a list of article summaries.
    """
    keywords = "protest OR curfew OR bandh OR strike OR flood"
    query = f"{keywords} {city} India"
    url = (
        f"https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={query}&mode=artlist&maxrecords={max_records}"
        f"&format=json&sort=DateDesc"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"GDELT returned {resp.status_code} for {city}")
                return []
            data = resp.json()

        articles = data.get("articles", [])
        results = []
        for article in articles:
            title = (article.get("title") or "").lower()
            url = article.get("url", "")
            date = article.get("seendate", "")

            # Determine which disruption type was found
            matched_keyword = None
            for keyword in DISRUPTION_KEYWORDS:
                if keyword in title:
                    matched_keyword = keyword
                    break

            if matched_keyword:
                results.append({
                    "keyword": matched_keyword,
                    "title": article.get("title", ""),
                    "url": url,
                    "date": date,
                    "source": article.get("domain", ""),
                    **DISRUPTION_KEYWORDS[matched_keyword],
                })

        return results

    except Exception as e:
        logger.error(f"GDELT fetch failed for {city}: {e}")
        return []


async def evaluate_disruptions(
    sb, city: str, zone_id: str, max_records: int = 10
) -> list[dict]:
    """
    Fetch GDELT disruptions for a city and create trigger_events
    for any matched disruption keywords.
    """
    from backend.app.services.trigger_evaluator import _is_on_cooldown, _create_trigger_event

    articles = await fetch_gdelt_disruptions(city, max_records)
    if not articles:
        return []

    created = []
    for article in articles:
        code = article["trigger_code"]
        family = article["trigger_family"]
        band = article["severity_band"]

        if _is_on_cooldown(sb, zone_id, family):
            continue

        event = _create_trigger_event(
            sb=sb,
            trigger_code=code,
            zone_id=zone_id,
            city=city,
            observed_value=1.0,  # Binary: disruption detected
            severity_band=band,
            description=f"GDELT: {article['keyword']} — {article['title'][:100]}",
            source_provider="gdelt",
        )
        if event:
            created.append(event)
            break  # One trigger per family per scan is enough

    return created
