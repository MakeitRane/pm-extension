# Product Requirements Document: Kalshi Markets Finder

## Overview

**Product Name:** Kalshi Markets Finder
**Platform:** Google Chrome Extension
**Version:** 1.0 (MVP)

### Problem Statement
Existing Kalshi users who infrequently trade often encounter news, articles, or content that relates to prediction markets but lack a seamless way to discover relevant Kalshi markets without leaving their current context.

### Solution
A Chrome extension that allows users to highlight any text on a webpage and instantly discover related Kalshi prediction markets, providing a frictionless path from content consumption to market discovery and trading.

### Target Users
- Existing Kalshi users who trade infrequently
- Users who consume news, research, and content online
- Users seeking to quickly check prediction market odds on topics they're reading about

---

## Functional Requirements

### 1. Trigger Mechanisms

| Trigger | Implementation |
|---------|----------------|
| Keyboard Shortcut | `Ctrl+K` (Windows/Linux) / `Cmd+K` (Mac) |
| Context Menu | Right-click → "Find Markets on Kalshi" |

**Behavior:**
- Both triggers capture the currently highlighted/selected text on the page
- If no text is selected, show a tooltip prompting user to select text first

### 2. Market Search & Display

#### 2.1 Search Results Popup
- **Location:** Floating overlay near the highlighted text
- **Results Count:** Top 5 most relevant markets
- **Initial View (Per Market):**
  - Market title/question
  - Current Yes price (e.g., "Yes: 67¢")
  - Current No price (e.g., "No: 33¢")

#### 2.2 Expanded Market Details
When user clicks on a market card, expand to show:
- All basic info (title, Yes/No prices)
- Trading volume (24h and total)
- Market close/expiration date
- Last trade price and time
- 24-hour price change (%)
- Open interest
- Mini price history chart (sparkline or small candlestick)
- **"Trade on Kalshi" button** → Opens market page on kalshi.com in new tab

#### 2.3 No Results State
- Display message: "No markets found"
- Clean, simple presentation without additional suggestions

### 3. User Authentication Flow

#### 3.1 First-Use Experience
1. User triggers search for the first time
2. Modal appears prompting for Kalshi API key
3. Input field for API key
4. **"Skip for now"** link below input to use as free user
5. "Save" button to store API key

#### 3.2 User Modes

| Mode | Capabilities | Trade Button Behavior |
|------|--------------|----------------------|
| **Free User** | View markets, see prices, view details | Redirects to API key input modal |
| **Authenticated User** | Full access to all features | Opens market on Kalshi in new tab |

#### 3.3 API Key Management
- API key stored locally in Chrome's `chrome.storage.sync`
- Users can update/remove API key via extension popup (click extension icon)
- API key is never sent to any server other than Kalshi's API

### 4. Error Handling

Display specific, user-friendly error messages:

| Error Type | Message |
|------------|---------|
| Invalid API Key | "Invalid API key. Please check your key in settings." |
| Network Error | "Unable to connect. Please check your internet connection." |
| Rate Limited | "Too many requests. Please wait a moment and try again." |
| Server Error | "Kalshi servers are experiencing issues. Please try again later." |
| Unknown Error | "Something went wrong. Please try again." |

---

## Non-Functional Requirements

### 1. Visual Design

#### Color Palette
- **Primary:** Kalshi Green (`#0AC285`)
- **Background:** Light theme (white/off-white)
- **Text:** Dark gray (#1a1a1a) for readability
- **Accents:** Green should "pop" and make the extension feel fun and enticing

#### Design Principles
- Modern, clean aesthetic
- Generous whitespace
- Smooth animations/transitions
- Green accents on interactive elements (buttons, price highlights)
- Cards with subtle shadows for depth

### 2. Performance
- Search results should appear within 2 seconds of trigger
- Popup should render smoothly without blocking page interaction
- Minimal memory footprint when idle

### 3. Security
- API keys stored securely in Chrome's encrypted storage
- No tracking or analytics in MVP
- All API calls over HTTPS
- Content Security Policy enforced

### 4. Browser Support
- Google Chrome (version 88+)
- Chromium-based browsers may work but are not officially supported

---

## User Flows

### Flow 1: First-Time User (Free Mode)
```
1. User installs extension
2. User highlights text on any webpage
3. User presses Cmd+K or right-clicks → "Find Markets on Kalshi"
4. API key modal appears
5. User clicks "Skip for now"
6. Search executes, popup shows results
7. User clicks a market → Details expand
8. User clicks "Trade on Kalshi" → API key modal appears again
9. User can enter key or dismiss
```

### Flow 2: Authenticated User
```
1. User has previously saved API key
2. User highlights text on any webpage
3. User presses Cmd+K or right-clicks → "Find Markets on Kalshi"
4. Popup appears with top 5 markets
5. User clicks a market → Details expand with full stats + chart
6. User clicks "Trade on Kalshi" → Opens kalshi.com market page in new tab
```

### Flow 3: No Results
```
1. User highlights obscure/unrelated text
2. User triggers search
3. Popup appears with "No markets found" message
4. User dismisses popup or selects different text
```

---

## Technical Architecture

### Components
1. **Manifest (manifest.json)** - Extension configuration, permissions, shortcuts
2. **Background Service Worker** - Handles context menu, keyboard shortcuts, API calls
3. **Content Script** - Injected into pages, captures selection, renders popup
4. **Popup UI** - Extension icon popup for settings/API key management
5. **Styles** - CSS for popup overlay and components

### API Integration
- **Base URL:** `https://api.elections.kalshi.com/trade-api/v2`
- **Primary Endpoint:** `GET /markets` - Fetch markets, filter client-side by query relevance
- **Authentication:** Bearer token (API key) in Authorization header
- **Rate Limits:** 20 reads/sec, 10 writes/sec
- **Secondary Endpoints:**
  - `GET /markets/{ticker}` - Individual market details
  - `GET /markets/{ticker}/candlesticks` - Price history for chart
- **SDK Available:** https://docs.kalshi.com/typescript-sdk/api/MarketsApi

### Data Flow
```
User Selection → Content Script → Background Worker → Kalshi API
                                                          ↓
User ← Content Script (Render Popup) ← Background Worker ←
```

---

## Success Metrics (Future)
- Extension installs
- Daily/weekly active users
- Searches per user per session
- Click-through rate to Kalshi (Trade button clicks)
- Conversion: Free user → API key registration

---

## Out of Scope (v1.0)
- Market watchlist/favorites
- Price alerts/notifications
- In-extension trading (placing bets)
- Firefox/Safari support
- Dark mode
- Customizable result count
- Search history

---

## Open Questions (Resolved)
1. ~~Does Kalshi have brand guidelines for the green color code?~~ → **Resolved:** `#0AC285` (pulled from kalshi.com)
2. ~~Is there a public search/relevance API endpoint?~~ → **Resolved:** Client-side filtering of `getMarkets()` results
3. ~~Rate limits for the Kalshi API?~~ → **Resolved:** 20 reads/sec, 10 writes/sec. TypeScript SDK available.
4. ~~Does Kalshi require approval for third-party extensions?~~ → **Resolved:** No approval required. 

---

## Appendix

### Kalshi API Reference
- Documentation: https://docs.kalshi.com/typescript-sdk/api/MarketsApi
- Key Methods:
  - `getMarkets()` - List/search markets with filters
  - `getMarket(ticker)` - Get single market details
  - `getMarketCandlesticks(ticker)` - Price history data

### Keyboard Shortcut Note
- `Cmd+K` / `Ctrl+K` is commonly used by other tools (Slack, Notion, etc.)
- May need to document potential conflicts or offer customization in future versions
