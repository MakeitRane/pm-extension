"""
Kalshi WebSocket Client
Handles real-time price updates via WebSocket with RSA-PSS authentication
"""

import asyncio
import json
import time
import base64
from typing import Optional, Dict, List
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

try:
    import websockets
except ImportError:
    websockets = None


class KalshiWebSocketClient:
    """
    WebSocket client for Kalshi real-time price updates.

    Usage:
        client = KalshiWebSocketClient(api_key_id, private_key_pem)
        await client.connect()
        await client.subscribe(['ticker'], ['MARKET-TICKER-1', 'MARKET-TICKER-2'])
        await client.listen_for_updates(timeout=3.0)
        prices = client.get_updated_prices()
        await client.disconnect()
    """

    WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
    DEMO_WS_URL = "wss://demo-api.kalshi.co/trade-api/ws/v2"

    def __init__(self, api_key_id: str, private_key_pem: str, use_demo: bool = False):
        """
        Initialize WebSocket client.

        Args:
            api_key_id: Kalshi API key ID
            private_key_pem: RSA private key in PEM format
            use_demo: Use demo environment instead of production
        """
        self.api_key_id = api_key_id
        self.private_key = self._load_private_key(private_key_pem)
        self.ws_url = self.DEMO_WS_URL if use_demo else self.WS_URL
        self.ws = None
        self.market_prices: Dict[str, Dict] = {}
        self.subscribed = False
        self._message_id = 0

    def _load_private_key(self, pem_content: str):
        """
        Load RSA private key from PEM content.

        Handles both PKCS#1 (BEGIN RSA PRIVATE KEY) and PKCS#8 (BEGIN PRIVATE KEY)
        formats, even when the PEM header doesn't match the actual key encoding.

        Args:
            pem_content: Private key in PEM format

        Returns:
            RSA private key object
        """
        if not pem_content:
            return None

        # Handle newlines that might be escaped in .env
        pem_content = pem_content.replace('\\n', '\n').strip()

        # First, try loading as-is
        try:
            return serialization.load_pem_private_key(
                pem_content.encode(),
                password=None,
                backend=default_backend()
            )
        except Exception:
            pass

        # If that failed, the PEM header may not match the key format.
        # Extract the base64 data and try re-wrapping with both PKCS#1 and PKCS#8 headers.
        lines = pem_content.strip().split('\n')
        base64_lines = [line.strip() for line in lines if not line.strip().startswith('-----')]
        base64_data = '\n'.join(base64_lines)

        pem_formats = [
            ('-----BEGIN RSA PRIVATE KEY-----', '-----END RSA PRIVATE KEY-----'),
            ('-----BEGIN PRIVATE KEY-----', '-----END PRIVATE KEY-----'),
        ]

        for header, footer in pem_formats:
            try:
                pem = f"{header}\n{base64_data}\n{footer}"
                return serialization.load_pem_private_key(
                    pem.encode(),
                    password=None,
                    backend=default_backend()
                )
            except Exception:
                continue

        print("Error loading private key: could not parse key in any supported PEM format")
        print("  Ensure RSA_KEY in .env is a valid PEM-encoded RSA private key")
        print("  PKCS#1 keys use: BEGIN RSA PRIVATE KEY / END RSA PRIVATE KEY")
        print("  PKCS#8 keys use: BEGIN PRIVATE KEY / END PRIVATE KEY")
        return None

    def _next_message_id(self) -> int:
        """Get next message ID for WebSocket commands."""
        self._message_id += 1
        return self._message_id

    def _generate_auth_headers(self) -> Dict[str, str]:
        """
        Generate RSA-PSS signed authentication headers.

        Returns:
            Dict with KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE, KALSHI-ACCESS-TIMESTAMP
        """
        if not self.private_key:
            raise ValueError("Private key not loaded")

        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}GET/trade-api/ws/v2"

        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
            "KALSHI-ACCESS-TIMESTAMP": timestamp
        }

    async def connect(self) -> bool:
        """
        Establish authenticated WebSocket connection.

        Returns:
            True if connection successful, False otherwise
        """
        if websockets is None:
            print("websockets library not installed")
            return False

        if not self.private_key:
            print("Private key not available for WebSocket authentication")
            return False

        try:
            headers = self._generate_auth_headers()
            # websockets v13+ renamed extra_headers to additional_headers
            try:
                self.ws = await websockets.connect(
                    self.ws_url,
                    additional_headers=headers,
                    ping_interval=20,
                    ping_timeout=10
                )
            except TypeError:
                self.ws = await websockets.connect(
                    self.ws_url,
                    extra_headers=headers,
                    ping_interval=20,
                    ping_timeout=10
                )
            print(f"WebSocket connected to {self.ws_url}")
            return True
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            self.ws = None
            return False

    async def subscribe(self, channels: List[str], market_tickers: Optional[List[str]] = None) -> bool:
        """
        Subscribe to channels for specified markets.

        Args:
            channels: List of channels (e.g., ['ticker', 'market_lifecycle_v2'])
            market_tickers: Optional list of market tickers to subscribe to

        Returns:
            True if subscription successful
        """
        if not self.ws:
            print("WebSocket not connected")
            return False

        msg = {
            "id": self._next_message_id(),
            "cmd": "subscribe",
            "params": {
                "channels": channels
            }
        }

        if market_tickers:
            msg["params"]["market_tickers"] = market_tickers

        try:
            await self.ws.send(json.dumps(msg))

            # Wait for subscription confirmation
            response = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
            data = json.loads(response)

            if data.get("type") == "subscribed":
                self.subscribed = True
                print(f"Subscribed to channels: {channels}")
                return True
            elif data.get("type") == "error":
                print(f"Subscription error: {data}")
                return False
            else:
                # Might be a different message, still consider subscribed
                self.subscribed = True
                self._handle_message(data)
                return True

        except asyncio.TimeoutError:
            print("Subscription timeout")
            return False
        except Exception as e:
            print(f"Subscription failed: {e}")
            return False

    async def listen_for_updates(self, timeout: float = 3.0):
        """
        Listen for price updates for a limited time.

        Args:
            timeout: Maximum time to listen in seconds
        """
        if not self.ws or not self.subscribed:
            return

        try:
            end_time = time.time() + timeout
            while time.time() < end_time:
                remaining = end_time - time.time()
                if remaining <= 0:
                    break

                try:
                    message = await asyncio.wait_for(
                        self.ws.recv(),
                        timeout=min(remaining, 1.0)
                    )
                    data = json.loads(message)
                    self._handle_message(data)
                except asyncio.TimeoutError:
                    continue

        except Exception as e:
            print(f"Error listening for updates: {e}")

    def _handle_message(self, data: Dict):
        """
        Process incoming WebSocket messages.

        Args:
            data: Parsed JSON message
        """
        msg_type = data.get("type")

        if msg_type == "ticker":
            msg = data.get("msg", {})
            ticker = msg.get("market_ticker")
            if ticker:
                self.market_prices[ticker] = {
                    "yes_bid": msg.get("yes_bid"),
                    "yes_ask": msg.get("yes_ask"),
                    "no_bid": msg.get("no_bid"),
                    "no_ask": msg.get("no_ask"),
                    "last_price": msg.get("last_price"),
                    "volume": msg.get("volume"),
                }

        elif msg_type == "market_lifecycle_v2":
            msg = data.get("msg", {})
            ticker = msg.get("market_ticker")
            if ticker:
                # Update market status
                if ticker in self.market_prices:
                    self.market_prices[ticker]["status"] = msg.get("status")
                else:
                    self.market_prices[ticker] = {"status": msg.get("status")}

        elif msg_type == "error":
            error = data.get("msg", {})
            print(f"WebSocket error: code={error.get('code')}, message={error.get('message')}")

        elif msg_type == "subscribed":
            print(f"Subscription confirmed: {data.get('msg', {}).get('channel')}")

        # Ignore other message types (pong, etc.)

    async def disconnect(self):
        """Close WebSocket connection."""
        if self.ws:
            try:
                await self.ws.close()
                print("WebSocket disconnected")
            except Exception as e:
                print(f"Error disconnecting: {e}")
            finally:
                self.ws = None
                self.subscribed = False

    def get_updated_prices(self) -> Dict[str, Dict]:
        """
        Return collected price updates.

        Returns:
            Dict mapping ticker to price data
        """
        return self.market_prices.copy()

    def apply_updates_to_markets(self, markets: List[Dict]) -> List[Dict]:
        """
        Apply collected price updates to market list.

        Args:
            markets: List of market dicts

        Returns:
            Updated market list
        """
        for market in markets:
            ticker = market.get('ticker')
            if ticker and ticker in self.market_prices:
                updates = self.market_prices[ticker]
                for key, value in updates.items():
                    if value is not None:
                        market[key] = value
        return markets


async def update_markets_with_realtime_prices(
    markets: List[Dict],
    api_key_id: str,
    private_key_pem: str,
    timeout: float = 3.0
) -> List[Dict]:
    """
    Convenience function to update market prices via WebSocket.

    Args:
        markets: List of market dicts to update
        api_key_id: Kalshi API key ID
        private_key_pem: RSA private key PEM content
        timeout: How long to listen for updates

    Returns:
        Updated market list
    """
    if not api_key_id or not private_key_pem:
        print("WebSocket auth not configured, skipping real-time updates")
        return markets

    if not markets:
        return markets

    client = KalshiWebSocketClient(api_key_id, private_key_pem)

    try:
        connected = await client.connect()
        if not connected:
            return markets

        # Get tickers from markets
        tickers = [m.get('ticker') for m in markets if m.get('ticker')]
        if not tickers:
            return markets

        # Subscribe to ticker updates
        subscribed = await client.subscribe(['ticker'], tickers)
        if not subscribed:
            return markets

        # Listen for updates
        await client.listen_for_updates(timeout)

        # Apply updates
        return client.apply_updates_to_markets(markets)

    except Exception as e:
        print(f"Error updating prices via WebSocket: {e}")
        return markets

    finally:
        await client.disconnect()
