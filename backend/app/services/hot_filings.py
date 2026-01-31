import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, TypeVar

from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from app.integrations.fmp import FMPClient, FMPEarningsEvent, fmp_client
from app.integrations.finnhub import FinnhubClient, FinnhubSentiment, finnhub_client
from app.models import Filing, UserSearch

logger = logging.getLogger(__name__)


KeyT = TypeVar("KeyT")


def _normalize(values: Dict[KeyT, float]) -> Dict[KeyT, float]:
    if not values:
        return {}
    max_value = max(values.values())
    if max_value <= 0:
        return {key: 0.0 for key in values.keys()}
    return {key: min(value / max_value, 1.0) for key, value in values.items()}


@dataclass
class HotFilingRecord:
    filing_id: int
    symbol: str
    company_name: str
    filing_type: str
    filing_date: datetime
    buzz_score: float
    sources: List[str]
    buzz_components: Dict[str, float]

    def to_dict(self) -> Dict[str, object]:
        return {
            "filing_id": self.filing_id,
            "symbol": self.symbol,
            "company_name": self.company_name,
            "filing_type": self.filing_type,
            "filing_date": self.filing_date.isoformat(),
            "buzz_score": round(self.buzz_score, 2),
            "sources": self.sources,
            "buzz_components": self.buzz_components,
        }


class HotFilingsService:
    """Service for computing and caching hot filings."""

    _cache: Dict[int, Dict[str, object]]
    _cache_expiry: Dict[int, datetime]

    def __init__(
        self,
        ttl_minutes: int = 15,
        fmp_client_instance: Optional[FMPClient] = None,
        news_client: Optional[FinnhubClient] = None,
    ) -> None:
        self._cache = {}
        self._cache_expiry = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        # Lazy lock initialization for event loop safety (created on first use)
        self._lock: Optional[asyncio.Lock] = None
        self._fmp_client = fmp_client_instance or fmp_client
        self._news_client = news_client or finnhub_client

    def _get_lock(self) -> asyncio.Lock:
        """Get or create the cache lock (lazy initialization for event loop safety)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get_hot_filings(
        self,
        db: Session,
        limit: int = 10,
        force_refresh: bool = False,
    ) -> Dict[str, object]:
        now = datetime.utcnow()

        async with self._get_lock():
            cache_entry = self._cache.get(limit)
            cache_expiry = self._cache_expiry.get(limit)

            if (
                not force_refresh
                and cache_entry is not None
                and cache_expiry is not None
                and now < cache_expiry
            ):
                return cache_entry

            records = await self._calculate_hot_filings(db, limit)
            payload = {
                "filings": [record.to_dict() for record in records],
                "last_updated": now.isoformat(),
            }

            self._cache[limit] = payload
            self._cache_expiry[limit] = now + self._ttl
            return payload

    async def _calculate_hot_filings(self, db: Session, limit: int) -> List[HotFilingRecord]:
        candidate_limit = max(limit * 3, 20)
        recent_filings = (
            db.query(Filing)
            .options(joinedload(Filing.company))
            .order_by(desc(Filing.filing_date))
            .limit(candidate_limit)
            .all()
        )

        if not recent_filings:
            return []

        company_ids = [filing.company_id for filing in recent_filings if filing.company_id]
        unique_company_ids = list({cid for cid in company_ids if cid is not None})
        now = datetime.utcnow()

        # Gather search interest over the last 7 days
        seven_days_ago = now - timedelta(days=7)
        search_interest: Dict[int, float] = {}
        if unique_company_ids:
            search_counts = (
                db.query(UserSearch.company_id, func.count(UserSearch.id))
                .filter(
                    UserSearch.company_id.in_(unique_company_ids),
                    UserSearch.created_at >= seven_days_ago,
                )
                .group_by(UserSearch.company_id)
                .all()
            )
            search_interest = {company_id: count for company_id, count in search_counts}

        # Filing velocity over the last 30 days
        thirty_days_ago = now - timedelta(days=30)
        filing_velocity: Dict[int, float] = {}
        if unique_company_ids:
            filing_counts = (
                db.query(Filing.company_id, func.count(Filing.id))
                .filter(
                    Filing.company_id.in_(unique_company_ids),
                    Filing.filing_date >= thirty_days_ago,
                )
                .group_by(Filing.company_id)
                .all()
            )
            filing_velocity = {company_id: count for company_id, count in filing_counts}

        ticker_to_company: Dict[str, int] = {
            filing.company.ticker.upper(): filing.company_id
            for filing in recent_filings
            if filing.company and filing.company_id and filing.company.ticker
        }

        tickers = set(ticker_to_company.keys())

        # Load FMP earnings calendar data
        fmp_earnings = await self._load_fmp_earnings(tickers)

        news_sentiments = await self._load_finnhub_sentiments(tickers)
        normalized_news_buzz = _normalize(
            {
                symbol: sentiment.buzz_ratio
                for symbol, sentiment in news_sentiments.items()
                if sentiment.buzz_ratio is not None
            }
        )
        normalized_news_headlines = _normalize(
            {
                symbol: sentiment.company_news_score
                for symbol, sentiment in news_sentiments.items()
                if sentiment.company_news_score is not None
            }
        )
        bullish_spread = {
            symbol: max(
                (sentiment.bullish_percent or 0.0)
                - (sentiment.sector_bullish_percent or 0.0),
                0.0,
            )
            for symbol, sentiment in news_sentiments.items()
            if sentiment.bullish_percent is not None
            and sentiment.sector_bullish_percent is not None
        }
        normalized_bullish_spread = _normalize(bullish_spread)

        normalized_search = _normalize(search_interest)
        normalized_velocity = _normalize(filing_velocity)

        today = date.today()
        hot_records: List[HotFilingRecord] = []
        for filing in recent_filings:
            if not filing.company:
                continue

            ticker = (filing.company.ticker or "").upper()
            fmp_event: Optional[FMPEarningsEvent] = (
                fmp_earnings.get(ticker) if ticker else None
            )
            sentiment: Optional[FinnhubSentiment] = (
                news_sentiments.get(ticker) if ticker else None
            )

            age_hours = (now - filing.filing_date).total_seconds() / 3600
            recency_weight = max(0.0, 1 - min(age_hours / 72.0, 1.0))
            recency_score = recency_weight * 5.0

            search_score = normalized_search.get(filing.company_id, 0.0) * 3.0
            velocity_score = normalized_velocity.get(filing.company_id, 0.0) * 2.0

            # FMP earnings calendar bonus (replaces EarningsWhispers)
            fmp_earnings_bonus = 0.0
            if fmp_event and fmp_event.earnings_date:
                days_to_earnings = (fmp_event.earnings_date - today).days
                if days_to_earnings == 0:
                    # Earnings TODAY - maximum boost
                    fmp_earnings_bonus = 4.0
                elif days_to_earnings == 1:
                    # Earnings tomorrow
                    fmp_earnings_bonus = 3.0
                elif days_to_earnings <= 3:
                    # Earnings within 3 days
                    fmp_earnings_bonus = 2.0
                elif days_to_earnings <= 7:
                    # Earnings within a week
                    fmp_earnings_bonus = 1.0
                elif days_to_earnings == -1:
                    # Just reported (yesterday) - post-earnings buzz
                    fmp_earnings_bonus = 2.5

            news_buzz_score = normalized_news_buzz.get(ticker, 0.0) * 4.0
            news_headline_score = normalized_news_headlines.get(ticker, 0.0) * 3.0
            news_sentiment_bonus = normalized_bullish_spread.get(ticker, 0.0) * 2.5

            filing_type_bonus = 0.5
            if filing.filing_type.upper() in {"10-K", "10-Q"}:
                filing_type_bonus = 1.5

            buzz_score = (
                recency_score
                + search_score
                + velocity_score
                + filing_type_bonus
                + fmp_earnings_bonus
                + news_buzz_score
                + news_headline_score
                + news_sentiment_bonus
            )

            sources: List[str] = ["recency"]

            def add_source(name: str) -> None:
                if name not in sources:
                    sources.append(name)

            if search_score > 0:
                add_source("search_activity")
            if velocity_score > 0:
                add_source("filing_velocity")
            if fmp_earnings_bonus > 0:
                add_source("earnings_calendar")
            if news_buzz_score > 0:
                add_source("finnhub_news_buzz")
            if news_headline_score > 0 or news_sentiment_bonus > 0:
                add_source("finnhub_sentiment")

            buzz_components = {
                "recency": round(recency_score, 2),
                "search_activity": round(search_score, 2),
                "filing_velocity": round(velocity_score, 2),
                "filing_type_bonus": round(filing_type_bonus, 2),
                "earnings_calendar": round(fmp_earnings_bonus, 2),
                "news_buzz": round(news_buzz_score, 2),
                "news_headlines": round(news_headline_score, 2),
                "news_sentiment": round(news_sentiment_bonus, 2),
            }

            logger.debug(
                "Hot filing computed",
                extra={
                    "filing_id": filing.id,
                    "symbol": filing.company.ticker,
                    "buzz_score": buzz_score,
                    "sources": sources,
                    "components": buzz_components,
                    "fmp_earnings_date": fmp_event.earnings_date.isoformat() if fmp_event else None,
                    "finnhub_sentiment": sentiment.raw if sentiment else None,
                },
            )

            hot_records.append(
                HotFilingRecord(
                    filing_id=filing.id,
                    symbol=filing.company.ticker,
                    company_name=filing.company.name,
                    filing_type=filing.filing_type,
                    filing_date=filing.filing_date,
                    buzz_score=buzz_score,
                    sources=sources,
                    buzz_components=buzz_components,
                )
            )

        if not hot_records:
            return []

        hot_records.sort(key=lambda record: record.buzz_score, reverse=True)
        return hot_records[:limit]


    async def _load_fmp_earnings(
        self, tickers: Set[str]
    ) -> Dict[str, FMPEarningsEvent]:
        """Load upcoming earnings events from FMP API."""
        if not tickers or not self._fmp_client:
            return {}

        try:
            # Fetch 14-day window of earnings (7 past, 7 future)
            events = await self._fmp_client.fetch_earnings_calendar()
        except Exception as exc:  # pragma: no cover - network failures
            logger.warning("Unable to load FMP earnings calendar", exc_info=exc)
            return {}

        return {symbol: event for symbol, event in events.items() if symbol in tickers}


    async def _load_finnhub_sentiments(
        self, tickers: Set[str]
    ) -> Dict[str, FinnhubSentiment]:
        if not tickers or not self._news_client:
            return {}

        try:
            return await self._news_client.fetch_news_sentiment(tickers)
        except Exception as exc:  # pragma: no cover - network failures
            logger.warning("Unable to load Finnhub sentiment", exc_info=exc)
            return {}


hot_filings_service = HotFilingsService()
