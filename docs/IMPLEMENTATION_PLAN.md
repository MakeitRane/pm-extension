# Implementation Plan: Kalshi Markets Finder

## Overview

This document outlines the step-by-step implementation plan for building the Kalshi Markets Finder Chrome extension.

---

## Phase 1: Project Setup & Foundation

### 1.1 Initialize Project Structure
```
kalshi-markets-finder/
├── manifest.json           # Extension manifest (v3)
├── src/
│   ├── background/
│   │   └── service-worker.js   # Background script
│   ├── content/
│   │   ├── content.js          # Content script
│   │   └── content.css         # Popup overlay styles
│   ├── popup/
│   │   ├── popup.html          # Extension icon popup
│   │   ├── popup.js            # Popup logic
│   │   └── popup.css           # Popup styles
│   ├── components/
│   │   ├── MarketCard.js       # Market result card component
│   │   ├── MarketDetails.js    # Expanded details view
│   │   ├── MiniChart.js        # Sparkline chart component
│   │   ├── ApiKeyModal.js      # API key input modal
│   │   └── ErrorMessage.js     # Error display component
│   ├── services/
│   │   ├── kalshi-api.js       # Kalshi API wrapper
│   │   └── storage.js          # Chrome storage wrapper
│   ├── utils/
│   │   └── helpers.js          # Utility functions
│   └── styles/
│       └── variables.css       # CSS variables (colors, spacing)
├── assets/
│   ├── icons/
│   │   ├── icon-16.png
│   │   ├── icon-32.png
│   │   ├── icon-48.png
│   │   └── icon-128.png
│   └── logo.svg
├── docs/
│   ├── PRD.md
│   └── IMPLEMENTATION_PLAN.md
└── README.md
```

### 1.2 Create Manifest File (manifest.json)
- Use Manifest V3 (latest Chrome extension standard)
- Define permissions: `activeTab`, `storage`, `contextMenus`
- Register background service worker
- Register content scripts
- Define keyboard shortcut command (`Ctrl+K` / `Cmd+K`)
- Set extension icons

### 1.3 Set Up Development Environment
- No build step required for MVP (vanilla JS)
- Optional: Set up live reload for development
- Load extension in Chrome via `chrome://extensions` → Developer mode → Load unpacked

---

## Phase 2: Core Infrastructure

### 2.1 Chrome Storage Service (`src/services/storage.js`)
**Purpose:** Abstract Chrome storage API for API key management

**Functions:**
- `getApiKey()` - Retrieve stored API key
- `setApiKey(key)` - Store API key
- `removeApiKey()` - Clear API key
- `isAuthenticated()` - Check if user has API key
- `getUserMode()` - Returns 'authenticated' | 'free' | 'new'

### 2.2 Kalshi API Service (`src/services/kalshi-api.js`)
**Purpose:** Handle all Kalshi API communication

**Option A: Use Kalshi TypeScript SDK**
- Install via npm: `@anthropic-ai/kalshi` or similar
- SDK documentation: https://docs.kalshi.com/typescript-sdk/api/MarketsApi
- Provides type safety and built-in error handling

**Option B: Direct API Calls (chosen for simplicity)**
- No build step required for vanilla JS approach

**Functions:**
- `searchMarkets(query, limit=5)` - Fetch all markets via `getMarkets()`, filter client-side by query relevance
- `getMarketDetails(ticker)` - Get full market info
- `getMarketCandlesticks(ticker, period='1d')` - Get price history
- `validateApiKey(key)` - Test if API key is valid

**Implementation Notes:**
- Use `fetch()` for HTTP requests
- **Client-side filtering:** Fetch markets from `getMarkets()` and filter/rank by text relevance to user's query
- Handle authentication header injection
- Implement error parsing and categorization
- Consider caching recent results
- **Rate limits:** 20 reads/sec, 10 writes/sec (reads only for this extension)

### 2.3 Background Service Worker (`src/background/service-worker.js`)
**Purpose:** Handle extension lifecycle, context menu, keyboard shortcuts

**Responsibilities:**
- Register context menu item on install
- Listen for context menu clicks
- Listen for keyboard shortcut commands
- Route messages between content script and API service
- Handle API calls (content scripts can't make cross-origin requests directly)

---

## Phase 3: User Interface Components

### 3.1 Design System Setup (`src/styles/variables.css`)
```css
:root {
  /* Colors - Kalshi Brand */
  --kalshi-green: #0AC285;
  --kalshi-green-light: #E6F9F3;
  --kalshi-green-dark: #089B6A;
  --bg-primary: #FFFFFF;
  --bg-secondary: #F8F9FA;
  --text-primary: #1A1A1A;
  --text-secondary: #6B7280;
  --border-color: #E5E7EB;
  --error-red: #EF4444;

  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;

  /* Typography */
  --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-size-sm: 12px;
  --font-size-md: 14px;
  --font-size-lg: 16px;

  /* Effects */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.1);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.15);
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
}
```

### 3.2 Market Card Component (`src/components/MarketCard.js`)
**Displays:** Single market result in collapsed state

**Elements:**
- Market title/question (truncated if long)
- Yes price pill (green background)
- No price pill (light gray background)
- Hover state with subtle lift effect
- Click handler to expand details

### 3.3 Market Details Component (`src/components/MarketDetails.js`)
**Displays:** Expanded view with full market information

**Elements:**
- Full market title
- Yes/No prices (larger, prominent)
- Stats grid:
  - Volume (24h)
  - Total Volume
  - Close Date
  - Last Trade
  - 24h Change (green/red based on direction)
  - Open Interest
- Mini chart area
- "Trade on Kalshi" button (green, prominent)
- Close/back button

### 3.4 Mini Chart Component (`src/components/MiniChart.js`)
**Displays:** Price history visualization

**Implementation:**
- Use Canvas API or SVG for lightweight rendering
- Show last 7-30 days of price data
- Simple line chart or area chart
- Green line color matching brand
- No axis labels (keep it minimal)

### 3.5 API Key Modal (`src/components/ApiKeyModal.js`)
**Displays:** API key input form

**Elements:**
- Header: "Connect Your Kalshi Account"
- Subtext: Brief explanation of why API key is needed
- Input field for API key (password type, with show/hide toggle)
- "Save" button (green)
- "Skip for now" link (subtle, below button)
- Error message area for invalid key feedback

### 3.6 Error Message Component (`src/components/ErrorMessage.js`)
**Displays:** Error states with appropriate messaging

**Elements:**
- Error icon
- Error message text
- Optional retry button
- Styled with error color (red accent)

---

## Phase 4: Content Script & Popup Overlay

### 4.1 Content Script (`src/content/content.js`)
**Purpose:** Inject into web pages, handle selection, render popup

**Responsibilities:**
- Listen for messages from background script
- Get selected text from page
- Calculate popup position based on selection
- Inject popup overlay into page DOM
- Handle popup interactions (clicks, close)
- Clean up popup when dismissed

**Popup Positioning Logic:**
1. Get selection bounding rect
2. Position popup below selection (or above if near bottom)
3. Keep popup within viewport bounds
4. Handle scroll events (reposition or dismiss)

### 4.2 Popup Overlay Container
**Structure:**
```html
<div id="kalshi-finder-popup" class="kalshi-popup">
  <div class="kalshi-popup-header">
    <span class="kalshi-popup-title">Markets for "highlighted text"</span>
    <button class="kalshi-popup-close">×</button>
  </div>
  <div class="kalshi-popup-content">
    <!-- Market cards or loading/error states -->
  </div>
</div>
```

**CSS Considerations:**
- Use Shadow DOM or highly specific selectors to avoid style conflicts
- Fixed/absolute positioning
- High z-index to stay above page content
- Smooth fade-in animation

---

## Phase 5: Extension Popup (Icon Click)

### 5.1 Popup HTML (`src/popup/popup.html`)
**Purpose:** Settings panel when user clicks extension icon

**Sections:**
- Header with logo
- API Key status (connected/not connected)
- API Key input field (if not connected)
- "Update API Key" / "Disconnect" buttons (if connected)
- Link to Kalshi website
- Version number

### 5.2 Popup Logic (`src/popup/popup.js`)
- Load current auth state on open
- Handle API key save/update/remove
- Validate key before saving
- Show success/error feedback

---

## Phase 6: Integration & Message Passing

### 6.1 Message Protocol
Define message types for communication between components:

```javascript
// Content → Background
{ type: 'SEARCH_MARKETS', payload: { query: string } }
{ type: 'GET_MARKET_DETAILS', payload: { ticker: string } }
{ type: 'GET_CANDLESTICKS', payload: { ticker: string } }

// Background → Content
{ type: 'SEARCH_RESULTS', payload: { markets: [], error: null } }
{ type: 'MARKET_DETAILS', payload: { market: {}, error: null } }
{ type: 'CANDLESTICKS', payload: { data: [], error: null } }

// Background → Content (Triggers)
{ type: 'TRIGGER_SEARCH' }  // From keyboard shortcut or context menu
```

### 6.2 Integration Flow
1. User triggers search (keyboard/context menu)
2. Background receives trigger, sends `TRIGGER_SEARCH` to content script
3. Content script gets selected text, sends `SEARCH_MARKETS` to background
4. Background calls Kalshi API, returns `SEARCH_RESULTS`
5. Content script renders popup with results
6. User clicks market, content sends `GET_MARKET_DETAILS`
7. Background fetches details + candlesticks, returns data
8. Content script renders expanded view

---

## Phase 7: Polish & Edge Cases

### 7.1 Edge Cases to Handle
- No text selected when triggered
- Very long selected text (truncate query)
- Multiple rapid triggers (debounce)
- Popup already open when triggered again
- Page scroll while popup open
- Window resize
- Navigating away from page
- iframes and shadow DOMs

### 7.2 Loading States
- Skeleton loaders for market cards
- Spinner for details/chart loading
- Subtle, non-blocking loading indicators

### 7.3 Animations
- Popup fade-in (150ms ease-out)
- Market card expand/collapse (200ms ease)
- Button hover states
- Error shake animation

### 7.4 Accessibility
- Keyboard navigation within popup
- Escape key to close popup
- Focus management
- ARIA labels for interactive elements
- Sufficient color contrast

---

## Phase 8: Testing & Quality Assurance

### 8.1 Manual Testing Checklist
- [ ] Extension installs correctly
- [ ] Keyboard shortcut works (Mac and Windows)
- [ ] Context menu appears and works
- [ ] API key save/load works
- [ ] Free mode works correctly
- [ ] Search returns relevant results
- [ ] Market details load correctly
- [ ] Chart renders properly
- [ ] Trade button opens correct Kalshi page
- [ ] Error messages display correctly
- [ ] Works on various websites (news sites, social media, etc.)
- [ ] Popup positioning is correct
- [ ] No console errors
- [ ] Memory usage is reasonable

### 8.2 Websites to Test On
- News sites: CNN, NYT, BBC, Reuters
- Social media: Twitter/X, Reddit
- Search: Google results page
- Blogs: Medium, Substack
- Finance: Bloomberg, Yahoo Finance

---

## Phase 9: Deployment

### 9.1 Pre-Submission Checklist
- [ ] All icons are correct sizes
- [ ] Manifest has correct version number
- [ ] Remove any console.log statements
- [ ] Test on clean Chrome profile
- [ ] Write Chrome Web Store description
- [ ] Create promotional screenshots
- [ ] Prepare privacy policy (required for API usage)

### 9.2 Chrome Web Store Submission
1. Create Chrome Web Store developer account ($5 one-time fee)
2. Prepare store listing:
   - Extension name
   - Short description (132 chars max)
   - Detailed description
   - Screenshots (1280x800 or 640x400)
   - Promotional images (optional)
   - Category: Productivity or News
3. Upload ZIP of extension
4. Submit for review (typically 1-3 days)

---

## Implementation Order (Recommended)

### Sprint 1: Foundation
1. Project setup & manifest
2. Storage service
3. Kalshi API service (basic)
4. Background service worker (context menu + shortcut)

### Sprint 2: Core UI
5. Design system (CSS variables)
6. Content script (selection + popup container)
7. Market card component
8. API key modal

### Sprint 3: Features
9. Market details component
10. Mini chart component
11. Error handling
12. Message passing integration

### Sprint 4: Polish
13. Extension popup (settings)
14. Edge cases & loading states
15. Animations & accessibility
16. Testing & bug fixes

### Sprint 5: Launch
17. Final testing
18. Store assets preparation
19. Chrome Web Store submission

---

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | Vanilla JS | Simpler, smaller bundle, no build step |
| Manifest Version | V3 | Required for new extensions, more secure |
| Styling | CSS (no preprocessor) | Simpler, sufficient for scope |
| State Management | Simple module pattern | No need for Redux/etc at this scale |
| Charts | Canvas API | Lightweight, no dependencies |
| Shadow DOM | No (scoped CSS) | Simpler, Shadow DOM has quirks |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Kalshi API changes | High | Version lock API, monitor for changes |
| Cmd+K conflicts | Medium | Document conflicts, consider alt shortcut |
| Rate limiting | Medium | Implement caching, respect limits |
| Store rejection | Medium | Follow all Chrome policies carefully |
| Performance issues | Low | Lazy load details, minimize DOM operations |

---

## Future Enhancements (Post-MVP)
- Dark mode support
- Firefox extension port
- Watchlist feature
- Price alerts
- Search history
- Customizable keyboard shortcut
- Multiple language support
