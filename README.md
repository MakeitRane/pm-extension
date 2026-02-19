# Kalshi Markets Finder

Trade on your edge in the moment.

A Chrome extension that lets you highlight any text on a webpage and instantly discover related [Kalshi](https://kalshi.com) prediction markets using **AI-powered causal analysis** with Google Gemini.

## Features

- **Causal Market Search**: Two-stage AI pipeline identifies markets with genuine causal relationships to your highlighted text, not just keyword overlap
- **Highlight to Search**: Select any text and press `Cmd+Shift+K` (Mac) or `Ctrl+Shift+K` (Windows)
- **Context Menu**: Right-click selected text and choose "Find Markets on Kalshi"
- **Quick Preview**: See top 5 relevant markets with live prices and AI-generated explanations
- **Detailed View**: Click a market to see full stats, price chart, and trading volume
- **Trade Integration**: One-click to open any market on Kalshi

## Architecture

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│  Chrome          │     │  Python Backend      │     │  Kalshi API     │
│  Extension       │────>│  (Flask + Gemini AI) │────>│  (REST + WS)   │
│  (Manifest V3)   │     │  localhost:5001      │     │                 │
└─────────────────┘     └─────────────────────┘     └─────────────────┘
                               │
                     ┌─────────┴─────────┐
                     │  Google Gemini AI  │
                     │  (2-Stage Search)  │
                     └───────────────────┘

Stage 1: gemini-3-flash-preview  →  Filters all markets to top 50 candidates
Stage 2: gemma-3-27b-it          →  Causal analysis to find top 5 matches
```

### How Search Works

1. User highlights text on a webpage and triggers a search
2. The backend fetches all open markets from Kalshi's API
3. **Stage 1** (gemini-3-flash-preview): Filters the full market list down to ~50 relevant candidates using high-context analysis
4. **Stage 2** (gemma-3-27b-it): Performs causal reasoning on the 50 candidates to identify markets with direct or indirect causal links
5. The top 5 markets with explanations are returned to the extension popup

## Prerequisites

- **Python 3.8+**
- **Google Chrome**
- **Google Gemini API keys** (2 keys required - free tier works)

## API Keys

### Google Gemini API Keys (Required)

Two separate Gemini API keys are needed because the two-stage pipeline uses different models with independent rate limits:

| Key | Model | Purpose | Rate Limits (Free Tier) |
|-----|-------|---------|------------------------|
| `GEMINI_API_KEY_1` | gemini-3-flash-preview | Stage 1: Relevance filtering | 4 RPM, 250k TPM, 18 RPD |
| `GEMINI_API_KEY_2` | gemma-3-27b-it | Stage 2: Causal analysis | 28 RPM, 14k TPM, 14k RPD |

To get your keys:
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create two API keys (you can use the same Google account)
3. Add both to `backend/.env`

### Kalshi API Key (Optional)

A Kalshi API key enables real-time WebSocket price updates. Without it, the extension uses REST API prices.

1. Go to [Kalshi API Settings](https://kalshi.com/account/api)
2. Generate an API key
3. You can add it via the extension popup (click the extension icon) or in `backend/.env`

### RSA Private Key (Optional)

Required only for WebSocket authentication (real-time price streaming). Generate one from your [Kalshi API settings](https://kalshi.com/account/api).

## Installation

### 1. Set Up the Backend

```bash
# Navigate to the backend directory
cd backend

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and add your Gemini API keys (see API Keys section above)
```

### 2. Start the Backend

```bash
cd backend
source venv/bin/activate
python app.py
```

You should see:
```
KALSHI MARKETS FINDER - BACKEND API
============================================================
  Server: http://localhost:5001

  Configuration:
    GEMINI_API_KEY_1 (Stage 1 - Flash): ✓ Configured
    GEMINI_API_KEY_2 (Stage 2 - Gemma): ✓ Configured
    Kalshi API Key: ✗ Not set (optional)
    RSA Key (WebSocket): ✗ Not set (optional)
```

### 3. Load the Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top right)
3. Click **Load unpacked**
4. Select the `pm-extension` folder (the project root)
5. The extension icon should appear in your toolbar

### 4. Configure Kalshi API Key (Optional)

1. Click the extension icon in the Chrome toolbar
2. Enter your Kalshi API key
3. Click "Save API Key"

You can skip this step and use the extension in "free mode" without an API key.

## Usage

**Important**: The Python backend must be running before using the extension.

1. **Start the backend**: `cd backend && source venv/bin/activate && python app.py`
2. **Highlight text** on any webpage (news article, social media post, etc.)
3. **Trigger search** using one of:
   - Press `Cmd+Shift+K` (Mac) or `Ctrl+Shift+K` (Windows)
   - Right-click and select "Find Markets on Kalshi"
4. **Browse results** - markets are ranked by causal relevance with AI explanations
5. **Click a market** to see detailed stats and a price chart
6. **Click "Trade on Kalshi"** to open the market directly on kalshi.com

## Project Structure

```
pm-extension/
├── manifest.json                 # Chrome Extension manifest (V3)
├── backend/
│   ├── app.py                    # Flask server and API endpoints
│   ├── gemini_service.py         # Two-stage Gemini AI pipeline
│   ├── kalshi_service.py         # Kalshi API integration and market search
│   ├── kalshi_ws.py              # WebSocket client for real-time prices
│   ├── .env.example              # Environment variable template
│   └── requirements.txt          # Python dependencies
├── src/
│   ├── background/
│   │   └── service-worker.js     # Extension lifecycle and message routing
│   ├── content/
│   │   ├── content.js            # Popup UI, market rendering, and interactions
│   │   └── content.css           # Popup and overlay styling
│   ├── popup/
│   │   ├── popup.html            # Extension toolbar popup (settings)
│   │   ├── popup.js              # API key management logic
│   │   └── popup.css             # Settings popup styling
│   └── services/
│       ├── kalshi-api.js          # API client for backend and Kalshi
│       └── storage.js             # Chrome storage abstraction
├── assets/
│   └── icons/                     # Extension icons (16, 32, 48, 128px)
└── docs/
    └── PRD.md                     # Product Requirements Document
```

## API Endpoints (Backend)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check with Gemini configuration and rate limit status |
| `/api/rate-limits` | GET | Current rate limit usage for both Gemini stages |
| `/api/search` | POST | Search markets by highlighted text (requires both Gemini keys) |
| `/api/market/:ticker` | GET | Get detailed info for a specific market |
| `/api/refresh` | POST | Force refresh the market cache |

## Troubleshooting

### "Search backend is not running"
- Make sure the Python backend is running: `cd backend && python app.py`
- Verify it's running on port 5001 (check for port conflicts)

### "Gemini API keys not fully configured"
- Ensure both `GEMINI_API_KEY_1` and `GEMINI_API_KEY_2` are set in `backend/.env`
- Verify the keys are valid at [Google AI Studio](https://aistudio.google.com/app/apikey)

### "Gemini API rate limit exceeded"
- The free tier has limited requests per minute/day
- Wait a moment and try again, or use a different API key

### Backend won't start
- Make sure Python 3.8+ is installed: `python3 --version`
- Try creating a fresh virtual environment
- Check that all dependencies installed: `pip install -r requirements.txt`

### Extension not loading
- Make sure all icon files exist in `assets/icons/`
- Check Chrome's extension error console for details

### Markets not loading
- Check the backend terminal for error messages
- The Kalshi API may be temporarily unavailable

## Development

### Modifying the extension
1. Make changes to files in `src/`
2. Go to `chrome://extensions/`
3. Click the refresh icon on the extension card
4. Test your changes

### Modifying the backend
1. Make changes to files in `backend/`
2. The Flask server auto-reloads in debug mode
3. Or restart manually: `python app.py`

## License

MIT - see [LICENSE](LICENSE) for details.
