/**
 * Background Service Worker
 * Handles context menu, keyboard shortcuts, and API communication
 */

import { getApiKey, isFirstUse, getUserMode } from '../services/storage.js';
import {
  searchMarkets,
  getMarketDetails,
  getMarketCandlesticks,
  validateApiKey,
  ErrorTypes
} from '../services/kalshi-api.js';

// Context menu ID
const CONTEXT_MENU_ID = 'kalshi-find-markets';

/**
 * Initialize the extension
 */
chrome.runtime.onInstalled.addListener(() => {
  // Create context menu item
  chrome.contextMenus.create({
    id: CONTEXT_MENU_ID,
    title: 'Find Markets on Kalshi',
    contexts: ['selection']
  });

  console.log('Kalshi Markets Finder installed');
});

/**
 * Handle context menu clicks
 */
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === CONTEXT_MENU_ID && info.selectionText) {
    triggerSearch(tab.id, info.selectionText);
  }
});

/**
 * Handle keyboard shortcut commands
 */
chrome.commands.onCommand.addListener((command, tab) => {
  if (command === 'find-markets') {
    // Tell content script to get selection and trigger search
    chrome.tabs.sendMessage(tab.id, { type: 'GET_SELECTION_AND_SEARCH' });
  }
});

/**
 * Trigger market search for selected text
 * @param {number} tabId
 * @param {string} selectedText
 */
async function triggerSearch(tabId, selectedText) {
  // Check if first use
  const firstUse = await isFirstUse();
  const userMode = await getUserMode();

  // Notify content script to show popup
  chrome.tabs.sendMessage(tabId, {
    type: 'SHOW_POPUP',
    payload: {
      query: selectedText,
      isFirstUse: firstUse,
      userMode: userMode
    }
  });
}

/**
 * Handle messages from content scripts
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Must return true for async response
  handleMessage(message, sender).then(sendResponse);
  return true;
});

/**
 * Process incoming messages
 * @param {object} message
 * @param {object} sender
 * @returns {Promise<object>}
 */
async function handleMessage(message, sender) {
  const { type, payload } = message;

  switch (type) {
    case 'SEARCH_MARKETS': {
      const apiKey = await getApiKey();
      const result = await searchMarkets(payload.query, apiKey, payload.limit || 5);
      return { type: 'SEARCH_RESULTS', payload: result };
    }

    case 'GET_MARKET_DETAILS': {
      const apiKey = await getApiKey();
      const [marketResult, candlesResult] = await Promise.all([
        getMarketDetails(payload.ticker, apiKey),
        getMarketCandlesticks(payload.ticker, apiKey)
      ]);
      return {
        type: 'MARKET_DETAILS',
        payload: {
          market: marketResult.market,
          candles: candlesResult.candles,
          error: marketResult.error
        }
      };
    }

    case 'VALIDATE_API_KEY': {
      const result = await validateApiKey(payload.apiKey);
      return { type: 'VALIDATION_RESULT', payload: result };
    }

    case 'GET_USER_STATE': {
      const [apiKey, firstUse, userMode] = await Promise.all([
        getApiKey(),
        isFirstUse(),
        getUserMode()
      ]);
      return {
        type: 'USER_STATE',
        payload: {
          hasApiKey: !!apiKey,
          isFirstUse: firstUse,
          userMode: userMode
        }
      };
    }

    case 'TRIGGER_SEARCH': {
      // Content script requesting search with selected text
      if (sender.tab) {
        triggerSearch(sender.tab.id, payload.query);
      }
      return { type: 'ACK' };
    }

    default:
      console.warn('Unknown message type:', type);
      return { type: 'ERROR', payload: { error: 'Unknown message type' } };
  }
}
