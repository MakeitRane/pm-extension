# Privacy Policy - Kalshi Markets Finder

**Last updated:** February 28, 2026

## Overview

Kalshi Markets Finder is a Chrome extension that helps users discover related prediction markets by highlighting text on webpages. This privacy policy explains what data is collected, how it is used, and how it is stored.

## Data Collection

### Data We Collect

1. **Selected Text**: When you use the extension (via keyboard shortcut or right-click menu), the text you have highlighted on the webpage is sent to our backend server for market search processing.

2. **Kalshi API Key** (optional): If you choose to enter your Kalshi API key for enhanced features, it is stored locally in your browser using Chrome's built-in sync storage.

### Data We Do NOT Collect

- We do not collect your browsing history
- We do not collect personally identifiable information
- We do not track which websites you visit
- We do not collect analytics or usage data
- We do not use cookies

## Data Transmission

When you perform a market search, the highlighted text is:

1. Sent to our backend API server for processing
2. Forwarded to the Google Gemini API for AI-powered market analysis
3. Used to query the Kalshi API for matching prediction markets

All data transmission uses HTTPS encryption.

## Data Storage

- **API Key**: Stored locally in Chrome's sync storage (encrypted by Chrome). Never sent to our servers.
- **User Preferences**: Backend URL and user mode stored locally in Chrome's sync storage.
- **Search Queries**: Not stored. Processed in-memory and discarded after the response is returned.

## Third-Party Services

This extension communicates with:

- **Our Backend Server**: Processes search queries and coordinates AI analysis
- **Google Gemini API**: Analyzes causal relationships between your text and prediction markets
- **Kalshi API**: Retrieves prediction market data and prices

Each of these services has their own privacy policies.

## Data Sharing

We do not sell, trade, or share your data with third parties. Data is only transmitted to the services listed above as necessary to provide the extension's functionality.

## Your Rights

You can:

- Remove your API key at any time via the extension popup
- Clear all stored data by removing the extension
- Use the extension without providing an API key

## Changes to This Policy

We may update this privacy policy from time to time. Changes will be reflected in the "Last updated" date above.

## Contact

For questions about this privacy policy, please open an issue at: https://github.com/MakeitRane/pm-extension/issues
