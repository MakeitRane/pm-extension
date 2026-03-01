"""
Kalshi API Service
Handles fetching markets and analyzing them with Gemini for causal relevance
Uses REST API for market fetching and WebSocket for real-time price updates
"""

import asyncio
import logging
import requests
import re
from typing import Optional, List, Dict
import time

logger = logging.getLogger(__name__)

from gemini_service import (
    GeminiError,
    GeminiRateLimitError,
    GeminiAuthError,
    GeminiUnavailableError,
    GeminiNotConfiguredError
)

KALSHI_API_BASE = 'https://api.elections.kalshi.com/trade-api/v2'

# Cache for event data
_event_cache = {}

# Cache for series data
_series_cache = {}

# Cache for market list
_market_list_cache = {
    'data': None,
    'timestamp': None,
    'ttl': 300  # 5 minutes
}


class KalshiService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        private_key: Optional[str] = None,
        gemini_service=None
    ):
        """
        Initialize Kalshi service.

        Args:
            api_key: Optional Kalshi API key ID for authenticated requests
            private_key: Optional RSA private key PEM for WebSocket authentication
            gemini_service: GeminiService for causal market analysis (required)
        """
        self.api_key = api_key
        self.private_key = private_key
        self.gemini_service = gemini_service
        self._ws_enabled = bool(api_key and private_key)

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to the Kalshi API."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        url = f'{KALSHI_API_BASE}{endpoint}'

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error("Kalshi API error: %s", e)
            raise

    def _build_market_about(self, market: Dict) -> str:
        """
        Build a structured 'about' string for a market.
        Format: "TITLE. Category. Closes DATE. Resolves YES if: RULE"

        This provides richer context for Gemini analysis.

        Args:
            market: Market dictionary

        Returns:
            Structured about string
        """
        title = market.get('title', '')
        category = market.get('category', '')
        close_time = market.get('close_time', '')
        rules = market.get('rules_primary', '') or market.get('rules', '')
        subtitle = market.get('subtitle', '')
        yes_sub_title = market.get('yes_sub_title', '')

        # Extract first rule sentence (up to first period or 150 chars)
        first_rule = ''
        if rules:
            first_rule = rules.split('.')[0][:150]
        elif yes_sub_title:
            first_rule = yes_sub_title[:150]

        # Format close time nicely if available
        close_str = ''
        if close_time:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(close_time.replace('Z', '+00:00'))
                close_str = dt.strftime('%b %d, %Y')
            except:
                close_str = close_time[:10]  # Just the date part

        # Build the about string
        parts = [title]
        if subtitle and subtitle != title:
            parts.append(subtitle)
        if category:
            parts.append(f"Category: {category}")
        if close_str:
            parts.append(f"Closes: {close_str}")
        if first_rule:
            parts.append(f"Resolves YES if: {first_rule}")

        return '. '.join(parts)

    def _slugify(self, text: str) -> str:
        """
        Convert text to URL-friendly slug.

        Args:
            text: Text to convert (e.g., "UFC Fight")

        Returns:
            URL-friendly slug (e.g., "ufc-fight")
        """
        if not text:
            return ''
        # Convert to lowercase
        slug = text.lower()
        # Replace spaces and underscores with hyphens
        slug = re.sub(r'[\s_]+', '-', slug)
        # Remove any characters that aren't alphanumeric or hyphens
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        # Remove consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        return slug

    def get_event(self, event_ticker: str) -> Optional[Dict]:
        """
        Get event details by ticker.
        Uses caching to avoid repeated API calls.

        Args:
            event_ticker: Event ticker

        Returns:
            Event data or None
        """
        global _event_cache

        # Check cache first
        if event_ticker in _event_cache:
            return _event_cache[event_ticker]

        try:
            response = self._make_request(f'/events/{event_ticker}')
            event = response.get('event')
            if event:
                _event_cache[event_ticker] = event
            return event
        except Exception as e:
            logger.error("Error fetching event %s: %s", event_ticker, e)
            return None

    def get_series(self, series_ticker: str) -> Optional[Dict]:
        """
        Get series details by ticker.
        Uses caching to avoid repeated API calls.

        Args:
            series_ticker: Series ticker (e.g., "KXUFCFIGHT")

        Returns:
            Series data or None
        """
        global _series_cache

        # Check cache first
        if series_ticker in _series_cache:
            return _series_cache[series_ticker]

        try:
            response = self._make_request(f'/series/{series_ticker}')
            series = response.get('series')
            if series:
                _series_cache[series_ticker] = series
            return series
        except Exception as e:
            logger.error("Error fetching series %s: %s", series_ticker, e)
            return None

    def get_market_url(self, market: Dict) -> str:
        """
        Build the proper Kalshi market URL.

        URL format: https://kalshi.com/markets/{series_ticker}/{series_title_slug}/{event_ticker}

        Args:
            market: Market dictionary with ticker and event_ticker

        Returns:
            Full Kalshi market URL
        """
        event_ticker = market.get('event_ticker', '')
        ticker = market.get('ticker', '')

        if not event_ticker:
            if ticker:
                return f'https://kalshi.com/markets/{ticker.lower()}'
            return 'https://kalshi.com/markets'

        # Get event details to find series_ticker
        event = self.get_event(event_ticker)

        if not event:
            return f'https://kalshi.com/markets/{event_ticker.lower()}'

        series_ticker = event.get('series_ticker', '')

        if not series_ticker:
            return f'https://kalshi.com/markets/{event_ticker.lower()}'

        # Get series details to find title
        series = self.get_series(series_ticker)

        if series:
            series_title = series.get('title', '')
            series_slug = self._slugify(series_title)
        else:
            series_slug = self._slugify(series_ticker.replace('KX', '', 1))

        if not series_slug:
            series_slug = series_ticker.lower()

        return f'https://kalshi.com/markets/{series_ticker.lower()}/{series_slug}/{event_ticker.lower()}'

    def fetch_markets(self, status: str = 'open', limit: int = 200, exclude_mve: bool = True) -> List[Dict]:
        """
        Fetch markets from Kalshi API.

        Args:
            status: Market status filter ('open', 'closed', etc.)
            limit: Max markets per request
            exclude_mve: Exclude multivariate/combo markets (default True)

        Returns:
            List of market dictionaries
        """
        all_markets = []
        cursor = None

        # Fetch up to 1000 markets (5 pages)
        for _ in range(5):
            params = {
                'limit': limit,
                'status': status
            }

            if exclude_mve:
                params['mve_filter'] = 'exclude'

            if cursor:
                params['cursor'] = cursor

            response = self._make_request('/markets', params)

            markets = response.get('markets', [])
            all_markets.extend(markets)

            cursor = response.get('cursor')
            if not cursor:
                break

        return all_markets

    def _is_spread_or_total_market(self, market: Dict) -> bool:
        """
        Detect if a market is a spread or total points market.

        These markets have multiple variations for the same event
        (e.g., "Team wins by 5+ points", "Team wins by 10+ points")
        and should be deduplicated.

        Args:
            market: Market dictionary

        Returns:
            True if this is a spread/total market that should be deduplicated
        """
        ticker = market.get('ticker', '').upper()
        title = market.get('title', '').lower()

        # Check ticker patterns for spread/total markets
        spread_ticker_patterns = ['SPREAD', 'TOTAL', 'SPRD']
        for pattern in spread_ticker_patterns:
            if pattern in ticker:
                return True

        # Check title patterns for spread markets
        spread_title_patterns = [
            'wins by over',
            'wins by under',
            'by over',
            'by under',
            'wins by more than',
            'wins by less than',
            'total points',
            'over/under',
            'points scored',
            '.5 points',  # Common in spreads like "by 7.5 points"
        ]
        for pattern in spread_title_patterns:
            if pattern in title:
                return True

        # Check for numeric spread patterns like "by X+" or "by X.5"
        import re
        spread_regex = r'by\s+\d+\.?\d*\s*\+?\s*points?'
        if re.search(spread_regex, title):
            return True

        return False

    def get_all_open_markets(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get all open markets with caching and smart deduplication.

        Only spread/total markets are deduplicated by event_ticker.
        Other markets (championship winners, game winners, etc.) are all kept.

        Args:
            force_refresh: Force refresh of cache

        Returns:
            List of open markets with spread markets deduplicated
        """
        global _market_list_cache
        from datetime import datetime, timezone

        # Check cache
        if (not force_refresh
            and _market_list_cache['data'] is not None
            and _market_list_cache['timestamp'] is not None
            and time.time() - _market_list_cache['timestamp'] < _market_list_cache['ttl']):
            logger.info("Using cached markets (%d markets)", len(_market_list_cache['data']))
            return _market_list_cache['data']

        logger.info("Fetching fresh markets from Kalshi API...")

        # Fetch fresh markets
        raw_markets = self.fetch_markets(status='open', exclude_mve=True)
        logger.info("Fetched %d markets from Kalshi API", len(raw_markets))

        # Filter to only truly open markets
        now = datetime.now(timezone.utc).isoformat()
        open_markets = []
        for market in raw_markets:
            status = market.get('status', '').lower()
            close_time = market.get('close_time') or market.get('expiration_time')

            is_open_status = status in ['open', 'active']
            is_not_expired = close_time and close_time > now

            if is_open_status and is_not_expired:
                open_markets.append(market)

        logger.info("Filtered to %d open markets", len(open_markets))

        # Smart deduplication: only dedupe spread/total markets
        # Keep all other markets (championship winners, game winners, etc.)
        seen_spread_events = set()
        deduplicated_markets = []
        spread_count = 0

        for market in open_markets:
            if self._is_spread_or_total_market(market):
                # For spread/total markets, dedupe by event_ticker
                event_ticker = market.get('event_ticker', market.get('ticker'))
                if event_ticker not in seen_spread_events:
                    seen_spread_events.add(event_ticker)
                    deduplicated_markets.append(market)
                else:
                    spread_count += 1
            else:
                # Keep all non-spread markets
                deduplicated_markets.append(market)

        logger.info("Removed %d duplicate spread/total markets", spread_count)
        logger.info("Final market count: %d", len(deduplicated_markets))

        # Update cache
        _market_list_cache['data'] = deduplicated_markets
        _market_list_cache['timestamp'] = time.time()

        return deduplicated_markets

    def search_markets(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for markets related to query using two-stage Gemini filtering.

        Seven-step approach:
        1. Get all open markets from Kalshi API
        2. Stage 1 (gemini-3-flash-preview): Filter ALL markets to top 50 by relevance
        3. Build rich 'about' strings for filtered markets
        4. Stage 2 (gemma-3-27b-it): Analyze for causal relationships (top 5)
        5. Build full response with market URLs and event data
        6. Update prices via WebSocket (if authenticated)
        7. Group markets by event for cleaner display

        Args:
            query: Highlighted text from frontend
            top_k: Number of results to return

        Returns:
            List of event groups, each containing:
            - event_ticker: Event identifier
            - event_title: Display title for the event
            - event_subtitle: Subtitle if available
            - explanation: Causal explanation from Gemini
            - markets: List of individual outcome markets with prices

        Raises:
            GeminiNotConfiguredError: If Gemini not configured
            GeminiRateLimitError: If rate limit would be exceeded
            GeminiAuthError: If authentication fails
            GeminiUnavailableError: For other API errors
        """
        logger.info("=" * 60)
        logger.info("MARKET SEARCH")
        logger.info("=" * 60)
        logger.info("Query: \"%s%s\"", query[:100], "..." if len(query) > 100 else "")

        # Validate Gemini is configured
        if not self.gemini_service:
            raise GeminiNotConfiguredError("Gemini service is required but not configured")

        # Store the highlighted text for use throughout the request
        highlighted_text = query

        # Step 1: Get all open markets
        all_markets = self.get_all_open_markets()

        if not all_markets:
            logger.info("No markets available")
            return []

        logger.info("Total available markets: %d", len(all_markets))

        # Step 2: Stage 1 (gemini-3-flash-preview) - Filter ALL markets to top 50
        logger.info("--- Stage 1: Relevance Filter (gemini-3-flash-preview) ---")
        top_50_tickers = self.gemini_service.filter_markets_by_title(
            highlighted_text=highlighted_text,
            markets=all_markets,
            top_k=50
        )

        if not top_50_tickers:
            logger.info("Gemini found no relevant markets in stage 1")
            return []

        logger.info("Stage 1 returned %d tickers", len(top_50_tickers))

        # Step 3: Build about strings for the top 50 markets
        ticker_to_market = {m.get('ticker'): m for m in all_markets}
        filtered_markets = []

        for ticker in top_50_tickers:
            if ticker in ticker_to_market:
                market = ticker_to_market[ticker].copy()
                market['about'] = self._build_market_about(market)
                filtered_markets.append(market)

        logger.info("Built about strings for %d markets", len(filtered_markets))

        # Step 4: Stage 2 (gemma-3-27b-it) - Analyze for causal relationships
        logger.info("--- Stage 2: Causal Analysis (gemma-3-27b-it) ---")
        gemini_results = self.gemini_service.analyze_top_markets(
            highlighted_text=highlighted_text,
            markets=filtered_markets,
            top_k=top_k
        )

        if not gemini_results:
            logger.info("Gemini found no causal relationships in stage 2")
            return []

        logger.info("Stage 2 returned %d results", len(gemini_results))

        # Step 5: Build full market response objects with event data
        results = []
        for gemini_result in gemini_results:
            ticker = gemini_result.get('ticker')

            if ticker in ticker_to_market:
                market = ticker_to_market[ticker].copy()

                # Add Gemini analysis (stored passively)
                market['hop'] = gemini_result.get('hop', 1)
                market['impact_score'] = gemini_result.get('impact_score', 50)
                market['direction'] = gemini_result.get('direction', 'up')
                market['explanation'] = gemini_result.get('explanation', '')

                # Add market URL
                market['market_url'] = self.get_market_url(market)

                # Enrich with event data for better display
                event_ticker = market.get('event_ticker')
                if event_ticker:
                    event = self.get_event(event_ticker)
                    if event:
                        market['event_title'] = event.get('title', '')
                        market['event_subtitle'] = event.get('sub_title', '')
                        market['mutually_exclusive'] = event.get('mutually_exclusive', False)

                # Use yes_sub_title for outcome display (recommended by Kalshi)
                market['outcome_title'] = market.get('yes_sub_title') or market.get('title', '')

                # Remove large fields from response
                market.pop('about', None)

                results.append(market)

        # Step 6: Update prices via WebSocket if enabled
        if self._ws_enabled and results:
            results = self._update_prices_via_websocket(results)

        # Step 7: Group markets by event for better display
        grouped_results = self._group_markets_by_event(results)

        logger.info("=" * 60)
        logger.info(
            "FINAL RESULTS: %d event groups, %d markets total",
            len(grouped_results), len(results)
        )
        for i, group in enumerate(grouped_results, 1):
            logger.info(
                "  [%d] %s | Outcomes: %d",
                i, group.get('event_title', 'Unknown')[:50],
                len(group.get('markets', []))
            )
        logger.info("=" * 60)

        return grouped_results

    def _group_markets_by_event(self, markets: List[Dict]) -> List[Dict]:
        """
        Group markets by their parent event for cleaner display.

        Markets from the same event (e.g., different team outcomes for "Super Bowl Winner")
        are grouped together with the event title as the header.

        Args:
            markets: List of market dictionaries with event data

        Returns:
            List of event groups, each containing:
            - event_ticker: Event identifier
            - event_title: Display title for the event
            - event_subtitle: Subtitle if available
            - mutually_exclusive: Whether only one outcome can win
            - explanation: Combined explanation from Gemini
            - markets: List of individual market outcomes
        """
        from collections import OrderedDict

        # Group markets by event_ticker, preserving order
        event_groups = OrderedDict()

        for market in markets:
            event_ticker = market.get('event_ticker') or market.get('ticker')

            if event_ticker not in event_groups:
                event_groups[event_ticker] = {
                    'event_ticker': event_ticker,
                    'event_title': market.get('event_title') or market.get('title', ''),
                    'event_subtitle': market.get('event_subtitle', ''),
                    'mutually_exclusive': market.get('mutually_exclusive', False),
                    'explanation': market.get('explanation', ''),
                    'markets': []
                }

            # Add market to group with outcome-specific data
            event_groups[event_ticker]['markets'].append({
                'ticker': market.get('ticker'),
                'outcome_title': market.get('outcome_title') or market.get('yes_sub_title') or market.get('title', ''),
                'yes_bid': market.get('yes_bid'),
                'yes_ask': market.get('yes_ask'),
                'no_bid': market.get('no_bid'),
                'no_ask': market.get('no_ask'),
                'last_price': market.get('last_price'),
                'market_url': market.get('market_url'),
                'hop': market.get('hop', 1),
                'impact_score': market.get('impact_score', 50),
                'direction': market.get('direction', 'up')
            })

            # Use the first market's explanation for the group if not set
            if not event_groups[event_ticker]['explanation'] and market.get('explanation'):
                event_groups[event_ticker]['explanation'] = market.get('explanation')

        return list(event_groups.values())

    def _update_prices_via_websocket(self, markets: List[Dict], timeout: float = 3.0) -> List[Dict]:
        """
        Update market prices via WebSocket for real-time data.

        Args:
            markets: List of market dicts to update
            timeout: How long to listen for updates

        Returns:
            Updated market list
        """
        try:
            from kalshi_ws import update_markets_with_realtime_prices

            logger.info("Fetching real-time prices via WebSocket...")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                updated_markets = loop.run_until_complete(
                    update_markets_with_realtime_prices(
                        markets,
                        self.api_key,
                        self.private_key,
                        timeout
                    )
                )
                logger.info("Real-time prices updated")
                return updated_markets
            finally:
                loop.close()

        except ImportError:
            logger.warning("WebSocket module not available, using REST prices")
            return markets
        except Exception as e:
            logger.error("WebSocket price update failed: %s", e)
            return markets

    def get_market_details(self, ticker: str) -> Optional[Dict]:
        """
        Get detailed information for a specific market.

        Args:
            ticker: Market ticker

        Returns:
            Market details or None
        """
        try:
            response = self._make_request(f'/markets/{ticker}')
            market = response.get('market')
            if market:
                market['market_url'] = self.get_market_url(market)
            return market
        except Exception as e:
            logger.error("Error fetching market details: %s", e)
            return None


def create_kalshi_service(
    api_key: Optional[str] = None,
    private_key: Optional[str] = None,
    gemini_service=None
) -> KalshiService:
    """
    Create a KalshiService instance.

    Args:
        api_key: Kalshi API key ID
        private_key: RSA private key PEM for WebSocket authentication
        gemini_service: GeminiService for causal market analysis (required)

    Returns:
        Configured KalshiService instance
    """
    return KalshiService(api_key, private_key, gemini_service)
