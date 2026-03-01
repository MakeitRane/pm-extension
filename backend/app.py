"""
Kalshi Markets Finder - Backend API
Flask server for market search using Gemini AI for causal analysis
"""

__version__ = '1.0.0'

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import os
import re
import json
import logging
import time
import traceback
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

# =============================================================================
# Structured JSON Logging
# =============================================================================

class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging in production."""

    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'message': record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
log_level = os.getenv('LOG_LEVEL', 'DEBUG' if debug_mode else 'INFO').upper()

# Configure logging
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, log_level, logging.INFO))
root_logger.handlers.clear()

handler = logging.StreamHandler()
if debug_mode:
    handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
else:
    handler.setFormatter(JSONFormatter())
root_logger.addHandler(handler)

logger = logging.getLogger(__name__)


# =============================================================================
# Flask App Setup
# =============================================================================

app = Flask(__name__)

# Max request body size: 16KB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024

# CORS configuration — environment-driven
cors_origins = ["chrome-extension://*"]
if debug_mode:
    cors_origins.append("http://localhost:*")
extra_origins = os.getenv('ALLOWED_ORIGINS', '')
if extra_origins:
    cors_origins.extend([o.strip() for o in extra_origins.split(',') if o.strip()])

CORS(app, resources={
    r"/api/*": {
        "origins": cors_origins,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Rate limiting (in-memory storage)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://",
)


# =============================================================================
# Request Timing Middleware
# =============================================================================

@app.before_request
def before_request():
    g.start_time = time.time()


@app.after_request
def after_request(response):
    duration_ms = (time.time() - g.start_time) * 1000
    logger.info(
        "%s %s %s %.0fms",
        request.method,
        request.path,
        response.status_code,
        duration_ms
    )
    return response


# =============================================================================
# Services
# =============================================================================

_services = {}


def get_services(api_key=None):
    """Get or initialize services."""
    global _services

    if 'gemini' not in _services:
        gemini_api_key_1 = os.getenv('GEMINI_API_KEY_1')
        gemini_api_key_2 = os.getenv('GEMINI_API_KEY_2')

        if gemini_api_key_1 and gemini_api_key_2:
            try:
                _services['gemini'] = create_gemini_service(gemini_api_key_1, gemini_api_key_2)
                logger.info("Gemini service ready (both stages configured)")
            except GeminiNotConfiguredError as e:
                logger.error("Gemini configuration error: %s", e)
                _services['gemini'] = None
        else:
            missing = []
            if not gemini_api_key_1:
                missing.append("GEMINI_API_KEY_1")
            if not gemini_api_key_2:
                missing.append("GEMINI_API_KEY_2")
            logger.warning("Missing Gemini API keys: %s", ', '.join(missing))
            _services['gemini'] = None

    key = api_key or os.getenv('KALSHI_API_KEY')
    private_key = os.getenv('RSA_KEY')

    _services['kalshi'] = create_kalshi_service(
        key,
        private_key,
        _services.get('gemini')
    )

    return _services


# =============================================================================
# Error Handling
# =============================================================================

def gemini_error_response(error: GeminiError):
    """Convert Gemini error to API response."""
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

    return {
        'success': False,
        'error': 'Gemini API is temporarily unavailable. Please try again later.',
        'error_type': 'GEMINI_UNAVAILABLE'
    }, 503


# Ticker validation: alphanumeric, hyphens, underscores
TICKER_RE = re.compile(r'^[A-Za-z0-9\-_]+$')

MAX_QUERY_LENGTH = 1000


# =============================================================================
# Endpoints
# =============================================================================

@app.route('/api/health', methods=['GET'])
@limiter.exempt
def health_check():
    """Enhanced health check with dependency status."""
    gemini_key_1_configured = bool(os.getenv('GEMINI_API_KEY_1'))
    gemini_key_2_configured = bool(os.getenv('GEMINI_API_KEY_2'))
    gemini_ok = gemini_key_1_configured and gemini_key_2_configured

    # Quick Kalshi API reachability check
    kalshi_reachable = False
    try:
        import requests as req_lib
        resp = req_lib.get(
            'https://api.elections.kalshi.com/trade-api/v2/exchange/status',
            timeout=5
        )
        kalshi_reachable = resp.status_code < 500
    except Exception:
        kalshi_reachable = False

    from gemini_service import get_rate_limiter
    stage1_rate_limiter = get_rate_limiter(stage=1)
    stage2_rate_limiter = get_rate_limiter(stage=2)

    overall_status = 'ok' if gemini_ok else 'degraded'
    status_code = 200 if gemini_ok else 503

    response = {
        'status': overall_status,
        'version': __version__,
        'message': 'Kalshi Markets Finder API is running',
        'dependencies': {
            'gemini': {
                'stage1_flash': gemini_key_1_configured,
                'stage2_gemma': gemini_key_2_configured,
            },
            'kalshi_api': kalshi_reachable,
        },
        'rate_limits': {
            'stage1': stage1_rate_limiter.get_current_usage(),
            'stage2': stage2_rate_limiter.get_current_usage()
        }
    }
    return jsonify(response), status_code


@app.route('/api/rate-limits', methods=['GET'])
def get_rate_limits():
    """Get current rate limit usage for both stages."""
    from gemini_service import get_rate_limiter
    stage1_usage = get_rate_limiter(stage=1).get_current_usage()
    stage2_usage = get_rate_limiter(stage=2).get_current_usage()

    return jsonify({
        'success': True,
        'data': {
            'stage1': stage1_usage,
            'stage2': stage2_usage
        }
    })


@app.route('/api/search', methods=['POST'])
@limiter.limit("10 per minute")
def search_markets():
    """Search for markets related to highlighted text."""
    try:
        data = request.get_json()

        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing "query" field in request body'
            }), 400

        query = data['query']
        limit = data.get('limit', 5)
        api_key = data.get('api_key')

        if not query or not query.strip():
            return jsonify({
                'success': False,
                'error': 'Query cannot be empty'
            }), 400

        if len(query) > MAX_QUERY_LENGTH:
            return jsonify({
                'success': False,
                'error': f'Query too long (max {MAX_QUERY_LENGTH} characters)'
            }), 400

        services = get_services(api_key)
        kalshi_service = services['kalshi']

        markets = kalshi_service.search_markets(query, top_k=limit)

        return jsonify({
            'success': True,
            'data': {
                'query': query,
                'markets': markets
            }
        })

    except GeminiError as e:
        response, status_code = gemini_error_response(e)
        return jsonify(response), status_code

    except Exception as e:
        logger.error("Error in /api/search: %s", e, exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An internal error occurred. Please try again.'
        }), 500


@app.route('/api/market/<ticker>', methods=['GET'])
def get_market_details(ticker):
    """Get detailed information for a specific market."""
    try:
        if not TICKER_RE.match(ticker):
            return jsonify({
                'success': False,
                'error': 'Invalid ticker format'
            }), 400

        api_key = request.headers.get('Authorization', '').replace('Bearer ', '')

        services = get_services(api_key if api_key else None)
        kalshi_service = services['kalshi']

        market = kalshi_service.get_market_details(ticker)

        if market is None:
            return jsonify({
                'success': False,
                'error': f'Market not found: {ticker}'
            }), 404

        return jsonify({'success': True, 'data': {'market': market}})

    except Exception as e:
        logger.error("Error in /api/market/%s: %s", ticker, e, exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An internal error occurred. Please try again.'
        }), 500


@app.route('/api/refresh', methods=['POST'])
def refresh_cache():
    """Force refresh of market cache."""
    try:
        api_key = request.get_json().get('api_key') if request.is_json else None

        services = get_services(api_key)
        kalshi_service = services['kalshi']

        markets = kalshi_service.get_all_open_markets(force_refresh=True)

        return jsonify({
            'success': True,
            'message': f'Cache refreshed with {len(markets)} markets'
        })

    except Exception as e:
        logger.error("Error in /api/refresh: %s", e, exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An internal error occurred. Please try again.'
        }), 500


# =============================================================================
# Dev Server Entry Point
# =============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))

    has_kalshi_key = bool(os.getenv('KALSHI_API_KEY'))
    has_rsa_key = bool(os.getenv('RSA_KEY'))
    has_gemini_key_1 = bool(os.getenv('GEMINI_API_KEY_1'))
    has_gemini_key_2 = bool(os.getenv('GEMINI_API_KEY_2'))
    has_both_gemini_keys = has_gemini_key_1 and has_gemini_key_2

    logger.info("")
    logger.info("=" * 60)
    logger.info("       KALSHI MARKETS FINDER - BACKEND API v%s", __version__)
    logger.info("=" * 60)
    logger.info("  Server: http://localhost:%d", port)
    logger.info("  Debug Mode: %s", debug_mode)
    logger.info("")
    logger.info("  Configuration:")
    logger.info("    GEMINI_API_KEY_1 (Stage 1 - Flash): %s", 'Configured' if has_gemini_key_1 else 'REQUIRED')
    logger.info("    GEMINI_API_KEY_2 (Stage 2 - Gemma): %s", 'Configured' if has_gemini_key_2 else 'REQUIRED')
    logger.info("    Kalshi API Key: %s", 'Configured' if has_kalshi_key else 'Not set (optional)')
    logger.info("    RSA Key (WebSocket): %s", 'Configured' if has_rsa_key else 'Not set (optional)')
    logger.info("")
    logger.info("  Endpoints:")
    logger.info("    GET  /api/health      - Health check with dependency status")
    logger.info("    GET  /api/rate-limits  - Current rate limit usage")
    logger.info("    POST /api/search       - Search markets (10 req/min)")
    logger.info("    GET  /api/market/:id   - Get market details")
    logger.info("    POST /api/refresh      - Refresh market cache")
    logger.info("=" * 60)
    logger.info("")

    if has_both_gemini_keys:
        logger.info("Initializing Gemini services...")
        get_services()
        logger.info("Server ready!")
    else:
        logger.warning("Gemini API keys not fully configured — search will not work")

    app.run(host='0.0.0.0', port=port, debug=debug_mode)
