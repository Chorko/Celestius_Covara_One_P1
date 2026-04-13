"""
Tests for the NewsAPI civic disruption ingestion service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone


class TestBuildQuery:
    """Test the query builder for NewsAPI."""

    def test_city_specific_query(self):
        from backend.app.services.news_ingest import _build_query

        query = _build_query("Mumbai")
        assert "Mumbai" in query
        assert "strike" in query.lower() or "bandh" in query.lower()

    def test_delhi_uses_alias(self):
        from backend.app.services.news_ingest import _build_query

        query = _build_query("Delhi")
        assert "New Delhi" in query

    def test_fallback_india_wide(self):
        from backend.app.services.news_ingest import _build_query

        query = _build_query(None)
        assert "India" in query

    def test_unknown_city_falls_back(self):
        from backend.app.services.news_ingest import _build_query

        query = _build_query("Nagpur")
        assert "India" in query


class TestScoreRelevance:
    """Test the article relevance scoring."""

    def test_zero_score_for_irrelevant(self):
        from backend.app.services.news_ingest import _score_relevance

        article = {"title": "Tech startup raises funding", "description": "A tech company got money"}
        score = _score_relevance(article)
        assert score == 0.0

    def test_positive_score_for_strike(self):
        from backend.app.services.news_ingest import _score_relevance

        article = {
            "title": "Mumbai auto-rickshaw strike disrupts commute",
            "description": "City-wide closure of auto services",
        }
        score = _score_relevance(article)
        assert score > 0.0

    def test_city_bonus(self):
        from backend.app.services.news_ingest import _score_relevance

        article = {
            "title": "Strike in Mumbai causes traffic jam",
            "description": "Workers protest in Mumbai",
        }
        score_with_city = _score_relevance(article, city="Mumbai")
        score_without = _score_relevance(article, city=None)
        assert score_with_city > score_without

    def test_max_score_capped_at_1(self):
        from backend.app.services.news_ingest import _score_relevance

        article = {
            "title": "strike bandh curfew closure shutdown protest road block waterlogging flood traffic jam power outage platform outage delivery ban GRAP",
            "description": "Mumbai Delhi strike curfew closure protest waterlogging",
        }
        score = _score_relevance(article, city="Mumbai")
        assert score <= 1.0


class TestFetchNewsAPI:
    """Test the NewsAPI fetch function."""

    @pytest.mark.asyncio
    async def test_no_key_returns_error(self):
        from backend.app.services.news_ingest import _fetch_newsapi

        result = await _fetch_newsapi(city="Mumbai", key="")
        assert result["error"] == "no_api_key"
        assert result["articles"] == []

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        from backend.app.services.news_ingest import _fetch_newsapi

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "totalResults": 2,
            "articles": [
                {
                    "title": "Mumbai strike causes traffic chaos",
                    "description": "Auto-rickshaw drivers in Mumbai went on a 24-hour strike today",
                    "url": "https://example.com/article1",
                    "source": {"name": "Times of India"},
                    "publishedAt": "2026-03-15T10:00:00Z",
                    "urlToImage": "https://example.com/img1.jpg",
                },
                {
                    "title": "Tech company launches new app",
                    "description": "A new mobile application was released",
                    "url": "https://example.com/article2",
                    "source": {"name": "TechCrunch"},
                    "publishedAt": "2026-03-15T09:00:00Z",
                    "urlToImage": None,
                },
            ],
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await _fetch_newsapi(city="Mumbai", key="test-key-123")

        assert result["provider"] == "newsapi"
        assert result["city"] == "Mumbai"
        assert result["total_results"] == 2
        assert len(result["articles"]) == 2
        # First article should have higher relevance (has "strike" keyword)
        assert result["articles"][0]["relevance_score"] >= result["articles"][1]["relevance_score"]
        assert result["articles"][0]["title"] == "Mumbai strike causes traffic chaos"


class TestFetchCivicNews:
    """Test the public API function."""

    @pytest.mark.asyncio
    async def test_no_providers_returns_warning(self):
        from backend.app.services.news_ingest import news_pool

        # When no providers configured
        original_count = news_pool.provider_count
        if original_count == 0:
            from backend.app.services.news_ingest import fetch_civic_news

            result = await fetch_civic_news(city="Mumbai")
            assert result.get("warning") == "no_news_providers_configured"
            assert result["data"]["articles"] == []


class TestNewsPoolHealth:
    """Test health reporting."""

    def test_health_report_structure(self):
        from backend.app.services.news_ingest import get_news_pool_health

        health = get_news_pool_health()
        assert "pool" in health
        assert health["pool"] == "news"
        assert "total_providers" in health
        assert "healthy_count" in health
        assert "providers" in health
