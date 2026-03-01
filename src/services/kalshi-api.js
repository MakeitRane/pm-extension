/**
 * Kalshi API Service
 * Handles communication with the Python backend for semantic search
 * and direct Kalshi API calls for market details
 */

// Default backend URL — will be replaced with Railway production URL after first deploy
const DEFAULT_BACKEND_URL = 'http://localhost:5001';
const KALSHI_API_URL = 'https://api.elections.kalshi.com/trade-api/v2';

// Cached backend URL (loaded from storage on first use)
let _cachedBackendUrl = null;

/**
 * Get the backend URL from storage, falling back to the default.
 * Caches the value after first read.
 * @returns {Promise<string>}
 */
async function getBackendUrl() {
  if (_cachedBackendUrl !== null) {
    return _cachedBackendUrl;
  }
  try {
    const result = await chrome.storage.sync.get('backend_url');
    _cachedBackendUrl = result.backend_url || DEFAULT_BACKEND_URL;
  } catch {
    _cachedBackendUrl = DEFAULT_BACKEND_URL;
  }
  return _cachedBackendUrl;
}

// Invalidate cache when storage changes
try {
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.backend_url) {
      _cachedBackendUrl = null;
    }
  });
} catch {
  // Not in extension context (e.g. tests)
}

/**
 * Error types for categorized error handling
 */
export const ErrorTypes = {
  INVALID_API_KEY: 'INVALID_API_KEY',
  NETWORK_ERROR: 'NETWORK_ERROR',
  RATE_LIMITED: 'RATE_LIMITED',
  SERVER_ERROR: 'SERVER_ERROR',
  BACKEND_UNAVAILABLE: 'BACKEND_UNAVAILABLE',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
  // Gemini-specific errors
  GEMINI_RATE_LIMITED: 'GEMINI_RATE_LIMITED',
  GEMINI_AUTH_ERROR: 'GEMINI_AUTH_ERROR',
  GEMINI_UNAVAILABLE: 'GEMINI_UNAVAILABLE',
  GEMINI_NOT_CONFIGURED: 'GEMINI_NOT_CONFIGURED'
};

/**
 * Get error message for display
 * @param {string} errorType
 * @returns {string}
 */
export function getErrorMessage(errorType) {
  const messages = {
    [ErrorTypes.INVALID_API_KEY]: 'Invalid API key. Please check your key in settings.',
    [ErrorTypes.NETWORK_ERROR]: 'Unable to connect. Please check your internet connection.',
    [ErrorTypes.RATE_LIMITED]: 'Too many requests. Please wait a moment and try again.',
    [ErrorTypes.SERVER_ERROR]: 'Kalshi servers are experiencing issues. Please try again later.',
    [ErrorTypes.BACKEND_UNAVAILABLE]: 'Search backend is not running. Please start the Python server.',
    [ErrorTypes.UNKNOWN_ERROR]: 'Something went wrong. Please try again.',
    // Gemini-specific error messages
    [ErrorTypes.GEMINI_RATE_LIMITED]: 'AI rate limit reached. Please wait a moment and try again.',
    [ErrorTypes.GEMINI_AUTH_ERROR]: 'AI service authentication failed. Please check the API key configuration.',
    [ErrorTypes.GEMINI_UNAVAILABLE]: 'AI service is temporarily unavailable. Please try again later.',
    [ErrorTypes.GEMINI_NOT_CONFIGURED]: 'AI service is not configured. Please set up the Gemini API key.'
  };
  return messages[errorType] || messages[ErrorTypes.UNKNOWN_ERROR];
}

/**
 * Make a request to the Python backend
 * @param {string} endpoint
 * @param {object} options
 * @returns {Promise<object>}
 */
async function backendRequest(endpoint, options = {}) {
  const backendUrl = await getBackendUrl();
  const url = `${backendUrl}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));

      // Check for Gemini-specific error types from backend
      if (errorData.error_type) {
        throw { type: errorData.error_type, message: errorData.error };
      }

      if (response.status >= 500) {
        throw { type: ErrorTypes.SERVER_ERROR, status: response.status };
      }

      throw { type: ErrorTypes.UNKNOWN_ERROR, message: errorData.error };
    }

    return await response.json();
  } catch (error) {
    if (error.type) {
      throw error;
    }
    // Network error - backend not running
    console.error('Backend request failed:', error);
    throw { type: ErrorTypes.BACKEND_UNAVAILABLE, originalError: error };
  }
}

/**
 * Make a direct request to Kalshi API
 * @param {string} endpoint
 * @param {string|null} apiKey
 * @returns {Promise<object>}
 */
async function kalshiRequest(endpoint, apiKey = null) {
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  };

  if (apiKey) {
    headers['Authorization'] = `Bearer ${apiKey}`;
  }

  try {
    const response = await fetch(`${KALSHI_API_URL}${endpoint}`, { headers });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        throw { type: ErrorTypes.INVALID_API_KEY };
      }
      if (response.status === 429) {
        throw { type: ErrorTypes.RATE_LIMITED };
      }
      if (response.status >= 500) {
        throw { type: ErrorTypes.SERVER_ERROR };
      }
      throw { type: ErrorTypes.UNKNOWN_ERROR };
    }

    return await response.json();
  } catch (error) {
    if (error.type) {
      throw error;
    }
    throw { type: ErrorTypes.NETWORK_ERROR, originalError: error };
  }
}

/**
 * Search markets using Gemini AI (via Python backend)
 * Returns event groups with multiple market outcomes
 *
 * @param {string} query - Search query (highlighted text)
 * @param {string|null} apiKey - Optional API key
 * @param {number} limit - Max results to return (default 5)
 * @returns {Promise<{markets: object[], error: string|null}>}
 *
 * Response format (markets is an array of event groups):
 * {
 *   markets: [
 *     {
 *       event_ticker: "KXSB-27",
 *       event_title: "Super Bowl 2027 Winner",
 *       explanation: "Causal explanation...",
 *       markets: [
 *         { ticker: "KXSB-27-KC", outcome_title: "Chiefs", yes_bid: 28, ... },
 *         { ticker: "KXSB-27-PHI", outcome_title: "Eagles", yes_bid: 18, ... }
 *       ]
 *     }
 *   ]
 * }
 */
export async function searchMarkets(query, apiKey = null, limit = 5) {
  try {
    if (!query || query.trim().length === 0) {
      return { markets: [], error: null };
    }

    const response = await backendRequest('/api/search', {
      method: 'POST',
      body: JSON.stringify({
        query: query.trim(),
        limit,
        api_key: apiKey
      })
    });

    if (!response.success) {
      throw { type: ErrorTypes.UNKNOWN_ERROR, message: response.error };
    }

    // Response is now an array of event groups
    // Each group contains event_title, explanation, and markets array
    const eventGroups = response.data.markets || [];

    return { markets: eventGroups, error: null };
  } catch (error) {
    console.error('Error searching markets:', error);
    return {
      markets: [],
      error: error.type || ErrorTypes.UNKNOWN_ERROR
    };
  }
}

/**
 * Get embedding for text (for debugging/display)
 * @param {string} text
 * @returns {Promise<object>}
 */
export async function getEmbedding(text) {
  try {
    const response = await backendRequest('/api/embed', {
      method: 'POST',
      body: JSON.stringify({ text })
    });

    return response.data;
  } catch (error) {
    console.error('Error getting embedding:', error);
    return null;
  }
}

/**
 * Get detailed information for a specific market
 * @param {string} ticker - Market ticker
 * @param {string|null} apiKey
 * @returns {Promise<{market: object|null, error: string|null}>}
 */
export async function getMarketDetails(ticker, apiKey = null) {
  try {
    // Try backend first
    try {
      const response = await backendRequest(`/api/market/${ticker}`);
      if (response.success) {
        return { market: response.data.market, error: null };
      }
    } catch (backendError) {
      // Fall back to direct Kalshi API
      console.log('Backend unavailable, using direct Kalshi API');
    }

    // Direct Kalshi API call
    const response = await kalshiRequest(`/markets/${ticker}`, apiKey);
    return { market: response.market, error: null };
  } catch (error) {
    console.error('Error getting market details:', error);
    return {
      market: null,
      error: error.type || ErrorTypes.UNKNOWN_ERROR
    };
  }
}

/**
 * Get candlestick data for a market (direct Kalshi API)
 * @param {string} ticker - Market ticker
 * @param {string|null} apiKey
 * @param {string} period - Candle period (1m, 5m, 1h, 1d)
 * @returns {Promise<{candles: object[]|null, error: string|null}>}
 */
export async function getMarketCandlesticks(ticker, apiKey = null, period = '1d') {
  try {
    const endTs = Math.floor(Date.now() / 1000);
    const startTs = endTs - (30 * 24 * 60 * 60);

    const params = new URLSearchParams({
      series_ticker: ticker,
      period: period,
      start_ts: startTs.toString(),
      end_ts: endTs.toString()
    });

    const response = await kalshiRequest(
      `/series/${ticker}/markets/${ticker}/candlesticks?${params}`,
      apiKey
    );

    return { candles: response.candles || [], error: null };
  } catch (error) {
    console.error('Error getting candlesticks:', error);
    return { candles: [], error: null };
  }
}

/**
 * Validate an API key by making a test request
 * @param {string} apiKey
 * @returns {Promise<{valid: boolean, error: string|null}>}
 */
export async function validateApiKey(apiKey) {
  try {
    await kalshiRequest('/portfolio/balance', apiKey);
    return { valid: true, error: null };
  } catch (error) {
    if (error.type === ErrorTypes.INVALID_API_KEY) {
      return { valid: false, error: ErrorTypes.INVALID_API_KEY };
    }
    return { valid: true, error: error.type };
  }
}

/**
 * Check if backend is available
 * @returns {Promise<boolean>}
 */
export async function checkBackendHealth() {
  try {
    const response = await backendRequest('/api/health');
    return response.status === 'ok';
  } catch (error) {
    return false;
  }
}

/**
 * Refresh the backend's market cache
 * @param {string|null} apiKey
 * @returns {Promise<boolean>}
 */
export async function refreshMarketCache(apiKey = null) {
  try {
    const response = await backendRequest('/api/refresh', {
      method: 'POST',
      body: JSON.stringify({ api_key: apiKey })
    });
    return response.success;
  } catch (error) {
    console.error('Error refreshing cache:', error);
    return false;
  }
}

/**
 * Generate URL-friendly slug from text
 * @param {string} text - Text to convert (e.g., "UFC Fight")
 * @returns {string} - URL-friendly slug (e.g., "ufc-fight")
 */
function slugify(text) {
  if (!text) return '';
  return text
    .toLowerCase()
    .replace(/[\s_]+/g, '-')      // Replace spaces/underscores with hyphens
    .replace(/[^a-z0-9\-]/g, '')  // Remove non-alphanumeric chars except hyphens
    .replace(/-+/g, '-')          // Remove consecutive hyphens
    .replace(/^-|-$/g, '');       // Remove leading/trailing hyphens
}

/**
 * Get the Kalshi market URL for a market object
 * @param {object} market - Market object with ticker, event_ticker, and optionally event_title
 * @returns {string} - Full Kalshi market URL
 */
export function getMarketUrl(market) {
  // If market_url is already provided by the backend, use it
  if (market.market_url) {
    return market.market_url;
  }

  const ticker = market.ticker || '';
  const eventTicker = market.event_ticker || '';

  if (!ticker) {
    return 'https://kalshi.com/markets';
  }

  if (!eventTicker) {
    // Fallback to simple URL if no event ticker
    return `https://kalshi.com/markets/${ticker}`;
  }

  // Generate event slug from event title/subtitle if available
  const eventTitle = market.event_title || market.event_sub_title || '';
  const eventSlug = eventTitle ? slugify(eventTitle) : eventTicker;

  return `https://kalshi.com/markets/${eventTicker}/${eventSlug}/${ticker}`;
}

/**
 * Format price from cents to display format
 * @param {number} price - Price in cents (0-100)
 * @returns {string}
 */
export function formatPrice(price) {
  if (price === null || price === undefined) return '--';
  return `${Math.round(price)}¢`;
}

/**
 * Format volume number
 * @param {number} volume
 * @returns {string}
 */
export function formatVolume(volume) {
  if (!volume) return '0';
  if (volume >= 1000000) {
    return `${(volume / 1000000).toFixed(1)}M`;
  }
  if (volume >= 1000) {
    return `${(volume / 1000).toFixed(1)}K`;
  }
  return volume.toString();
}

/**
 * Format date for display
 * @param {string} dateString - ISO date string
 * @returns {string}
 */
export function formatDate(dateString) {
  if (!dateString) return '--';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });
}
