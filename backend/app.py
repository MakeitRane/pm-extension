"""
Kalshi Markets Finder - Backend API
Flask server for market search using Gemini AI for causal analysis
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging
from datetime import datetime

from kalshi_service import create_kalshi_service
from gemini_service import (
    create_gemini_service,
    GeminiError,
    GeminiRateLimitError,
    GeminiAuthError,
    GeminiUnavailableError,
    GeminiNotConfiguredError
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class RequestResponseLogger:
    """Logger for tracking API requests and responses."""

    @staticmethod
    def log_request(endpoint: str, method: str, data: dict = None):
        """Log incoming request details."""
        logger.info("=" * 80)
        logger.info(f"REQUEST: {method} {endpoint}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        if data:
            logger.info(f"Request Body:")
            for key, value in data.items():
                if key == 'query':
                    logger.info(f"  Highlighted Text: \"{value}\"")
                elif key == 'text':
                    logger.info(f"  Text: \"{value}\"")
                else:
                    logger.info(f"  {key}: {value}")

    @staticmethod
    def log_response(endpoint: str, response: dict, status_code: int = 200):
        """Log outgoing response details."""
        logger.info("-" * 40)
        logger.info(f"RESPONSE: {endpoint} (Status: {status_code})")

        if response.get('success'):
            data = response.get('data', {})

            # Log markets if present
            if 'markets' in data:
                markets = data['markets']
                logger.info(f"Found {len(markets)} markets:")
                for i, market in enumerate(markets, 1):
                    logger.info(f"  [{i}] {market.get('title', 'Unknown')}")
                    if market.get('ticker'):
                        logger.info(f"      Ticker: {market['ticker']}")
                    if market.get('yes_bid') is not None:
                        logger.info(f"      Yes Price: {market.get('yes_bid')}¢")
                    if market.get('explanation'):
                        logger.info(f"      Explanation: {market['explanation'][:100]}...")
                    if market.get('market_url'):
                        logger.info(f"      URL: {market['market_url']}")

            # Log single market if present
            elif 'market' in data:
                market = data['market']
                logger.info(f"Market Details: {market.get('title', 'Unknown')}")
                logger.info(f"  Ticker: {market.get('ticker')}")
                logger.info(f"  Status: {market.get('status')}")
                if market.get('yes_bid') is not None:
                    logger.info(f"  Yes Price: {market.get('yes_bid')}¢")
        else:
            logger.error(f"Error: {response.get('error', 'Unknown error')}")
            if response.get('error_type'):
                logger.error(f"Error Type: {response.get('error_type')}")

        logger.info("=" * 80 + "\n")


req_logger = RequestResponseLogger()

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for Chrome extension
CORS(app, resources={
    r"/api/*": {
        "origins": ["chrome-extension://*", "http://localhost:*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Initialize services (lazy loading)
_services = {}


def get_services(api_key=None):
    """Get or initialize services."""
    global _services

    # Initialize Gemini service if not already done
    if 'gemini' not in _services:
        gemini_api_key_1 = os.getenv('GEMINI_API_KEY_1')
        gemini_api_key_2 = os.getenv('GEMINI_API_KEY_2')

        if gemini_api_key_1 and gemini_api_key_2:
            try:
                _services['gemini'] = create_gemini_service(gemini_api_key_1, gemini_api_key_2)
                print("Gemini service ready (both stages configured)!")
            except GeminiNotConfiguredError as e:
                print(f"Gemini configuration error: {e}")
                _services['gemini'] = None
        else:
            missing = []
            if not gemini_api_key_1:
                missing.append("GEMINI_API_KEY_1 (Stage 1: gemini-3-flash-preview)")
            if not gemini_api_key_2:
                missing.append("GEMINI_API_KEY_2 (Stage 2: gemma-3-27b-it)")
            print(f"WARNING: Missing Gemini API keys - search will not work!")
            print(f"  Missing: {', '.join(missing)}")
            _services['gemini'] = None

    # Create Kalshi service with provided API key or env var
    key = api_key or os.getenv('KALSHI_API_KEY')

    # Load RSA private key for WebSocket authentication
    private_key = os.getenv('RSA_KEY')
    if private_key:
        print("RSA key loaded for WebSocket authentication")
    else:
        print("No RSA key found - WebSocket features disabled")

    _services['kalshi'] = create_kalshi_service(
        key,
        private_key,
        _services['gemini']
    )

    return _services


def gemini_error_response(error: GeminiError):
    """
    Convert Gemini error to API response.

    Args:
        error: GeminiError exception

    Returns:
        Tuple of (response_dict, status_code)
    """
    if isinstance(error, GeminiRateLimitError):
        return {
            'success': False,
            'error': 'Gemini API rate limit exceeded. Please wait a moment and try again.',
            'error_type': 'GEMINI_RATE_LIMITED'
        }, 429

    if isinstance(error, GeminiAuthError):
        return {
            'success': False,
            'error': 'Gemini API authentication failed. Please check your API key.',
            'error_type': 'GEMINI_AUTH_ERROR'
        }, 401

    if isinstance(error, GeminiNotConfiguredError):
        return {
            'success': False,
            'error': 'Gemini API is not configured. Please set the GEMINI_API_KEY environment variable.',
            'error_type': 'GEMINI_NOT_CONFIGURED'
        }, 503

    # GeminiUnavailableError or other
    return {
        'success': False,
        'error': 'Gemini API is temporarily unavailable. Please try again later.',
        'error_type': 'GEMINI_UNAVAILABLE'
    }, 503


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    req_logger.log_request('/api/health', 'GET')

    gemini_key_1_configured = bool(os.getenv('GEMINI_API_KEY_1'))
    gemini_key_2_configured = bool(os.getenv('GEMINI_API_KEY_2'))

    # Get rate limit status for both stages
    from gemini_service import get_rate_limiter
    stage1_rate_limiter = get_rate_limiter(stage=1)
    stage2_rate_limiter = get_rate_limiter(stage=2)

    response = {
        'status': 'ok',
        'message': 'Kalshi Markets Finder API is running',
        'gemini_configured': {
            'stage1_flash': gemini_key_1_configured,
            'stage2_gemma': gemini_key_2_configured
        },
        'rate_limits': {
            'stage1': stage1_rate_limiter.get_current_usage(),
            'stage2': stage2_rate_limiter.get_current_usage()
        }
    }
    req_logger.log_response('/api/health', {'success': True, 'data': response})
    return jsonify(response)


@app.route('/api/rate-limits', methods=['GET'])
def get_rate_limits():
    """
    Get current rate limit usage for both stages.

    Response:
        {
            "success": true,
            "data": {
                "stage1": {
                    "name": "Stage1-Flash",
                    "requests_per_minute": 1,
                    "tokens_per_minute": 50000,
                    "requests_per_day": 5,
                    "limits": {"max_rpm": 4, "max_tpm": 250000, "max_rpd": 18}
                },
                "stage2": {
                    "name": "Stage2-Gemma",
                    "requests_per_minute": 3,
                    "tokens_per_minute": 5000,
                    "requests_per_day": 10,
                    "limits": {"max_rpm": 28, "max_tpm": 14000, "max_rpd": 14000}
                }
            }
        }
    """
    req_logger.log_request('/api/rate-limits', 'GET')

    from gemini_service import get_rate_limiter
    stage1_usage = get_rate_limiter(stage=1).get_current_usage()
    stage2_usage = get_rate_limiter(stage=2).get_current_usage()

    response = {
        'success': True,
        'data': {
            'stage1': stage1_usage,
            'stage2': stage2_usage
        }
    }
    req_logger.log_response('/api/rate-limits', response)
    return jsonify(response)


@app.route('/api/search', methods=['POST'])
def search_markets():
    """
    Search for markets related to highlighted text.

    Request body:
        {
            "query": "highlighted text",
            "limit": 5,  // optional, default 5
            "api_key": "..."  // optional Kalshi API key
        }

    Response:
        {
            "success": true,
            "data": {
                "query": "...",
                "markets": [
                    {
                        "ticker": "...",
                        "title": "...",
                        "explanation": "...",
                        "hop": 1,
                        "impact_score": 85,
                        "direction": "up",
                        ...
                    }
                ]
            }
        }

    Error Response:
        {
            "success": false,
            "error": "Error message",
            "error_type": "GEMINI_RATE_LIMITED" | "GEMINI_AUTH_ERROR" | "GEMINI_UNAVAILABLE" | "GEMINI_NOT_CONFIGURED"
        }
    """
    try:
        data = request.get_json()
        req_logger.log_request('/api/search', 'POST', {
            'query': data.get('query') if data else None,
            'limit': data.get('limit', 5) if data else 5
        })

        if not data or 'query' not in data:
            response = {'success': False, 'error': 'Missing "query" field in request body'}
            req_logger.log_response('/api/search', response, 400)
            return jsonify(response), 400

        query = data['query']
        limit = data.get('limit', 5)
        api_key = data.get('api_key')

        if not query or not query.strip():
            response = {'success': False, 'error': 'Query cannot be empty'}
            req_logger.log_response('/api/search', response, 400)
            return jsonify(response), 400

        services = get_services(api_key)
        kalshi_service = services['kalshi']

        # This will raise GeminiError subclasses if Gemini fails
        markets = kalshi_service.search_markets(query, top_k=limit)

        response = {
            'success': True,
            'data': {
                'query': query,
                'markets': markets
            }
        }
        req_logger.log_response('/api/search', response)
        return jsonify(response)

    except GeminiError as e:
        response, status_code = gemini_error_response(e)
        req_logger.log_response('/api/search', response, status_code)
        return jsonify(response), status_code

    except Exception as e:
        logger.error(f"Error in /api/search: {e}")
        import traceback
        traceback.print_exc()
        response = {'success': False, 'error': str(e)}
        req_logger.log_response('/api/search', response, 500)
        return jsonify(response), 500


@app.route('/api/market/<ticker>', methods=['GET'])
def get_market_details(ticker):
    """
    Get detailed information for a specific market.

    Response:
        {
            "success": true,
            "data": {
                "market": { ... }
            }
        }
    """
    try:
        req_logger.log_request(f'/api/market/{ticker}', 'GET', {'ticker': ticker})

        api_key = request.headers.get('Authorization', '').replace('Bearer ', '')

        services = get_services(api_key if api_key else None)
        kalshi_service = services['kalshi']

        market = kalshi_service.get_market_details(ticker)

        if market is None:
            response = {'success': False, 'error': f'Market not found: {ticker}'}
            req_logger.log_response(f'/api/market/{ticker}', response, 404)
            return jsonify(response), 404

        response = {'success': True, 'data': {'market': market}}
        req_logger.log_response(f'/api/market/{ticker}', response)
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in /api/market: {e}")
        response = {'success': False, 'error': str(e)}
        req_logger.log_response(f'/api/market/{ticker}', response, 500)
        return jsonify(response), 500


@app.route('/api/refresh', methods=['POST'])
def refresh_cache():
    """
    Force refresh of market cache.

    Response:
        {
            "success": true,
            "message": "Cache refreshed with X markets"
        }
    """
    try:
        req_logger.log_request('/api/refresh', 'POST')

        api_key = request.get_json().get('api_key') if request.is_json else None

        services = get_services(api_key)
        kalshi_service = services['kalshi']

        markets = kalshi_service.get_all_open_markets(force_refresh=True)

        response = {'success': True, 'message': f'Cache refreshed with {len(markets)} markets'}
        req_logger.log_response('/api/refresh', response)
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in /api/refresh: {e}")
        response = {'success': False, 'error': str(e)}
        req_logger.log_response('/api/refresh', response, 500)
        return jsonify(response), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('DEBUG', 'True').lower() == 'true'

    # Check configuration
    has_kalshi_key = bool(os.getenv('KALSHI_API_KEY'))
    has_rsa_key = bool(os.getenv('RSA_KEY'))
    has_gemini_key_1 = bool(os.getenv('GEMINI_API_KEY_1'))
    has_gemini_key_2 = bool(os.getenv('GEMINI_API_KEY_2'))
    has_both_gemini_keys = has_gemini_key_1 and has_gemini_key_2

    logger.info("")
    logger.info("=" * 60)
    logger.info("       KALSHI MARKETS FINDER - BACKEND API")
    logger.info("=" * 60)
    logger.info(f"  Server: http://localhost:{port}")
    logger.info(f"  Debug Mode: {debug}")
    logger.info("")
    logger.info("  Configuration:")
    logger.info(f"    GEMINI_API_KEY_1 (Stage 1 - Flash): {'✓ Configured' if has_gemini_key_1 else '✗ REQUIRED'}")
    logger.info(f"    GEMINI_API_KEY_2 (Stage 2 - Gemma): {'✓ Configured' if has_gemini_key_2 else '✗ REQUIRED'}")
    logger.info(f"    Kalshi API Key: {'✓ Configured' if has_kalshi_key else '✗ Not set (optional)'}")
    logger.info(f"    RSA Key (WebSocket): {'✓ Configured' if has_rsa_key else '✗ Not set (optional)'}")
    logger.info("")
    logger.info("  Rate Limits:")
    logger.info("    Stage 1 (gemini-3-flash-preview): 4 RPM, 250k TPM, 18 RPD")
    logger.info("    Stage 2 (gemma-3-27b-it):  28 RPM, 14k TPM, 14k RPD")
    logger.info("")
    logger.info("  Endpoints:")
    logger.info("    GET  /api/health      - Health check with rate limit status")
    logger.info("    GET  /api/rate-limits - Current rate limit usage")
    logger.info("    POST /api/search      - Search markets (requires both Gemini keys)")
    logger.info("    GET  /api/market/:id  - Get market details")
    logger.info("    POST /api/refresh     - Refresh market cache")
    logger.info("")
    logger.info("  Logging: All requests and responses will be logged")
    logger.info("=" * 60)
    logger.info("")

    # Pre-initialize services on startup
    if has_both_gemini_keys:
        logger.info("Initializing Gemini services (Stage 1 + Stage 2)...")
        get_services()
        logger.info("Server ready! Waiting for requests...")
    else:
        logger.warning("WARNING: Gemini API keys not fully configured!")
        if not has_gemini_key_1:
            logger.warning("  Missing: GEMINI_API_KEY_1 (for gemini-3-flash-preview)")
        if not has_gemini_key_2:
            logger.warning("  Missing: GEMINI_API_KEY_2 (for gemma-3-27b-it)")
        logger.warning("Set both keys in .env file for search to work.")

    logger.info("")

    app.run(host='0.0.0.0', port=port, debug=debug)
