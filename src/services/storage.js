/**
 * Chrome Storage Service
 * Handles API key storage and user mode management
 */

const STORAGE_KEYS = {
  API_KEY: 'kalshi_api_key',
  USER_MODE: 'user_mode', // 'authenticated' | 'free' | 'new'
  FIRST_USE: 'first_use_completed',
  BACKEND_URL: 'backend_url'
};

/**
 * Get the stored API key
 * @returns {Promise<string|null>}
 */
export async function getApiKey() {
  try {
    const result = await chrome.storage.sync.get(STORAGE_KEYS.API_KEY);
    return result[STORAGE_KEYS.API_KEY] || null;
  } catch (error) {
    console.error('Error getting API key:', error);
    return null;
  }
}

/**
 * Store the API key
 * @param {string} key - The Kalshi API key
 * @returns {Promise<boolean>}
 */
export async function setApiKey(key) {
  try {
    await chrome.storage.sync.set({
      [STORAGE_KEYS.API_KEY]: key,
      [STORAGE_KEYS.USER_MODE]: 'authenticated'
    });
    return true;
  } catch (error) {
    console.error('Error setting API key:', error);
    return false;
  }
}

/**
 * Remove the stored API key
 * @returns {Promise<boolean>}
 */
export async function removeApiKey() {
  try {
    await chrome.storage.sync.remove(STORAGE_KEYS.API_KEY);
    await chrome.storage.sync.set({
      [STORAGE_KEYS.USER_MODE]: 'free'
    });
    return true;
  } catch (error) {
    console.error('Error removing API key:', error);
    return false;
  }
}

/**
 * Check if user has an API key stored
 * @returns {Promise<boolean>}
 */
export async function isAuthenticated() {
  const apiKey = await getApiKey();
  return apiKey !== null && apiKey.length > 0;
}

/**
 * Get the current user mode
 * @returns {Promise<'authenticated'|'free'|'new'>}
 */
export async function getUserMode() {
  try {
    const result = await chrome.storage.sync.get([
      STORAGE_KEYS.USER_MODE,
      STORAGE_KEYS.FIRST_USE
    ]);

    if (!result[STORAGE_KEYS.FIRST_USE]) {
      return 'new';
    }

    return result[STORAGE_KEYS.USER_MODE] || 'free';
  } catch (error) {
    console.error('Error getting user mode:', error);
    return 'new';
  }
}

/**
 * Mark first use as completed (user has seen API key modal)
 * @param {boolean} skipped - Whether user skipped API key entry
 * @returns {Promise<boolean>}
 */
export async function completeFirstUse(skipped = false) {
  try {
    await chrome.storage.sync.set({
      [STORAGE_KEYS.FIRST_USE]: true,
      [STORAGE_KEYS.USER_MODE]: skipped ? 'free' : 'authenticated'
    });
    return true;
  } catch (error) {
    console.error('Error completing first use:', error);
    return false;
  }
}

/**
 * Check if this is the user's first use
 * @returns {Promise<boolean>}
 */
export async function isFirstUse() {
  try {
    const result = await chrome.storage.sync.get(STORAGE_KEYS.FIRST_USE);
    return !result[STORAGE_KEYS.FIRST_USE];
  } catch (error) {
    console.error('Error checking first use:', error);
    return true;
  }
}

/**
 * Get the stored backend URL
 * @returns {Promise<string|null>}
 */
export async function getBackendUrl() {
  try {
    const result = await chrome.storage.sync.get(STORAGE_KEYS.BACKEND_URL);
    return result[STORAGE_KEYS.BACKEND_URL] || null;
  } catch (error) {
    console.error('Error getting backend URL:', error);
    return null;
  }
}

/**
 * Store the backend URL
 * @param {string} url - The backend URL
 * @returns {Promise<boolean>}
 */
export async function setBackendUrl(url) {
  try {
    await chrome.storage.sync.set({
      [STORAGE_KEYS.BACKEND_URL]: url
    });
    return true;
  } catch (error) {
    console.error('Error setting backend URL:', error);
    return false;
  }
}

/**
 * Remove the stored backend URL (resets to default)
 * @returns {Promise<boolean>}
 */
export async function removeBackendUrl() {
  try {
    await chrome.storage.sync.remove(STORAGE_KEYS.BACKEND_URL);
    return true;
  } catch (error) {
    console.error('Error removing backend URL:', error);
    return false;
  }
}

/**
 * Clear all stored data
 * @returns {Promise<boolean>}
 */
export async function clearAllData() {
  try {
    await chrome.storage.sync.clear();
    return true;
  } catch (error) {
    console.error('Error clearing data:', error);
    return false;
  }
}
