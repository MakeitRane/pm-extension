/**
 * Content Script
 * Handles text selection, popup rendering, and user interaction
 */

// State
let popupRoot = null;
let selectionButton = null;
let currentView = 'list'; // 'list' | 'details' | 'loading' | 'error' | 'apikey'
let currentMarkets = [];
let selectedMarket = null;
let marketDetails = null;
let isFirstUse = false;
let userMode = 'new';
let lastSelectedText = '';
let lastSelectionRect = null;

/**
 * Initialize content script
 */
function init() {
  // Listen for messages from background script
  chrome.runtime.onMessage.addListener(handleMessage);

  // Show floating button on text selection
  document.addEventListener('mouseup', handleMouseUp);
}

/**
 * Handle mouseup - show floating button if text is selected
 */
function handleMouseUp(e) {
  // Ignore if clicking on our own UI
  if (popupRoot?.contains(e.target) || selectionButton?.contains(e.target)) return;

  // Ignore right-clicks (context menu handles those)
  if (e.button === 2) return;

  // Small delay to let selection finalize
  setTimeout(() => {
    const text = getSelectedText();
    if (text && text.length >= 2) {
      showSelectionButton();
    } else {
      removeSelectionButton();
    }
  }, 10);
}

/**
 * Get selected text from the page - handles all text types
 * Supports: regular text, input/textarea, contentEditable, multi-line, etc.
 */
function getSelectedText() {
  let text = '';

  // Check for standard text selection (works for regular text and contentEditable)
  const selection = window.getSelection();
  if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
    text = selection.toString();
  }

  // If no standard selection, check active input/textarea
  if (!text) {
    const activeEl = document.activeElement;
    if (activeEl) {
      if (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA') {
        const start = activeEl.selectionStart;
        const end = activeEl.selectionEnd;
        if (typeof start === 'number' && typeof end === 'number' && start !== end) {
          text = activeEl.value.substring(start, end);
        }
      }
    }
  }

  // Normalize the text: collapse whitespace, trim
  text = text
    .replace(/[\r\n]+/g, ' ')
    .replace(/\t+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  // Truncate very long selections to keep search queries reasonable
  if (text.length > 500) {
    text = text.substring(0, 500);
  }

  return text;
}

/**
 * Get selection rect in viewport coordinates
 * Handles both standard selections and input/textarea selections
 */
function getSelectionRect() {
  const selection = window.getSelection();
  if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    if (rect.width > 0 || rect.height > 0) {
      return rect;
    }
  }

  // Fallback for input/textarea
  const activeEl = document.activeElement;
  if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA')) {
    return activeEl.getBoundingClientRect();
  }

  return null;
}

/**
 * Show floating "Find Markets on Kalshi" button near selection
 */
function showSelectionButton() {
  removeSelectionButton();

  const text = getSelectedText();
  if (!text || text.length < 2) return;

  lastSelectedText = text;

  const rect = getSelectionRect();
  if (!rect) return;

  // Store for popup positioning (viewport coordinates)
  lastSelectionRect = {
    top: rect.top,
    bottom: rect.bottom,
    left: rect.left,
    right: rect.right
  };

  selectionButton = document.createElement('div');
  selectionButton.id = 'kalshi-selection-btn';

  selectionButton.innerHTML = `
    <button class="kalshi-find-btn">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/>
        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      Find Markets on Kalshi
    </button>
  `;

  // Position below selection using absolute coords (stays with text on scroll)
  let top = rect.bottom + window.scrollY + 6;
  let left = rect.left + window.scrollX;

  const btnWidth = 220;
  if (left + btnWidth > window.innerWidth + window.scrollX) {
    left = window.innerWidth + window.scrollX - btnWidth - 16;
  }
  if (left < window.scrollX + 16) {
    left = window.scrollX + 16;
  }

  selectionButton.style.top = `${top}px`;
  selectionButton.style.left = `${left}px`;

  document.body.appendChild(selectionButton);

  // Prevent mousedown from clearing the text selection
  selectionButton.addEventListener('mousedown', (e) => {
    e.preventDefault();
  });

  selectionButton.querySelector('.kalshi-find-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    e.preventDefault();
    handleButtonClick();
  });
}

/**
 * Remove the floating selection button
 */
function removeSelectionButton() {
  if (selectionButton) {
    selectionButton.remove();
    selectionButton = null;
  }
}

/**
 * Handle "Find Markets on Kalshi" button click
 */
async function handleButtonClick() {
  const query = lastSelectedText;
  if (!query) return;

  removeSelectionButton();

  // Get user state from service worker
  try {
    const response = await chrome.runtime.sendMessage({ type: 'GET_USER_STATE' });
    const payload = response?.payload || {};

    isFirstUse = payload.isFirstUse || false;
    userMode = payload.userMode || 'free';

    if (isFirstUse) {
      showApiKeyModal(query);
    } else {
      showPopup(query);
    }
  } catch (error) {
    // Fallback: just show popup directly
    showPopup(query);
  }
}

/**
 * Handle messages from background script
 */
function handleMessage(message, sender, sendResponse) {
  const { type, payload } = message;

  switch (type) {
    case 'GET_SELECTION_AND_SEARCH':
      const selectedText = getSelectedText();
      if (selectedText) {
        // Store selection rect before it might get cleared
        const rect = getSelectionRect();
        if (rect) {
          lastSelectionRect = {
            top: rect.top,
            bottom: rect.bottom,
            left: rect.left,
            right: rect.right
          };
        }
        chrome.runtime.sendMessage({
          type: 'TRIGGER_SEARCH',
          payload: { query: selectedText }
        });
      }
      break;

    case 'SHOW_POPUP':
      isFirstUse = payload.isFirstUse;
      userMode = payload.userMode;

      // Store selection rect if still available
      const selRect = getSelectionRect();
      if (selRect) {
        lastSelectionRect = {
          top: selRect.top,
          bottom: selRect.bottom,
          left: selRect.left,
          right: selRect.right
        };
      }

      removeSelectionButton();

      if (isFirstUse) {
        showApiKeyModal(payload.query);
      } else {
        showPopup(payload.query);
      }
      break;
  }
}

/**
 * Get popup position based on selection
 * Uses viewport coordinates for position:fixed
 */
function getPopupPosition() {
  let rect = null;

  // Try active selection first
  const selRect = getSelectionRect();
  if (selRect) {
    rect = selRect;
  }

  // Fall back to stored selection rect
  if (!rect && lastSelectionRect) {
    rect = lastSelectionRect;
  }

  if (!rect) {
    return { top: 100, left: 100 };
  }

  // position:fixed uses viewport coordinates - no scroll offset
  let top = rect.bottom + 8;
  let left = rect.left;

  const popupWidth = 420;
  const popupHeight = 480;

  if (left + popupWidth > window.innerWidth) {
    left = window.innerWidth - popupWidth - 16;
  }
  if (left < 16) {
    left = 16;
  }

  // If popup would go below viewport, show above selection
  if (top + popupHeight > window.innerHeight) {
    top = rect.top - popupHeight - 8;
  }

  return { top, left };
}

/**
 * Create and show the popup
 */
function showPopup(query) {
  removePopup();

  const position = getPopupPosition();

  popupRoot = document.createElement('div');
  popupRoot.id = 'kalshi-finder-root';
  popupRoot.style.top = `${position.top}px`;
  popupRoot.style.left = `${position.left}px`;

  renderLoading(query);
  document.body.appendChild(popupRoot);

  // Add click outside listener
  setTimeout(() => {
    document.addEventListener('click', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
  }, 100);

  // Search for markets
  searchMarkets(query);
}

/**
 * Remove the popup
 */
function removePopup() {
  if (popupRoot) {
    popupRoot.remove();
    popupRoot = null;
  }
  removeSelectionButton();
  currentView = 'list';
  currentMarkets = [];
  selectedMarket = null;
  marketDetails = null;

  document.removeEventListener('click', handleClickOutside);
  document.removeEventListener('keydown', handleKeyDown);
}

/**
 * Handle click outside popup
 */
function handleClickOutside(event) {
  if (popupRoot && !popupRoot.contains(event.target)) {
    removePopup();
  }
}

/**
 * Handle keyboard events
 */
function handleKeyDown(event) {
  if (event.key === 'Escape') {
    removePopup();
  }
}

/**
 * Search for markets
 */
async function searchMarkets(query) {
  try {
    const response = await chrome.runtime.sendMessage({
      type: 'SEARCH_MARKETS',
      payload: { query, limit: 5 }
    });

    if (!response || !response.payload) {
      console.error('Search: empty response from service worker', response);
      renderError('BACKEND_UNAVAILABLE');
      return;
    }

    if (response.payload.error) {
      renderError(response.payload.error);
    } else if (!response.payload.markets || response.payload.markets.length === 0) {
      renderNoResults();
    } else {
      currentMarkets = response.payload.markets;
      renderMarketList(query);
    }
  } catch (error) {
    console.error('Search error:', error);
    // Check if this is a disconnected extension error (stale content script after reload)
    if (error?.message?.includes('Extension context invalidated') ||
        error?.message?.includes('Receiving end does not exist')) {
      renderError('EXTENSION_RELOADED');
    } else {
      renderError('UNKNOWN_ERROR');
    }
  }
}

/**
 * Render loading state
 */
function renderLoading(query) {
  const truncatedQuery = query.length > 30 ? query.substring(0, 30) + '...' : query;

  popupRoot.innerHTML = `
    <div class="kalshi-popup">
      <div class="kalshi-popup-header">
        <div class="kalshi-popup-title">Markets for "<span>${escapeHtml(truncatedQuery)}</span>"</div>
        <button class="kalshi-popup-close" aria-label="Close">&times;</button>
      </div>
      <div class="kalshi-popup-content">
        <div class="kalshi-loading">
          <div class="kalshi-spinner"></div>
          <div class="kalshi-loading-text">Searching markets...</div>
        </div>
      </div>
      <div class="kalshi-popup-footer">Not Financial Advice</div>
    </div>
  `;

  popupRoot.querySelector('.kalshi-popup-close').addEventListener('click', removePopup);
}

/**
 * Render error state
 */
function renderError(errorType) {
  const errorMessages = {
    'INVALID_API_KEY': 'Invalid API key. Please check your key in settings.',
    'NETWORK_ERROR': 'Unable to connect. Please check your internet connection.',
    'RATE_LIMITED': 'Too many requests. Please wait a moment and try again.',
    'SERVER_ERROR': 'Kalshi servers are experiencing issues. Please try again later.',
    'UNKNOWN_ERROR': 'Something went wrong. Please try again.',
    'BACKEND_UNAVAILABLE': 'Search backend is not running. Please start the Python server.',
    'EXTENSION_RELOADED': 'Extension was updated. Please refresh this page and try again.',
    // Gemini-specific error messages
    'GEMINI_RATE_LIMITED': 'AI rate limit reached. Please wait a moment and try again.',
    'GEMINI_AUTH_ERROR': 'AI service authentication failed. Please contact support.',
    'GEMINI_UNAVAILABLE': 'AI service is temporarily unavailable. Please try again later.',
    'GEMINI_NOT_CONFIGURED': 'AI service is not configured. Please contact support.'
  };

  const message = errorMessages[errorType] || errorMessages['UNKNOWN_ERROR'];

  const content = popupRoot.querySelector('.kalshi-popup-content');
  content.innerHTML = `
    <div class="kalshi-error">
      <div class="kalshi-error-icon">!</div>
      <div class="kalshi-error-message">${escapeHtml(message)}</div>
    </div>
  `;
}

/**
 * Render no results state
 */
function renderNoResults() {
  const content = popupRoot.querySelector('.kalshi-popup-content');
  content.innerHTML = `
    <div class="kalshi-no-results">
      <div class="kalshi-no-results-icon">&#128269;</div>
      <div class="kalshi-no-results-text">No markets found</div>
    </div>
  `;
}

/**
 * Render market list - displays event groups with expandable outcomes
 */
function renderMarketList(query) {
  const truncatedQuery = query.length > 30 ? query.substring(0, 30) + '...' : query;

  // currentMarkets is now an array of event groups
  const eventGroupsHtml = currentMarkets.map((eventGroup, groupIndex) => {
    const eventTitle = eventGroup.event_title || 'Unknown Event';
    const explanation = eventGroup.explanation || '';
    const markets = eventGroup.markets || [];
    const hasMultipleOutcomes = markets.length > 1;

    // Render explanation if available
    const explanationHtml = explanation
      ? `<div class="kalshi-market-explanation">${escapeHtml(explanation)}</div>`
      : '';

    // Render outcome rows for each market in the group
    const outcomesHtml = markets.map((market, marketIndex) => {
      const outcomeTitle = market.outcome_title || market.ticker;
      const yesPrice = formatPrice(market.last_price || market.yes_ask || market.yes_bid);

      return `
        <div class="kalshi-outcome-row" data-group="${groupIndex}" data-market="${marketIndex}">
          <span class="kalshi-outcome-name">${escapeHtml(outcomeTitle)}</span>
          <span class="kalshi-outcome-odds">${yesPrice}</span>
        </div>
      `;
    }).join('');

    // Determine if we should show expanded view or collapsed
    const showExpanded = markets.length <= 3;
    const visibleOutcomes = showExpanded ? outcomesHtml : markets.slice(0, 2).map((market, marketIndex) => {
      const outcomeTitle = market.outcome_title || market.ticker;
      const yesPrice = formatPrice(market.last_price || market.yes_ask || market.yes_bid);

      return `
        <div class="kalshi-outcome-row" data-group="${groupIndex}" data-market="${marketIndex}">
          <span class="kalshi-outcome-name">${escapeHtml(outcomeTitle)}</span>
          <span class="kalshi-outcome-odds">${yesPrice}</span>
        </div>
      `;
    }).join('');

    const expandButton = !showExpanded && markets.length > 2
      ? `<button class="kalshi-expand-btn" data-group="${groupIndex}">+${markets.length - 2} more outcomes</button>`
      : '';

    const hiddenOutcomes = !showExpanded && markets.length > 2
      ? `<div class="kalshi-hidden-outcomes" data-group="${groupIndex}" style="display: none;">
          ${markets.slice(2).map((market, marketIndex) => {
            const outcomeTitle = market.outcome_title || market.ticker;
            const yesPrice = formatPrice(market.last_price || market.yes_ask || market.yes_bid);

            return `
              <div class="kalshi-outcome-row" data-group="${groupIndex}" data-market="${marketIndex + 2}">
                <span class="kalshi-outcome-name">${escapeHtml(outcomeTitle)}</span>
                <span class="kalshi-outcome-odds">${yesPrice}</span>
              </div>
            `;
          }).join('')}
        </div>`
      : '';

    return `
      <div class="kalshi-event-card" data-group="${groupIndex}">
        <div class="kalshi-event-header">
          <div class="kalshi-event-title">${escapeHtml(eventTitle)}</div>
        </div>
        ${explanationHtml}
        <div class="kalshi-outcomes-container">
          ${showExpanded ? outcomesHtml : visibleOutcomes}
          ${hiddenOutcomes}
          ${expandButton}
        </div>
        <div class="kalshi-event-footer">
          ${hasMultipleOutcomes ? `<span class="kalshi-outcome-count">${markets.length} outcomes</span>` : ''}
        </div>
      </div>
    `;
  }).join('');

  popupRoot.innerHTML = `
    <div class="kalshi-popup">
      <div class="kalshi-popup-header">
        <div class="kalshi-popup-title">Markets for "<span>${escapeHtml(truncatedQuery)}</span>"</div>
        <button class="kalshi-popup-close" aria-label="Close">&times;</button>
      </div>
      <div class="kalshi-popup-content">
        ${eventGroupsHtml}
      </div>
      <div class="kalshi-popup-footer">Not Financial Advice</div>
    </div>
  `;

  // Add event listeners
  popupRoot.querySelector('.kalshi-popup-close').addEventListener('click', removePopup);

  // Handle outcome row clicks - open market URL
  popupRoot.querySelectorAll('.kalshi-outcome-row').forEach(chip => {
    chip.addEventListener('click', (e) => {
      e.stopPropagation();
      const groupIndex = parseInt(chip.dataset.group);
      const marketIndex = parseInt(chip.dataset.market);
      const eventGroup = currentMarkets[groupIndex];
      const market = eventGroup.markets[marketIndex];

      // Open the Kalshi market page in a new tab
      const marketUrl = market.market_url || `https://kalshi.com/markets/${market.ticker}`;
      window.open(marketUrl, '_blank');
    });
  });

  // Handle expand button clicks
  popupRoot.querySelectorAll('.kalshi-expand-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const groupIndex = btn.dataset.group;
      const hiddenOutcomes = popupRoot.querySelector(`.kalshi-hidden-outcomes[data-group="${groupIndex}"]`);

      if (hiddenOutcomes) {
        const isHidden = hiddenOutcomes.style.display === 'none';
        hiddenOutcomes.style.display = isHidden ? 'flex' : 'none';
        btn.textContent = isHidden
          ? 'Show less'
          : `+${currentMarkets[groupIndex].markets.length - 2} more outcomes`;
      }
    });
  });
}

/**
 * Load market details
 */
async function loadMarketDetails(ticker) {
  renderDetailsLoading();

  try {
    const response = await chrome.runtime.sendMessage({
      type: 'GET_MARKET_DETAILS',
      payload: { ticker }
    });

    if (!response || !response.payload) {
      console.error('Details: empty response from service worker', response);
      renderError('BACKEND_UNAVAILABLE');
      return;
    }

    if (response.payload.error) {
      renderError(response.payload.error);
    } else {
      marketDetails = response.payload;
      renderMarketDetails();
    }
  } catch (error) {
    console.error('Details error:', error);
    renderError('UNKNOWN_ERROR');
  }
}

/**
 * Render details loading state
 */
function renderDetailsLoading() {
  const content = popupRoot.querySelector('.kalshi-popup-content');
  content.innerHTML = `
    <div class="kalshi-loading">
      <div class="kalshi-spinner"></div>
      <div class="kalshi-loading-text">Loading details...</div>
    </div>
  `;
}

/**
 * Render market details
 */
function renderMarketDetails() {
  const market = marketDetails.market || selectedMarket;
  const candles = marketDetails.candles || [];

  const yesPrice = market.last_price || market.yes_ask || market.yes_bid || 50;
  const noPrice = market.no_ask || (100 - yesPrice);

  // Calculate 24h change (mock if no data)
  const priceChange = candles.length >= 2
    ? ((candles[candles.length - 1]?.close || yesPrice) - (candles[0]?.close || yesPrice))
    : 0;
  const changeClass = priceChange >= 0 ? 'up' : 'down';
  const changeSign = priceChange >= 0 ? '+' : '';

  const content = popupRoot.querySelector('.kalshi-popup-content');
  content.innerHTML = `
    <div class="kalshi-market-details">
      <div class="kalshi-details-header">
        <button class="kalshi-back-btn" aria-label="Back">&larr;</button>
        <div class="kalshi-details-title">${escapeHtml(market.title || market.ticker)}</div>
      </div>

      <div class="kalshi-details-prices">
        <div class="kalshi-price-large yes">
          <div class="kalshi-price-label">Yes</div>
          <div class="kalshi-price-value yes">${formatPrice(yesPrice)}</div>
        </div>
        <div class="kalshi-price-large no">
          <div class="kalshi-price-label">No</div>
          <div class="kalshi-price-value no">${formatPrice(noPrice)}</div>
        </div>
      </div>

      <div class="kalshi-stats-grid">
        <div class="kalshi-stat">
          <div class="kalshi-stat-label">24h Volume</div>
          <div class="kalshi-stat-value">${formatVolume(market.volume_24h || market.volume || 0)}</div>
        </div>
        <div class="kalshi-stat">
          <div class="kalshi-stat-label">24h Change</div>
          <div class="kalshi-stat-value ${changeClass}">${changeSign}${priceChange.toFixed(1)}¢</div>
        </div>
        <div class="kalshi-stat">
          <div class="kalshi-stat-label">Total Volume</div>
          <div class="kalshi-stat-value">${formatVolume(market.volume || 0)}</div>
        </div>
        <div class="kalshi-stat">
          <div class="kalshi-stat-label">Closes</div>
          <div class="kalshi-stat-value">${formatDate(market.close_time || market.expiration_time)}</div>
        </div>
        <div class="kalshi-stat">
          <div class="kalshi-stat-label">Last Trade</div>
          <div class="kalshi-stat-value">${formatPrice(market.last_price)}</div>
        </div>
        <div class="kalshi-stat">
          <div class="kalshi-stat-label">Open Interest</div>
          <div class="kalshi-stat-value">${formatVolume(market.open_interest || 0)}</div>
        </div>
      </div>

      <div class="kalshi-chart-container">
        <canvas class="kalshi-chart-canvas" id="kalshi-price-chart"></canvas>
      </div>

      <button class="kalshi-trade-btn">Trade on Kalshi</button>
    </div>
  `;

  // Event listeners
  content.querySelector('.kalshi-back-btn').addEventListener('click', () => {
    renderMarketList(currentMarkets[0]?.title || 'Markets');
  });

  content.querySelector('.kalshi-trade-btn').addEventListener('click', () => {
    if (userMode === 'free' || userMode === 'new') {
      showApiKeyModal(null, true);
    } else {
      // Use the market_url from the API if available, otherwise fall back to ticker-only URL
      const url = market.market_url || `https://kalshi.com/markets/${market.ticker}`;
      window.open(url, '_blank');
    }
  });

  // Render chart
  if (candles.length > 0) {
    renderMiniChart(candles);
  }
}

/**
 * Render mini price chart
 */
function renderMiniChart(candles) {
  const canvas = document.getElementById('kalshi-price-chart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const rect = canvas.parentElement.getBoundingClientRect();

  canvas.width = rect.width - 24;
  canvas.height = rect.height - 24;

  const prices = candles.map(c => c.close || c.price || 50);
  if (prices.length === 0) return;

  const minPrice = Math.min(...prices) - 5;
  const maxPrice = Math.max(...prices) + 5;
  const priceRange = maxPrice - minPrice || 1;

  const width = canvas.width;
  const height = canvas.height;
  const stepX = width / (prices.length - 1 || 1);

  // Draw line
  ctx.beginPath();
  ctx.strokeStyle = '#0AC285';
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  prices.forEach((price, i) => {
    const x = i * stepX;
    const y = height - ((price - minPrice) / priceRange) * height;

    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });

  ctx.stroke();

  // Draw area fill
  ctx.lineTo(width, height);
  ctx.lineTo(0, height);
  ctx.closePath();

  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, 'rgba(10, 194, 133, 0.2)');
  gradient.addColorStop(1, 'rgba(10, 194, 133, 0)');
  ctx.fillStyle = gradient;
  ctx.fill();
}

/**
 * Show API key modal
 */
function showApiKeyModal(query = null, isTradeRedirect = false) {
  // Create modal overlay
  const modalOverlay = document.createElement('div');
  modalOverlay.className = 'kalshi-modal-overlay';
  modalOverlay.id = 'kalshi-api-modal';

  modalOverlay.innerHTML = `
    <div class="kalshi-modal">
      <div class="kalshi-modal-header">
        <div class="kalshi-modal-title">Connect Your Kalshi Account</div>
        <div class="kalshi-modal-subtitle">Enter your API key to access full features and trade directly.</div>
      </div>
      <div class="kalshi-modal-body">
        <div class="kalshi-input-group">
          <label class="kalshi-input-label">Kalshi API Key</label>
          <input type="password" class="kalshi-input" id="kalshi-api-input" placeholder="Enter your API key">
          <div class="kalshi-input-error" id="kalshi-api-error" style="display: none;"></div>
        </div>
        <div class="kalshi-modal-actions">
          <button class="kalshi-btn-primary" id="kalshi-save-key">Save API Key</button>
          <div class="kalshi-skip-link" id="kalshi-skip-btn">Skip for now and use as free user</div>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(modalOverlay);

  const input = modalOverlay.querySelector('#kalshi-api-input');
  const saveBtn = modalOverlay.querySelector('#kalshi-save-key');
  const skipBtn = modalOverlay.querySelector('#kalshi-skip-btn');
  const errorDiv = modalOverlay.querySelector('#kalshi-api-error');

  // Save API key
  saveBtn.addEventListener('click', async () => {
    const apiKey = input.value.trim();
    if (!apiKey) {
      errorDiv.textContent = 'Please enter an API key';
      errorDiv.style.display = 'block';
      input.classList.add('error');
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = 'Validating...';

    try {
      const response = await chrome.runtime.sendMessage({
        type: 'VALIDATE_API_KEY',
        payload: { apiKey }
      });

      if (response.payload.valid) {
        // Save the key
        await chrome.storage.sync.set({
          'kalshi_api_key': apiKey,
          'user_mode': 'authenticated',
          'first_use_completed': true
        });

        userMode = 'authenticated';
        isFirstUse = false;

        modalOverlay.remove();

        if (isTradeRedirect && selectedMarket) {
          // Use the market_url from the API if available, otherwise fall back to ticker-only URL
          const url = selectedMarket.market_url || `https://kalshi.com/markets/${selectedMarket.ticker}`;
          window.open(url, '_blank');
        } else if (query) {
          showPopup(query);
        }
      } else {
        errorDiv.textContent = 'Invalid API key. Please check and try again.';
        errorDiv.style.display = 'block';
        input.classList.add('error');
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save API Key';
      }
    } catch (error) {
      errorDiv.textContent = 'Error validating key. Please try again.';
      errorDiv.style.display = 'block';
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save API Key';
    }
  });

  // Skip
  skipBtn.addEventListener('click', async () => {
    await chrome.storage.sync.set({
      'user_mode': 'free',
      'first_use_completed': true
    });

    userMode = 'free';
    isFirstUse = false;

    modalOverlay.remove();

    if (!isTradeRedirect && query) {
      showPopup(query);
    }
  });

  // Close on click outside
  modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) {
      modalOverlay.remove();
      if (!isTradeRedirect && query) {
        showPopup(query);
      }
    }
  });

  // Focus input
  setTimeout(() => input.focus(), 100);
}

/**
 * Utility: Format price
 */
function formatPrice(price) {
  if (price === null || price === undefined) return '--';
  return `${Math.round(price)}%`;
}

/**
 * Utility: Format volume
 */
function formatVolume(volume) {
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
 * Utility: Format date
 */
function formatDate(dateString) {
  if (!dateString) return '--';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric'
  });
}

/**
 * Utility: Escape HTML
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Initialize
init();
