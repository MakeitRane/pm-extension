"""
Gemini Service
Two-stage market filtering using different Gemini models:

Stage 1 (Relevance Filter): gemini-3-flash-preview with GEMINI_API_KEY_1
  - High context window for processing all markets
  - Rate limits: 4 RPM, 250k TPM, 18 RPD

Stage 2 (Causal Analysis): gemma-3-27b-it with GEMINI_API_KEY_2
  - Detailed causal reasoning on top 50 candidates
  - Rate limits: 28 RPM, 14k TPM, 14k RPD
"""

import json
import logging
import re
import time
import threading
from typing import List, Dict, Optional
from collections import deque
from google import genai
from google.genai import errors as genai_errors

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================

class GeminiError(Exception):
    """Base exception for Gemini-related errors."""
    pass


class GeminiRateLimitError(GeminiError):
    """Raised when Gemini API rate limit is hit or would be exceeded."""
    pass


class GeminiAuthError(GeminiError):
    """Raised when Gemini API authentication fails."""
    pass


class GeminiUnavailableError(GeminiError):
    """Raised when Gemini API is unavailable."""
    pass


class GeminiNotConfiguredError(GeminiError):
    """Raised when Gemini API key is not configured."""
    pass


# =============================================================================
# Rate Limiter (Configurable per Model)
# =============================================================================

class RateLimiter:
    """
    Thread-safe rate limiter for Gemini API.
    Configurable limits per model/stage.
    Throws errors immediately when limits would be exceeded.
    """

    # Token estimation: ~4 characters per token (conservative estimate)
    CHARS_PER_TOKEN = 4

    def __init__(
        self,
        name: str,
        max_rpm: int,
        max_tpm: int,
        max_rpd: int
    ):
        """
        Initialize rate limiter with specific limits.

        Args:
            name: Identifier for logging (e.g., "Stage1", "Stage2")
            max_rpm: Maximum requests per minute
            max_tpm: Maximum tokens per minute
            max_rpd: Maximum requests per day
        """
        self.name = name
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.max_rpd = max_rpd

        self._lock = threading.Lock()

        # Sliding window for requests per minute (timestamp)
        self._minute_requests: deque = deque()

        # Sliding window for requests per day (timestamp)
        self._day_requests: deque = deque()

        # Track tokens in current minute (timestamp, token_count)
        self._minute_tokens: deque = deque()

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a piece of text.
        Uses conservative estimate of ~4 characters per token.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        return max(1, len(text) // self.CHARS_PER_TOKEN)

    def _cleanup_old_entries(self, now: float):
        """Remove entries older than their respective windows."""
        minute_ago = now - 60
        day_ago = now - 86400

        # Clean minute window
        while self._minute_requests and self._minute_requests[0] < minute_ago:
            self._minute_requests.popleft()

        while self._minute_tokens and self._minute_tokens[0][0] < minute_ago:
            self._minute_tokens.popleft()

        # Clean day window
        while self._day_requests and self._day_requests[0] < day_ago:
            self._day_requests.popleft()

    def get_current_usage(self) -> Dict:
        """
        Get current rate limit usage.

        Returns:
            Dict with current usage stats
        """
        with self._lock:
            now = time.time()
            self._cleanup_old_entries(now)

            current_tokens = sum(tokens for _, tokens in self._minute_tokens)

            return {
                'name': self.name,
                'requests_per_minute': len(self._minute_requests),
                'tokens_per_minute': current_tokens,
                'requests_per_day': len(self._day_requests),
                'limits': {
                    'max_rpm': self.max_rpm,
                    'max_tpm': self.max_tpm,
                    'max_rpd': self.max_rpd
                }
            }

    def check_limits(self, estimated_tokens: int) -> None:
        """
        Check if request can proceed. Throws error immediately if limits exceeded.

        Args:
            estimated_tokens: Estimated tokens for the request

        Raises:
            GeminiRateLimitError: If any rate limit would be exceeded
        """
        with self._lock:
            now = time.time()
            self._cleanup_old_entries(now)

            # Check daily limit
            if len(self._day_requests) >= self.max_rpd:
                raise GeminiRateLimitError(
                    f"[{self.name}] Daily request limit exceeded "
                    f"({len(self._day_requests)}/{self.max_rpd} requests/day). "
                    "Please try again tomorrow."
                )

            # Check requests per minute
            if len(self._minute_requests) >= self.max_rpm:
                wait_time = 60 - (now - self._minute_requests[0])
                raise GeminiRateLimitError(
                    f"[{self.name}] Request rate limit exceeded "
                    f"({len(self._minute_requests)}/{self.max_rpm} requests/min). "
                    f"Try again in {wait_time:.0f}s."
                )

            # Check tokens per minute
            current_tokens = sum(tokens for _, tokens in self._minute_tokens)
            if current_tokens + estimated_tokens > self.max_tpm:
                wait_time = 60 - (now - self._minute_tokens[0][0]) if self._minute_tokens else 60
                raise GeminiRateLimitError(
                    f"[{self.name}] Token rate limit would be exceeded "
                    f"({current_tokens}+{estimated_tokens}={current_tokens + estimated_tokens} > {self.max_tpm} tokens/min). "
                    f"Try again in {wait_time:.0f}s."
                )

            # Log successful check
            logger.info(
                "[%s] Rate check passed: RPM=%d/%d, TPM=%d/%d, RPD=%d/%d",
                self.name,
                len(self._minute_requests) + 1, self.max_rpm,
                current_tokens + estimated_tokens, self.max_tpm,
                len(self._day_requests) + 1, self.max_rpd
            )

    def record_request(self, actual_tokens: int) -> None:
        """
        Record a completed request.

        Args:
            actual_tokens: Actual tokens used (estimated if not known)
        """
        with self._lock:
            now = time.time()
            self._minute_requests.append(now)
            self._minute_tokens.append((now, actual_tokens))
            self._day_requests.append(now)


# =============================================================================
# Global Rate Limiters (one per stage)
# =============================================================================

# Stage 1: gemini-3-flash-preview (high context, low RPM)
_stage1_rate_limiter = RateLimiter(
    name="Stage1-Flash",
    max_rpm=4,
    max_tpm=250000,
    max_rpd=18
)

# Stage 2: gemma-3-27b-it (lower context, higher RPM)
_stage2_rate_limiter = RateLimiter(
    name="Stage2-Gemma",
    max_rpm=28,
    max_tpm=14000,
    max_rpd=14000
)


def get_rate_limiter(stage: int = 2) -> RateLimiter:
    """
    Get the rate limiter for a specific stage.

    Args:
        stage: 1 for Stage 1 (Flash), 2 for Stage 2 (Gemma)

    Returns:
        Appropriate RateLimiter instance
    """
    return _stage1_rate_limiter if stage == 1 else _stage2_rate_limiter


# =============================================================================
# Stage 1 Service: Relevance Filter (gemini-3-flash-preview)
# =============================================================================

class Stage1Service:
    """
    Stage 1: Filter all markets to top 50 by relevance.
    Uses gemini-3-flash-preview with high context window.
    """

    MODEL_NAME = "gemini-3-flash-preview"

    def __init__(self, api_key: str):
        """
        Initialize Stage 1 service.

        Args:
            api_key: GEMINI_API_KEY_1 for gemini-3-flash-preview
        """
        self.client = genai.Client(api_key=api_key)
        self.rate_limiter = _stage1_rate_limiter
        logger.info("Stage1Service initialized with model: %s", self.MODEL_NAME)

    def _handle_api_error(self, error: Exception) -> None:
        """Convert API errors to specific exception types."""
        error_str = str(error).lower()

        if '429' in str(error) or 'rate limit' in error_str or 'quota' in error_str:
            raise GeminiRateLimitError(f"[Stage1] Rate limit exceeded: {error}")

        if '401' in str(error) or '403' in str(error) or 'api key' in error_str:
            raise GeminiAuthError(f"[Stage1] Authentication failed: {error}")

        raise GeminiUnavailableError(f"[Stage1] API error: {error}")

    def filter_markets_by_title(
        self,
        highlighted_text: str,
        markets: List[Dict],
        top_k: int = 50
    ) -> List[str]:
        """
        Filter markets to top K based on title relevance.

        Args:
            highlighted_text: Text highlighted by user
            markets: List of ALL market dictionaries
            top_k: Number of markets to return (default 50)

        Returns:
            List of ticker strings for the top K most relevant markets

        Raises:
            GeminiRateLimitError: If rate limit would be exceeded
            GeminiAuthError: If authentication fails
            GeminiUnavailableError: For other API errors
        """
        if not markets:
            return []

        # Format markets as "[TICKER] Title" pairs
        market_lines = []
        for market in markets:
            ticker = market.get('ticker', '')
            title = market.get('title', '')
            if ticker and title:
                market_lines.append(f"[{ticker}] {title}")

        markets_text = '\n'.join(market_lines)

        prompt = f"""You are a relevance filter for prediction markets. Your job is to identify markets that could be related to the highlighted text.

HIGHLIGHTED TEXT:
\"\"\"{highlighted_text}\"\"\"

AVAILABLE MARKETS:
{markets_text}

TASK:
Select the top {top_k} markets whose outcomes could potentially be related to or influenced by the highlighted text. Consider:
- Direct relationships (the text directly affects the market outcome)
- Indirect relationships (the text affects something that affects the market)
- Topical relationships (same domain/subject matter)

Return ONLY a JSON array of ticker strings, nothing else. Example:
["TICKER1", "TICKER2", "TICKER3"]

Return exactly {top_k} tickers (or fewer if not enough relevant markets exist).
If no markets are relevant, return: []"""

        # Estimate tokens for rate limiting
        estimated_tokens = self.rate_limiter.estimate_tokens(prompt)

        try:
            logger.info("=" * 60)
            logger.info("STAGE 1: RELEVANCE FILTER (gemini-3-flash-preview)")
            logger.info("=" * 60)
            logger.info(
                "Highlighted text: \"%s%s\"",
                highlighted_text[:100],
                "..." if len(highlighted_text) > 100 else ""
            )
            logger.info("Total markets: %d", len(markets))
            logger.info("Estimated tokens: %d", estimated_tokens)

            # Check rate limits BEFORE making request
            self.rate_limiter.check_limits(estimated_tokens)

            # Make the API call
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=prompt
            )

            # Estimate response tokens and record request
            response_tokens = self.rate_limiter.estimate_tokens(response.text) if response.text else 0
            total_tokens = estimated_tokens + response_tokens
            self.rate_limiter.record_request(total_tokens)

            logger.info("─" * 40)
            logger.info("RESPONSE (Stage 1):")
            logger.info("─" * 40)
            logger.info(
                "%s%s",
                response.text[:500],
                "..." if len(response.text) > 500 else ""
            )

            # Parse the response
            tickers = self._parse_ticker_list(response.text, markets)

            logger.info("Extracted %d tickers", len(tickers))
            logger.info("=" * 60)

            return tickers

        except (GeminiRateLimitError, GeminiAuthError, GeminiUnavailableError):
            raise
        except Exception as e:
            logger.error("[Stage1] API error: %s", e)
            self._handle_api_error(e)

    def _parse_ticker_list(self, response_text: str, markets: List[Dict]) -> List[str]:
        """Parse Gemini's response to extract ticker list."""
        json_match = re.search(r'\[[\s\S]*?\]', response_text)
        if not json_match:
            logger.warning("Could not find JSON array in response")
            return []

        try:
            tickers = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s", e)
            return []

        # Validate tickers exist in our markets
        valid_tickers = {m.get('ticker') for m in markets}
        validated_tickers = [t for t in tickers if t in valid_tickers]

        return validated_tickers


# =============================================================================
# Stage 2 Service: Causal Analysis (gemma-3-27b-it)
# =============================================================================

class Stage2Service:
    """
    Stage 2: Analyze top 50 markets for causal relationships.
    Uses gemma-3-27b-it with strict token limits.
    """

    MODEL_NAME = "gemma-3-27b-it"

    def __init__(self, api_key: str):
        """
        Initialize Stage 2 service.

        Args:
            api_key: GEMINI_API_KEY_2 for gemma-3-27b-it
        """
        self.client = genai.Client(api_key=api_key)
        self.rate_limiter = _stage2_rate_limiter
        logger.info("Stage2Service initialized with model: %s", self.MODEL_NAME)

    def _handle_api_error(self, error: Exception) -> None:
        """Convert API errors to specific exception types."""
        error_str = str(error).lower()

        if '429' in str(error) or 'rate limit' in error_str or 'quota' in error_str:
            raise GeminiRateLimitError(f"[Stage2] Rate limit exceeded: {error}")

        if '401' in str(error) or '403' in str(error) or 'api key' in error_str:
            raise GeminiAuthError(f"[Stage2] Authentication failed: {error}")

        raise GeminiUnavailableError(f"[Stage2] API error: {error}")

    def _format_markets_for_prompt(self, markets: List[Dict]) -> str:
        """
        Format markets with about strings for the prompt.
        Truncates to stay within token budget.

        Args:
            markets: List of market dictionaries with 'about' field

        Returns:
            Formatted string with market info
        """
        lines = []
        for market in markets:
            ticker = market.get('ticker', '')
            about = market.get('about', market.get('title', ''))

            # Truncate to 250 chars max per market
            if len(about) > 250:
                about = about[:247] + '...'

            lines.append(f"[{ticker}] {about}")

        return '\n'.join(lines)

    def analyze_top_markets(
        self,
        highlighted_text: str,
        markets: List[Dict],
        top_k: int = 5
    ) -> List[Dict]:
        """
        Analyze pre-filtered markets for causal relevance.

        Args:
            highlighted_text: Text highlighted by user
            markets: List of pre-filtered candidate markets (typically 50)
            top_k: Number of top results to return

        Returns:
            List of dicts with ticker, hop, impact_score, direction, explanation

        Raises:
            GeminiRateLimitError: If rate limit would be exceeded
            GeminiAuthError: If authentication fails
            GeminiUnavailableError: For other API errors
        """
        if not markets:
            return []

        markets_text = self._format_markets_for_prompt(markets)

        prompt = f"""You are a causal analysis expert for prediction markets. Your job is to identify markets whose probability would CHANGE if a rational trader learned the highlighted information.

HIGHLIGHTED TEXT:
\"\"\"{highlighted_text}\"\"\"

CANDIDATE MARKETS:
{markets_text}

TASK:
Identify the top {top_k} markets with the STRONGEST causal relationship to the highlighted text. For each market, determine:

1. **hop**: Causal distance
   - 1 = Direct (text directly affects outcome)
   - 2 = Indirect (text affects X, which affects outcome)

2. **impact_score**: How much would probability change? (0-100)
   - 80-100 = Major shift
   - 50-79 = Moderate shift
   - 30-49 = Small shift
   - Below 30 = Not significant enough

3. **direction**: Would the market become more likely YES or NO?
   - "up" = More likely YES
   - "down" = More likely NO

4. **explanation**: ONE sentence explaining the causal relationship

Return ONLY valid JSON (no markdown, no extra text):
[
  {{"ticker": "EXACT_TICKER", "hop": 1, "impact_score": 85, "direction": "up", "explanation": "One sentence explaining why this text affects this market."}},
  {{"ticker": "EXACT_TICKER", "hop": 2, "impact_score": 65, "direction": "down", "explanation": "One sentence explaining the causal chain."}}
]

Return the top {top_k} markets sorted by causal strength (strongest first).
If no markets have a meaningful causal relationship, return: []"""

        # Estimate tokens for rate limiting
        estimated_tokens = self.rate_limiter.estimate_tokens(prompt)

        try:
            logger.info("=" * 60)
            logger.info("STAGE 2: CAUSAL ANALYSIS (gemma-3-27b-it)")
            logger.info("=" * 60)
            logger.info(
                "Highlighted text: \"%s%s\"",
                highlighted_text[:100],
                "..." if len(highlighted_text) > 100 else ""
            )
            logger.info("Candidate markets: %d", len(markets))
            logger.info("Estimated tokens: %d", estimated_tokens)

            # CRITICAL: Check rate limits BEFORE making request
            # Especially important for the 14k TPM limit
            self.rate_limiter.check_limits(estimated_tokens)

            # Make the API call
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=prompt
            )

            # Estimate response tokens and record request
            response_tokens = self.rate_limiter.estimate_tokens(response.text) if response.text else 0
            total_tokens = estimated_tokens + response_tokens
            self.rate_limiter.record_request(total_tokens)

            logger.info("─" * 40)
            logger.info("RESPONSE (Stage 2):")
            logger.info("─" * 40)
            logger.info(
                "%s%s",
                response.text[:1000],
                "..." if len(response.text) > 1000 else ""
            )

            # Parse the response
            results = self._parse_analysis_response(response.text, markets)

            logger.info("Parsed %d results:", len(results))
            for i, r in enumerate(results, 1):
                logger.info(
                    "  [%d] %s | Hop: %s | Impact: %s | Dir: %s",
                    i, r.get('ticker'), r.get('hop'),
                    r.get('impact_score'), r.get('direction')
                )
            logger.info("=" * 60)

            return results

        except (GeminiRateLimitError, GeminiAuthError, GeminiUnavailableError):
            raise
        except Exception as e:
            logger.error("[Stage2] API error: %s", e)
            self._handle_api_error(e)

    def _parse_analysis_response(self, response_text: str, markets: List[Dict]) -> List[Dict]:
        """Parse Gemini's causal analysis response."""
        json_match = re.search(r'\[[\s\S]*?\]', response_text)
        if not json_match:
            logger.warning("Could not find JSON array in response")
            return []

        try:
            results = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s", e)
            return []

        # Validate tickers exist in our markets
        valid_tickers = {m.get('ticker') for m in markets}
        validated_results = []

        for result in results:
            ticker = result.get('ticker', '')

            if ticker not in valid_tickers:
                continue

            hop = result.get('hop', 1)
            impact_score = result.get('impact_score', 50)
            direction = result.get('direction', 'up')
            explanation = result.get('explanation', '')

            validated_results.append({
                'ticker': ticker,
                'hop': int(hop) if hop in [1, 2, '1', '2'] else 1,
                'impact_score': int(impact_score) if isinstance(impact_score, (int, float)) else 50,
                'direction': direction if direction in ['up', 'down'] else 'up',
                'explanation': str(explanation) if explanation else 'Causally related market'
            })

        return validated_results


# =============================================================================
# Combined Gemini Service (wraps both stages)
# =============================================================================

class GeminiService:
    """
    Combined service that wraps both Stage 1 and Stage 2.
    Provides the same interface as before for backward compatibility.
    """

    def __init__(self, stage1_service: Stage1Service, stage2_service: Stage2Service):
        """
        Initialize combined service.

        Args:
            stage1_service: Stage1Service instance (gemini-3-flash-preview)
            stage2_service: Stage2Service instance (gemma-3-27b-it)
        """
        self.stage1 = stage1_service
        self.stage2 = stage2_service

    def filter_markets_by_title(
        self,
        highlighted_text: str,
        markets: List[Dict],
        top_k: int = 50
    ) -> List[str]:
        """Delegate to Stage 1."""
        return self.stage1.filter_markets_by_title(highlighted_text, markets, top_k)

    def analyze_top_markets(
        self,
        highlighted_text: str,
        markets: List[Dict],
        top_k: int = 5
    ) -> List[Dict]:
        """Delegate to Stage 2."""
        return self.stage2.analyze_top_markets(highlighted_text, markets, top_k)


# =============================================================================
# Factory Functions
# =============================================================================

def create_gemini_service(
    api_key_1: Optional[str] = None,
    api_key_2: Optional[str] = None
) -> Optional[GeminiService]:
    """
    Create a GeminiService instance with both stages.

    Args:
        api_key_1: GEMINI_API_KEY_1 for Stage 1 (gemini-3-flash-preview)
        api_key_2: GEMINI_API_KEY_2 for Stage 2 (gemma-3-27b-it)

    Returns:
        GeminiService instance

    Raises:
        GeminiNotConfiguredError: If either API key is missing
    """
    if not api_key_1:
        raise GeminiNotConfiguredError(
            "GEMINI_API_KEY_1 is required for Stage 1 (gemini-3-flash-preview)"
        )

    if not api_key_2:
        raise GeminiNotConfiguredError(
            "GEMINI_API_KEY_2 is required for Stage 2 (gemma-3-27b-it)"
        )

    stage1 = Stage1Service(api_key_1)
    stage2 = Stage2Service(api_key_2)

    return GeminiService(stage1, stage2)
