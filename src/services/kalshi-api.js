/**
 * Kalshi API Service
 * Handles all communication with the Kalshi API
 */

const API_BASE_URL = 'https://api.elections.kalshi.com/trade-api/v2';

// Cache for market data to reduce API calls
const marketCache = {
  data: null,
  timestamp: null,
  TTL: 60000 // 1 minute cache
};

/**
 * Error types for categorized error handling
 */
export const ErrorTypes = {
  INVALID_API_KEY: 'INVALID_API_KEY',
  NETWORK_ERROR: 'NETWORK_ERROR',
  RATE_LIMITED: 'RATE_LIMITED',
  SERVER_ERROR: 'SERVER_ERROR',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR'
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
    [ErrorTypes.UNKNOWN_ERROR]: 'Something went wrong. Please try again.'
  };
  return messages[errorType] || messages[ErrorTypes.UNKNOWN_ERROR];
}

/**
 * Parse API error response
 * @param {Response} response
 * @returns {string}
 */
function parseErrorType(response) {
  if (response.status === 401 || response.status === 403) {
    return ErrorTypes.INVALID_API_KEY;
  }
  if (response.status === 429) {
    return ErrorTypes.RATE_LIMITED;
  }
  if (response.status >= 500) {
    return ErrorTypes.SERVER_ERROR;
  }
  return ErrorTypes.UNKNOWN_ERROR;
}

/**
 * Make an authenticated API request
 * @param {string} endpoint
 * @param {string|null} apiKey
 * @param {object} options
 * @returns {Promise<object>}
 */
async function apiRequest(endpoint, apiKey = null, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  };

  if (apiKey) {
    headers['Authorization'] = `Bearer ${apiKey}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        ...headers,
        ...options.headers
      }
    });

    if (!response.ok) {
      const errorType = parseErrorType(response);
      throw { type: errorType, status: response.status };
    }

    return await response.json();
  } catch (error) {
    if (error.type) {
      throw error;
    }
    // Network error
    throw { type: ErrorTypes.NETWORK_ERROR, originalError: error };
  }
}

/**
 * Calculate relevance score for a market based on search query
 * @param {object} market
 * @param {string} query
 * @returns {number}
 */
function calculateRelevance(market, query) {
  const queryLower = query.toLowerCase();
  const queryWords = queryLower.split(/\s+/).filter(w => w.length > 2);

  let score = 0;

  // Check title
  const titleLower = (market.title || '').toLowerCase();
  if (titleLower.includes(queryLower)) {
    score += 100; // Exact phrase match
  }

  // Check individual words
  queryWords.forEach(word => {
    if (titleLower.includes(word)) {
      score += 10;
    }
  });

  // Check subtitle/description
  const subtitleLower = (market.subtitle || '').toLowerCase();
  if (subtitleLower.includes(queryLower)) {
    score += 50;
  }
  queryWords.forEach(word => {
    if (subtitleLower.includes(word)) {
      score += 5;
    }
  });

  // Check category/event
  const categoryLower = (market.category || '').toLowerCase();
  const eventTickerLower = (market.event_ticker || '').toLowerCase();
  queryWords.forEach(word => {
    if (categoryLower.includes(word) || eventTickerLower.includes(word)) {
      score += 3;
    }
  });

  // Boost active markets
  if (market.status === 'open') {
    score += 5;
  }

  // Boost markets with higher volume
  if (market.volume && market.volume > 10000) {
    score += 2;
  }

  return score;
}

/**
 * Fetch all markets from Kalshi API
 * @param {string|null} apiKey
 * @returns {Promise<object[]>}
 */
async function fetchAllMarkets(apiKey = null) {
  // Check cache
  if (marketCache.data && marketCache.timestamp &&
      Date.now() - marketCache.timestamp < marketCache.TTL) {
    return marketCache.data;
  }

  const allMarkets = [];
  let cursor = null;
  const limit = 200; // Max per request

  // Fetch multiple pages (up to 1000 markets for searching)
  for (let i = 0; i < 5; i++) {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (cursor) {
      params.append('cursor', cursor);
    }
    // Only get open markets
    params.append('status', 'open');

    const response = await apiRequest(`/markets?${params}`, apiKey);

    if (response.markets) {
      allMarkets.push(...response.markets);
    }

    cursor = response.cursor;
    if (!cursor) break;
  }

  // Update cache
  marketCache.data = allMarkets;
  marketCache.timestamp = Date.now();

  return allMarkets;
}

/**
 * Search markets by query text
 * @param {string} query - Search query
 * @param {string|null} apiKey - Optional API key
 * @param {number} limit - Max results to return (default 5)
 * @returns {Promise<{markets: object[], error: string|null}>}
 */
export async function searchMarkets(query, apiKey = null, limit = 5) {
  try {
    if (!query || query.trim().length === 0) {
      return { markets: [], error: null };
    }

    const allMarkets = await fetchAllMarkets(apiKey);

    // Score and filter markets
    const scoredMarkets = allMarkets
      .map(market => ({
        ...market,
        relevanceScore: calculateRelevance(market, query)
      }))
      .filter(market => market.relevanceScore > 0)
      .sort((a, b) => b.relevanceScore - a.relevanceScore)
      .slice(0, limit);

    return { markets: scoredMarkets, error: null };
  } catch (error) {
    console.error('Error searching markets:', error);
    return {
      markets: [],
      error: error.type || ErrorTypes.UNKNOWN_ERROR
    };
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
    const response = await apiRequest(`/markets/${ticker}`, apiKey);
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
 * Get candlestick data for a market
 * @param {string} ticker - Market ticker
 * @param {string|null} apiKey
 * @param {string} period - Candle period (1m, 5m, 1h, 1d)
 * @returns {Promise<{candles: object[]|null, error: string|null}>}
 */
export async function getMarketCandlesticks(ticker, apiKey = null, period = '1d') {
  try {
    // Get last 30 days of data
    const endTs = Math.floor(Date.now() / 1000);
    const startTs = endTs - (30 * 24 * 60 * 60);

    const params = new URLSearchParams({
      series_ticker: ticker,
      period: period,
      start_ts: startTs.toString(),
      end_ts: endTs.toString()
    });

    const response = await apiRequest(`/series/${ticker}/markets/${ticker}/candlesticks?${params}`, apiKey);
    return { candles: response.candles || [], error: null };
  } catch (error) {
    console.error('Error getting candlesticks:', error);
    // Don't fail the whole request if candlesticks fail
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
    // Try to fetch account balance - requires valid auth
    await apiRequest('/portfolio/balance', apiKey);
    return { valid: true, error: null };
  } catch (error) {
    if (error.type === ErrorTypes.INVALID_API_KEY) {
      return { valid: false, error: ErrorTypes.INVALID_API_KEY };
    }
    // Other errors don't necessarily mean invalid key
    return { valid: true, error: error.type };
  }
}

/**
 * Get the Kalshi market URL for a ticker
 * @param {string} ticker
 * @returns {string}
 */
export function getMarketUrl(ticker) {
  return `https://kalshi.com/markets/${ticker}`;
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
