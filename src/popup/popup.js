/**
 * Extension Popup Script
 * Handles API key management in the extension popup
 */

// DOM Elements
const statusSection = document.getElementById('status-section');
const apikeySection = document.getElementById('apikey-section');

// State
let hasApiKey = false;

/**
 * Initialize popup
 */
async function init() {
  await loadUserState();
  render();
}

/**
 * Load user state from storage
 */
async function loadUserState() {
  try {
    const result = await chrome.storage.sync.get(['kalshi_api_key', 'user_mode']);
    hasApiKey = !!(result.kalshi_api_key && result.kalshi_api_key.length > 0);
  } catch (error) {
    console.error('Error loading state:', error);
    hasApiKey = false;
  }
}

/**
 * Render the popup UI
 */
function render() {
  renderStatus();
  renderApiKeySection();
}

/**
 * Render status section
 */
function renderStatus() {
  if (hasApiKey) {
    statusSection.className = 'popup-status connected';
    statusSection.innerHTML = `
      <div class="status-icon connected">&#10003;</div>
      <div class="status-text">
        <div class="status-title">Connected</div>
        <div class="status-subtitle">Your Kalshi account is linked</div>
      </div>
    `;
  } else {
    statusSection.className = 'popup-status disconnected';
    statusSection.innerHTML = `
      <div class="status-icon disconnected">&#8212;</div>
      <div class="status-text">
        <div class="status-title">Not Connected</div>
        <div class="status-subtitle">Add your API key to enable all features</div>
      </div>
    `;
  }
}

/**
 * Render API key section
 */
function renderApiKeySection() {
  if (hasApiKey) {
    apikeySection.innerHTML = `
      <div class="success-message" id="success-message">API key updated successfully!</div>
      <div class="input-group">
        <label class="input-label">API Key</label>
        <input type="password" class="input-field" id="api-input" placeholder="Enter new API key to update">
        <div class="input-error" id="api-error"></div>
      </div>
      <div class="button-group">
        <button class="btn btn-primary" id="update-btn">Update Key</button>
        <button class="btn btn-danger" id="remove-btn">Remove</button>
      </div>
    `;

    document.getElementById('update-btn').addEventListener('click', handleUpdate);
    document.getElementById('remove-btn').addEventListener('click', handleRemove);
  } else {
    apikeySection.innerHTML = `
      <div class="success-message" id="success-message">API key saved successfully!</div>
      <div class="input-group">
        <label class="input-label">Kalshi API Key</label>
        <input type="password" class="input-field" id="api-input" placeholder="Enter your API key">
        <div class="input-error" id="api-error"></div>
      </div>
      <button class="btn btn-primary" id="save-btn">Save API Key</button>
    `;

    document.getElementById('save-btn').addEventListener('click', handleSave);
  }
}

/**
 * Handle save API key
 */
async function handleSave() {
  const input = document.getElementById('api-input');
  const errorDiv = document.getElementById('api-error');
  const saveBtn = document.getElementById('save-btn');
  const successMsg = document.getElementById('success-message');

  const apiKey = input.value.trim();

  if (!apiKey) {
    showError(errorDiv, input, 'Please enter an API key');
    return;
  }

  saveBtn.disabled = true;
  saveBtn.textContent = 'Validating...';
  hideError(errorDiv, input);

  try {
    const response = await chrome.runtime.sendMessage({
      type: 'VALIDATE_API_KEY',
      payload: { apiKey }
    });

    if (response.payload.valid) {
      await chrome.storage.sync.set({
        'kalshi_api_key': apiKey,
        'user_mode': 'authenticated',
        'first_use_completed': true
      });

      hasApiKey = true;
      render();

      // Show success briefly
      const newSuccessMsg = document.getElementById('success-message');
      if (newSuccessMsg) {
        newSuccessMsg.classList.add('visible');
        setTimeout(() => newSuccessMsg.classList.remove('visible'), 3000);
      }
    } else {
      showError(errorDiv, input, 'Invalid API key. Please check and try again.');
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save API Key';
    }
  } catch (error) {
    showError(errorDiv, input, 'Error validating key. Please try again.');
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save API Key';
  }
}

/**
 * Handle update API key
 */
async function handleUpdate() {
  const input = document.getElementById('api-input');
  const errorDiv = document.getElementById('api-error');
  const updateBtn = document.getElementById('update-btn');
  const successMsg = document.getElementById('success-message');

  const apiKey = input.value.trim();

  if (!apiKey) {
    showError(errorDiv, input, 'Please enter a new API key');
    return;
  }

  updateBtn.disabled = true;
  updateBtn.textContent = 'Validating...';
  hideError(errorDiv, input);

  try {
    const response = await chrome.runtime.sendMessage({
      type: 'VALIDATE_API_KEY',
      payload: { apiKey }
    });

    if (response.payload.valid) {
      await chrome.storage.sync.set({
        'kalshi_api_key': apiKey,
        'user_mode': 'authenticated'
      });

      input.value = '';
      successMsg.classList.add('visible');
      setTimeout(() => successMsg.classList.remove('visible'), 3000);

      updateBtn.disabled = false;
      updateBtn.textContent = 'Update Key';
    } else {
      showError(errorDiv, input, 'Invalid API key. Please check and try again.');
      updateBtn.disabled = false;
      updateBtn.textContent = 'Update Key';
    }
  } catch (error) {
    showError(errorDiv, input, 'Error validating key. Please try again.');
    updateBtn.disabled = false;
    updateBtn.textContent = 'Update Key';
  }
}

/**
 * Handle remove API key
 */
async function handleRemove() {
  if (!confirm('Are you sure you want to remove your API key?')) {
    return;
  }

  try {
    await chrome.storage.sync.remove('kalshi_api_key');
    await chrome.storage.sync.set({ 'user_mode': 'free' });

    hasApiKey = false;
    render();
  } catch (error) {
    console.error('Error removing key:', error);
    alert('Error removing API key. Please try again.');
  }
}

/**
 * Show error message
 */
function showError(errorDiv, input, message) {
  errorDiv.textContent = message;
  errorDiv.classList.add('visible');
  input.classList.add('error');
}

/**
 * Hide error message
 */
function hideError(errorDiv, input) {
  errorDiv.classList.remove('visible');
  input.classList.remove('error');
}

/**
 * Initialize advanced settings (backend URL)
 */
async function initAdvancedSettings() {
  const toggle = document.getElementById('advanced-toggle');
  const arrow = document.getElementById('advanced-arrow');
  const content = document.getElementById('advanced-content');
  const urlInput = document.getElementById('backend-url-input');
  const saveBtn = document.getElementById('save-url-btn');
  const resetBtn = document.getElementById('reset-url-btn');

  // Toggle visibility
  toggle.addEventListener('click', () => {
    content.classList.toggle('visible');
    arrow.classList.toggle('open');
  });

  // Load current URL
  try {
    const result = await chrome.storage.sync.get('backend_url');
    if (result.backend_url) {
      urlInput.value = result.backend_url;
    }
  } catch (e) {
    // ignore
  }

  // Save URL
  saveBtn.addEventListener('click', async () => {
    const url = urlInput.value.trim();
    const errorDiv = document.getElementById('backend-url-error');
    const successMsg = document.getElementById('url-success-message');

    hideError(errorDiv, urlInput);

    if (url && !url.match(/^https?:\/\/.+/)) {
      showError(errorDiv, urlInput, 'Please enter a valid URL (starting with http:// or https://)');
      return;
    }

    // If URL provided, verify it's reachable
    if (url) {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Checking...';
      try {
        const resp = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(5000) });
        if (!resp.ok) {
          showError(errorDiv, urlInput, 'Backend responded but health check failed');
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save';
          return;
        }
      } catch {
        showError(errorDiv, urlInput, 'Could not connect to this URL');
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
        return;
      }
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save';
    }

    try {
      if (url) {
        await chrome.storage.sync.set({ 'backend_url': url });
      } else {
        await chrome.storage.sync.remove('backend_url');
      }
      successMsg.classList.add('visible');
      setTimeout(() => successMsg.classList.remove('visible'), 3000);
    } catch (e) {
      showError(errorDiv, urlInput, 'Failed to save URL');
    }
  });

  // Reset URL
  resetBtn.addEventListener('click', async () => {
    urlInput.value = '';
    const errorDiv = document.getElementById('backend-url-error');
    hideError(errorDiv, urlInput);
    try {
      await chrome.storage.sync.remove('backend_url');
      const successMsg = document.getElementById('url-success-message');
      successMsg.textContent = 'Reset to default!';
      successMsg.classList.add('visible');
      setTimeout(() => {
        successMsg.classList.remove('visible');
        successMsg.textContent = 'Backend URL saved!';
      }, 3000);
    } catch (e) {
      // ignore
    }
  });
}

// Initialize
init();
initAdvancedSettings();
