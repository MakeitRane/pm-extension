# Kalshi Markets Finder

Trade on your edge in the moment.

A Chrome extension that lets you highlight any text on a webpage and instantly discover related Kalshi prediction markets.

## Features

- **Highlight to Search**: Select any text and press `Cmd+Shift+K` (Mac) or `Ctrl+Shift+K` (Windows) to find related markets
- **Context Menu**: Right-click selected text and choose "Find Markets on Kalshi"
- **Quick Preview**: See top 5 relevant markets with Yes/No prices
- **Detailed View**: Click a market to see full stats, price chart, and trading volume
- **Trade Integration**: One-click to open the market on Kalshi

## Installation (Development)

### 1. Create Extension Icons

Before loading the extension, you need to create icon files. Create PNG icons in the following sizes and place them in `assets/icons/`:

- `icon-16.png` (16x16 pixels)
- `icon-32.png` (32x32 pixels)
- `icon-48.png` (48x48 pixels)
- `icon-128.png` (128x128 pixels)

**Quick option**: Use any image editor to create simple green squares with rounded corners, or use this online tool: https://favicon.io/

Recommended icon design:
- Background: Kalshi Green (#0AC285)
- Simple checkmark or "K" logo in white

### 2. Load the Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top right)
3. Click **Load unpacked**
4. Select the `pm-extension` folder
5. The extension should now appear in your toolbar

### 3. Configure Your API Key (Optional)

1. Click the extension icon in the toolbar
2. Enter your Kalshi API key
3. Click "Save API Key"

You can also use the extension without an API key in "free mode" - you'll just be prompted to add one when you try to trade.

## Usage

1. **Highlight text** on any webpage (news article, social media post, etc.)
2. **Trigger search**:
   - Press `Cmd+Shift+K` (Mac) or `Ctrl+Shift+K` (Windows)
   - Or right-click and select "Find Markets on Kalshi"
3. **Browse results** in the popup
4. **Click a market** to see detailed stats and price chart
5. **Click "Trade on Kalshi"** to open the market on kalshi.com

## Project Structure

```
pm-extension/
├── manifest.json              # Chrome extension manifest
├── src/
│   ├── background/
│   │   └── service-worker.js  # Background script (API calls, context menu)
│   ├── content/
│   │   ├── content.js         # Content script (popup UI, selection handling)
│   │   └── content.css        # Popup styles
│   ├── popup/
│   │   ├── popup.html         # Extension icon popup
│   │   ├── popup.js           # Popup logic
│   │   └── popup.css          # Popup styles
│   ├── services/
│   │   ├── storage.js         # Chrome storage wrapper
│   │   └── kalshi-api.js      # Kalshi API client
│   └── styles/
│       └── variables.css      # CSS design system
├── assets/
│   └── icons/                 # Extension icons
└── docs/
    ├── PRD.md                 # Product Requirements Document
    └── IMPLEMENTATION_PLAN.md # Implementation Plan
```

## API Rate Limits

The Kalshi API has the following rate limits:
- **Reads**: 20 requests/second
- **Writes**: 10 requests/second

This extension only performs read operations.

## Keyboard Shortcut Conflicts

The default shortcut `Cmd/Ctrl+Shift+K` was chosen to avoid conflicts with common browser shortcuts. If it conflicts with another extension or application, you can change it:

1. Go to `chrome://extensions/shortcuts`
2. Find "Kalshi Markets Finder"
3. Click the pencil icon next to "Find Kalshi markets for selected text"
4. Press your preferred key combination

## Troubleshooting

### Extension not loading
- Make sure all icon files exist in `assets/icons/`
- Check the Chrome console for errors (`chrome://extensions/` → click "Errors" on the extension card)

### Markets not loading
- Check your internet connection
- Verify your API key is valid (if using authenticated mode)
- The Kalshi API may be temporarily unavailable

### Popup not appearing
- Make sure text is selected before triggering the search
- Try refreshing the page
- Some pages with strict Content Security Policies may block the popup

## Development

To modify the extension:

1. Make changes to the source files
2. Go to `chrome://extensions/`
3. Click the refresh icon on the extension card
4. Test your changes

## License

MIT
