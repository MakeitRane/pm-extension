# Kalshi Markets Finder - Codebase Documentation

## Project Overview

**Kalshi Markets Finder** is a Chrome extension that enables users to highlight text on any webpage and instantly discover related Kalshi prediction markets using semantic search powered by AI.

### Tech Stack
- **Frontend:** Vanilla JavaScript (ES6+), Chrome Extension Manifest V3, HTML5, CSS3
- **Backend:** Python 3.8+, Flask, Sentence Transformers (all-mpnet-base-v2)
- **AI/ML:** Sentence Transformers for embeddings, Google Gemini API for causal analysis
- **APIs:** Kalshi REST API, Kalshi WebSocket API
- **Authentication:** RSA-PSS for WebSocket, Bearer tokens for REST APIs
- **Storage:** Chrome's sync storage for encrypted data

---

## File Structure & Purposes

```
pm-extension/
├── manifest.json                    # Chrome Extension manifest (V3)
├── README.md                        # Project documentation
├── Claude.md                        # This file - codebase understanding
├── assets/
│   ├── generate-icons.html          # Icon generation tool
│   └── icons/                       # Extension icons (16, 32, 48, 128px)
├── docs/
│   ├── PRD.md                       # Product Requirements Document
│   └── IMPLEMENTATION_PLAN.md       # Implementation roadmap
├── src/
│   ├── background/
│   │   └── service-worker.js        # Extension lifecycle & message routing
│   ├── content/
│   │   ├── content.js               # Main popup UI and interactions
│   │   └── content.css              # Popup styling
│   ├── popup/
│   │   ├── popup.html               # Extension icon popup UI
│   │   ├── popup.js                 # API key management
│   │   └── popup.css                # Settings popup styling
│   ├── services/
│   │   ├── kalshi-api.js            # Kalshi API wrapper and market search
│   │   └── storage.js               # Chrome storage abstraction
│   └── styles/
│       └── variables.css            # Design system CSS variables
└── backend/
    ├── app.py                       # Flask server and API endpoints
    ├── embedding_service.py         # Sentence Transformers wrapper
    ├── kalshi_service.py            # Market fetching and semantic search
    ├── gemini_service.py            # Google Gemini causal analysis
    ├── kalshi_ws.py                 # WebSocket client for real-time prices
    ├── .env                         # Environment variables (API keys)
    └── requirements.txt             # Python dependencies
```

---

## Detailed File Documentation

### Frontend Layer

#### `manifest.json`
**Purpose:** Chrome Extension Manifest V3 configuration

**Key Configurations:**
- Permissions: `activeTab`, `storage`, `contextMenus`
- Host permissions for Kalshi APIs (`*.kalshi.com`) and local backend (`localhost:5001`)
- Registers service worker, content scripts, and popup UI
- Keyboard shortcut: `Cmd+Shift+K` (Mac) / `Ctrl+Shift+K` (Windows)

**Relationships:**
- → References `src/background/service-worker.js` as background script
- → References `src/content/content.js` and `content.css` as content scripts
- → References `src/popup/popup.html` as default popup

---

#### `src/background/service-worker.js`
**Purpose:** Extension lifecycle management and central message routing hub

**Key Responsibilities:**
- Creates context menu item "Find Markets on Kalshi" on install
- Listens for context menu clicks and keyboard shortcuts
- Routes messages between content script and backend
- Handles API calls: search, market details, candlesticks, API key validation

**Key Functions:**
- `triggerSearch()` - Initiates market search from selected text
- `handleMessage()` - Routes messages and manages async responses

**Relationships:**
- ← Registered by `manifest.json`
- → Communicates with `content.js` via `chrome.tabs.sendMessage()`
- → Calls `kalshi-api.js` functions for backend communication
- → Uses `storage.js` for user state (authentication, first-use status)

**Message Types Handled:**
```javascript
GET_USER_STATE       // → Returns { userMode, isFirstUse }
SEARCH_MARKETS       // → Calls searchMarketsWithBackend()
GET_MARKET_DETAILS   // → Calls getMarketDetails()
GET_CANDLESTICKS     // → Calls getCandlesticks()
VALIDATE_API_KEY     // → Calls validateApiKey()
```

---

#### `src/content/content.js`
**Purpose:** Injects popup UI into webpages and manages all user interactions

**Key Responsibilities:**
- Captures selected text from webpage
- Calculates optimal popup positioning (respects viewport bounds)
- Renders market results popup overlay
- Handles user interactions (clicks, key presses)
- Manages modal states: list view, details view, loading, errors, API key modal
- Renders price charts using Canvas API

**State Management:**
```javascript
currentMarkets    // Array of search results
selectedMarket    // Currently expanded market
marketDetails     // Full details for selected market
userMode          // 'authenticated' | 'free' | 'new'
currentView       // 'list' | 'details' | 'loading' | 'error' | 'apikey'
```

**Key Functions:**
- `renderMarketList()` - Displays top 5 search results with prices
- `renderMarketDetails()` - Expanded view with stats and chart
- `renderMiniChart()` - Draws price history using Canvas API
- `showApiKeyModal()` - First-time user API key input
- `calculatePopupPosition()` - Smart positioning relative to selection

**Relationships:**
- ← Injected by `manifest.json` into all web pages
- ← Receives messages from `service-worker.js`
- → Sends messages to `service-worker.js` for API calls
- → Uses styles from `content.css`

---

#### `src/content/content.css`
**Purpose:** Styling for injected content script popup

**Design Patterns:**
- Scoped CSS with `kalshi-*` class prefix (avoids conflicts with host page)
- High z-index (2147483647) for overlay layering
- Smooth animations: fade-in (150ms), spinner rotation (0.8s)

**Key Components:**
| Class | Purpose |
|-------|---------|
| `.kalshi-popup` | Main result container (360px width, 480px max height) |
| `.kalshi-market-card` | Individual market result item |
| `.kalshi-price-pill` | Price badges (Yes: green, No: gray) |
| `.kalshi-market-details` | Expanded detail view |
| `.kalshi-modal-overlay` | Full-screen modal backdrop |
| `.kalshi-chart-container` | Canvas chart area |

**Relationships:**
- ← Referenced by `manifest.json` as content script CSS
- → Provides styling for elements created by `content.js`

---

#### `src/popup/popup.html`
**Purpose:** Extension icon popup for API key management

**Structure:**
- Header with logo and title
- Status section (connected/disconnected indicator)
- API key input and action buttons
- Usage instructions
- Footer with Kalshi link and version

**Relationships:**
- ← Registered in `manifest.json` as default popup
- → Uses `popup.js` for logic
- → Uses `popup.css` for styling

---

#### `src/popup/popup.js`
**Purpose:** API key management logic in the settings popup

**Key Responsibilities:**
- Load stored API key and user state from Chrome storage
- Display appropriate UI based on authentication status
- Validate API keys before saving (calls Kalshi API)
- Handle save/update/remove operations
- Show success/error feedback messages

**Key Functions:**
- `handleSave()` - Validate and save new API key
- `handleUpdate()` - Update existing API key with validation
- `handleRemove()` - Delete stored API key with confirmation
- `render()` - Update UI based on current state

**Relationships:**
- ← Used by `popup.html`
- → Uses `storage.js` for API key persistence
- → Uses `kalshi-api.js` for key validation

---

#### `src/services/kalshi-api.js`
**Purpose:** Abstraction layer for all Kalshi API communication

**Key Responsibilities:**
- Backend request handling via `backendRequest()`
- Direct Kalshi API calls via `kalshiRequest()`
- Market search with semantic filtering
- Market detail fetching
- Candlestick data retrieval for charts
- API key validation
- Backend health checks

**API Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/search` | Semantic market search (via backend) |
| GET | `/api/market/:ticker` | Market details (backend or direct) |
| POST | `/api/embed` | Text embedding (backend) |
| GET | `/candlesticks` | Price history (direct Kalshi API) |

**Error Categories:**
```javascript
INVALID_API_KEY      // 401/403 responses
NETWORK_ERROR        // Connection failures
RATE_LIMITED         // 429 responses
SERVER_ERROR         // 500+ responses
BACKEND_UNAVAILABLE  // Backend not running
```

**Relationships:**
- ← Called by `service-worker.js` and `popup.js`
- → Communicates with Python backend (`localhost:5001`)
- → Communicates with Kalshi API (`api.elections.kalshi.com`)
- → Uses `storage.js` for API key retrieval

---

#### `src/services/storage.js`
**Purpose:** Chrome storage API abstraction

**Key Responsibilities:**
- Get/set/remove API keys securely
- Manage user modes: `authenticated`, `free`, `new`
- Track first-use completion
- State queries: `isAuthenticated()`, `getUserMode()`

**Storage Keys:**
```javascript
STORAGE_KEYS = {
  API_KEY: 'kalshi_api_key',
  USER_MODE: 'user_mode',
  FIRST_USE: 'first_use_completed'
}
```

**Relationships:**
- ← Used by `service-worker.js`, `popup.js`, `kalshi-api.js`
- → Uses Chrome's `chrome.storage.sync` API

---

#### `src/styles/variables.css`
**Purpose:** Design system and theme variables

**Contents:**
- Color palette (Kalshi green `#0AC285` primary)
- Spacing scale (4px to 32px)
- Typography (font family, sizes, weights)
- Shadows (sm to xl)
- Border radius scale
- Transitions and z-index values

**Relationships:**
- → Imported by CSS files for consistent theming

---

### Backend Layer

#### `backend/app.py`
**Purpose:** Main Flask server and API endpoint definitions

**Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check endpoint |
| POST | `/api/embed` | Get text embedding with metadata |
| POST | `/api/search` | Semantic search for markets (main endpoint) |
| GET | `/api/market/:ticker` | Fetch specific market details |
| POST | `/api/refresh` | Force refresh market cache |

**Configuration:**
- Default port: 5001
- CORS enabled for Chrome extensions and localhost
- Lazy service initialization
- Pre-initializes embedding model on startup

**Relationships:**
- → Uses `embedding_service.py` for text embeddings
- → Uses `kalshi_service.py` for market search
- → Uses `gemini_service.py` for causal analysis (optional)
- ← Called by `kalshi-api.js` from frontend

---

#### `backend/embedding_service.py`
**Purpose:** Text embedding using Sentence Transformers

**Model:** `all-mpnet-base-v2`
- 768-dimensional embeddings
- ~420MB model size
- Pre-trained on large text corpora

**Key Functions:**
- `get_embedding(text)` - Single text embedding (normalized)
- `get_embeddings_batch(texts)` - Efficient batch encoding
- `cosine_similarity(emb1, emb2)` - Calculate vector similarity
- `find_similar(query_emb, embeddings, top_k)` - Ranking and retrieval

**Design Pattern:** Singleton with lazy initialization

**Relationships:**
- ← Used by `app.py` for `/api/embed` endpoint
- ← Used by `kalshi_service.py` for market embeddings

---

#### `backend/kalshi_service.py`
**Purpose:** Core market search and Kalshi API integration

**Key Responsibilities:**
- Fetch open markets from Kalshi API
- Compute embeddings for market titles/descriptions
- Perform semantic similarity ranking
- Causal analysis integration with Gemini
- Market URL construction
- Price fetching via WebSocket (when authenticated)
- Caching for performance (5-minute TTL)

**Search Methods:**
1. `search_markets_gemini()` - Two-stage causal analysis
   - Pre-filter: Top 50 candidates via semantic search
   - Causal analysis: Gemini identifies true causal relationships

2. `_search_markets_semantic()` - Pure semantic search
   - Fetch all open markets
   - Batch embed market titles
   - Rank by cosine similarity
   - Deduplicate by event ticker

**Caching:**
```python
_market_list_cache    # Open markets (5 min TTL)
_market_cache         # Markets with embeddings
_event_cache          # Event details (permanent)
_series_cache         # Series details (permanent)
```

**URL Construction:**
Format: `https://kalshi.com/markets/{series_ticker}/{series_slug}/{event_ticker}`

**Relationships:**
- ← Used by `app.py` for search endpoints
- → Uses `embedding_service.py` for embeddings
- → Uses `gemini_service.py` for causal analysis
- → Uses `kalshi_ws.py` for real-time prices
- → Calls Kalshi REST API

---

#### `backend/gemini_service.py`
**Purpose:** Google Gemini API integration for causal market analysis

**Two-Stage Filtering:**
1. Semantic pre-filtering (top 50 candidates)
2. Gemini LLM analyzes causal relationships

**Causal Relationship Types:**
- **1-step (direct):** "Player injured" → "Team loses game"
- **2-step (indirect):** "Player injured" → "Team misses playoffs"
- **Excluded:** Tangential overlaps, weak correlations

**Causal Strength Labels:**
- `strong` - Direct 1-step causal link
- `moderate` - Clear 2-step causal chain
- `weak` - Excluded (too tenuous)

**Model:** `gemma-3-27b-it` (free tier, 128K context)

**Relationships:**
- ← Used by `kalshi_service.py` for enhanced search
- → Calls Google Gemini API

---

#### `backend/kalshi_ws.py`
**Purpose:** WebSocket client for real-time market price updates

**Features:**
- RSA-PSS authentication for WebSocket connections
- Subscription to ticker price updates
- Real-time price collection and market update
- Async/await pattern for concurrent updates
- Timeout handling (3 second default)

**WebSocket Endpoints:**
- Production: `wss://api.elections.kalshi.com/trade-api/ws/v2`
- Demo: `wss://demo-api.kalshi.co/trade-api/ws/v2`

**Message Types:**
- `ticker` - Price updates (yes_bid, yes_ask, no_bid, no_ask)
- `market_lifecycle_v2` - Market status changes
- `subscribed` - Subscription confirmation

**Relationships:**
- ← Used by `kalshi_service.py` for live prices
- → Connects to Kalshi WebSocket API

---

## Data Flow & Architecture

### Complete User Journey

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER ACTION                               │
│              (Selects text + Cmd+Shift+K or right-click)        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONTENT SCRIPT (content.js)                   │
│                   Captures selected text                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│               SERVICE WORKER (service-worker.js)                 │
│                    Routes search request                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   KALSHI API SERVICE (kalshi-api.js)             │
│                   Sends request to backend                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FLASK BACKEND (app.py)                       │
│                    Receives /api/search                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ embedding_service │ │  kalshi_service  │ │  gemini_service  │
│ (generate query   │ │ (fetch markets,  │ │ (causal analysis │
│  embedding)       │ │  compute scores) │ │  - optional)     │
└──────────────────┘ └──────────────────┘ └──────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      KALSHI API                                  │
│              (REST for markets, WS for prices)                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RESULTS RETURNED                               │
│                  (Top 5 markets with prices)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONTENT SCRIPT                                │
│                  Renders popup with results                      │
└─────────────────────────────────────────────────────────────────┘
```

### Message Passing Protocol

**Content Script ↔ Background Service Worker:**
```javascript
// Trigger search
{ type: 'GET_SELECTION_AND_SEARCH' }

// Show popup with results
{ type: 'SHOW_POPUP', payload: { query, isFirstUse, userMode } }

// Request market search
{ type: 'SEARCH_MARKETS', payload: { query, limit: 5 } }

// Get market details
{ type: 'GET_MARKET_DETAILS', payload: { ticker } }

// Validate API key
{ type: 'VALIDATE_API_KEY', payload: { apiKey } }
```

---

## File Relationship Diagram

```
                        manifest.json
                             │
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    service-worker.js    content.js       popup.html
           │                 │                 │
           │                 ▼                 ▼
           │           content.css        popup.js
           │                               popup.css
           │                                   │
           └───────────┬───────────────────────┘
                       ▼
              ┌────────────────┐
              │  kalshi-api.js │◄──────────────────────┐
              └────────────────┘                       │
                       │                               │
                       ▼                               │
              ┌────────────────┐                       │
              │   storage.js   │                       │
              └────────────────┘                       │
                                                       │
    ═══════════════════════════════════════════════════│═══════
                    BACKEND (Python)                   │
    ═══════════════════════════════════════════════════│═══════
                                                       │
              ┌────────────────┐                       │
              │     app.py     │◄──────────────────────┘
              └────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ embedding_  │ │  kalshi_    │ │  gemini_    │
│ service.py  │ │  service.py │ │  service.py │
└─────────────┘ └─────────────┘ └─────────────┘
         │             │             │
         └─────────────┼─────────────┘
                       ▼
              ┌────────────────┐
              │  kalshi_ws.py  │
              └────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │  Kalshi APIs   │
              │ (REST + WS)    │
              └────────────────┘
```

---

## Caching Architecture

### Client-Side (Chrome Storage)
```
chrome.storage.sync
├── kalshi_api_key        # Encrypted by Chrome
├── user_mode             # 'authenticated' | 'free' | 'new'
└── first_use_completed   # boolean
```

### Backend (Python Memory)
```
In-Memory Caches
├── _market_list_cache    # Open markets (5 min TTL)
├── _market_cache         # Markets with pre-computed embeddings
├── _event_cache          # Event details (permanent)
├── _series_cache         # Series details (permanent)
└── _message_id           # WebSocket message counter
```

---

## Authentication Modes

| Mode | Features | Storage |
|------|----------|---------|
| `new` | First-time user, shown API key modal | No API key stored |
| `free` | View markets, no trade button | `user_mode: 'free'` |
| `authenticated` | Full access, real-time prices | API key + `user_mode: 'authenticated'` |

---

## Key Implementation Details

### Semantic Search Algorithm
1. User query → 768-dim embedding via Sentence Transformers
2. Fetch all open markets from Kalshi API
3. Batch encode market titles → embeddings
4. Compute cosine similarity between query and each market
5. Sort by similarity score
6. Deduplicate by event ticker (keep highest score)
7. Return top 5 results

### Causal Analysis (Optional Gemini)
1. Pre-filter: Top 50 candidates via semantic search
2. Send to Gemini with causal analysis prompt
3. Gemini identifies 1-step and 2-step causal links
4. Parse JSON response with ticker, strength, reasoning
5. Filter to strong/moderate matches
6. Return top 5 with reasoning

### Market URL Construction
```
https://kalshi.com/markets/{series_ticker}/{series_slug}/{event_ticker}

Example:
https://kalshi.com/markets/kxsuperbowl/super-bowl-winner/KXSUPERBOWL-25-KC
```

---

## Error Handling

| Error Code | Meaning | User Message |
|------------|---------|--------------|
| `INVALID_API_KEY` | 401/403 from API | "Invalid API key. Please check your key in settings." |
| `NETWORK_ERROR` | Connection failed | "Unable to connect. Please check your internet connection." |
| `RATE_LIMITED` | 429 from API | "Too many requests. Please wait a moment and try again." |
| `SERVER_ERROR` | 500+ from API | "Kalshi servers are experiencing issues. Please try again later." |
| `BACKEND_UNAVAILABLE` | Backend not running | "Search backend is not running. Please start the Python server." |

---

## Environment Variables

### Backend (.env)
```bash
KALSHI_API_KEY=        # Optional: For WebSocket auth
KALSHI_KEY_ID=         # Optional: For WebSocket auth
RSA_KEY=               # Optional: RSA private key for WS auth
GEMINI_API_KEY=        # Optional: For causal analysis
PORT=5001              # Server port
```

---

## Running the Project

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Extension
1. Open Chrome → `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `pm-extension` folder

### Usage
1. Highlight any text on a webpage
2. Press `Cmd+Shift+K` (Mac) or `Ctrl+Shift+K` (Windows)
3. Or right-click → "Find Markets on Kalshi"
4. View matching prediction markets in popup
5. Click a market to see details and price chart
6. Click "Trade on Kalshi" to open on Kalshi.com

---

## Architecture Patterns

1. **Service-Oriented Architecture** - Clear separation between background service, content script, and services
2. **Message-Driven Communication** - Chrome extension components communicate via structured messages
3. **Lazy Loading & Singleton** - Embedding model loaded once on first request
4. **Graceful Degradation** - Falls back to semantic search if Gemini unavailable
5. **Multi-Layer Caching** - Client-side (Chrome storage) + server-side (memory caches)

---

*Last updated: 2026-02-01*
