"""
Binance REST API Integration Module
Cryptocurrency exchange trading and market data
"""

import asyncio
import logging
import aiohttp
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
import hmac
import hashlib
import time
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class BinanceProvider:
    """
    Async Binance REST API client for cryptocurrency trading
    Handles authentication, order placement, and market data
    """

    BASE_URL = "https://api.binance.com"
    TESTNET_URL = "https://testnet.binance.vision"

    def __init__(self,
                 api_key: str,
                 api_secret: str,
                 testnet: bool = True,
                 timeout: int = 30):
        """
        Initialize Binance provider
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet (default: True)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.timeout = timeout
        
        self.base_url = self.TESTNET_URL if testnet else self.BASE_URL
        self.is_connected = False
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info(f"BinanceProvider initialized (testnet={testnet})")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the session"""
        if self._session:
            await self._session.close()
            self._session = None

    async def _generate_signature(self, data: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for request"""
        query_string = urlencode(data)
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(self,
                      method: str,
                      endpoint: str,
                      signed: bool = False,
                      **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request to Binance API
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint
            signed: Whether to sign the request
            **kwargs: Additional parameters
        
        Returns:
            Response JSON
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}{endpoint}"
            
            headers = {
                "X-MBX-APIKEY": self.api_key
            }
            
            params = {}
            params.update(kwargs)
            
            if signed:
                params['timestamp'] = int(time.time() * 1000)
                params['signature'] = await self._generate_signature(params)
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            async with session.request(
                method,
                url,
                params=params,
                headers=headers,
                timeout=timeout
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Binance API error {response.status}: {error_text}")
                    return {'error': error_text, 'status': response.status}
        
        except Exception as e:
            logger.error(f"Binance request failed: {str(e)}")
            return {'error': str(e)}

    async def connect(self) -> bool:
        """Test connection to Binance API"""
        try:
            result = await self._request("GET", "/api/v3/ping")
            self.is_connected = 'error' not in result
            if self.is_connected:
                logger.info("Connected to Binance API")
            return self.is_connected
        except Exception as e:
            logger.error(f"Binance connection failed: {str(e)}")
            return False

    async def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information
        
        Returns:
            Account balances and trading info
        """
        try:
            result = await self._request("GET", "/api/v3/account", signed=True)
            
            if 'error' in result:
                return {'error': result['error']}
            
            balances = {}
            for balance in result.get('balances', []):
                if float(balance['free']) > 0 or float(balance['locked']) > 0:
                    balances[balance['asset']] = {
                        'free': Decimal(balance['free']),
                        'locked': Decimal(balance['locked']),
                        'total': Decimal(balance['free']) + Decimal(balance['locked'])
                    }
            
            return {
                'balances': balances,
                'can_trade': result.get('canTrade', True),
                'can_withdraw': result.get('canWithdraw', True),
                'can_deposit': result.get('canDeposit', True),
                'maker_commission': result.get('makerCommission', 0),
                'taker_commission': result.get('takerCommission', 0),
            }
        
        except Exception as e:
            logger.error(f"Failed to get account info: {str(e)}")
            return {'error': str(e)}

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get 24h market data for a symbol
        
        Args:
            symbol: Trading pair (e.g., BTCUSDT)
        
        Returns:
            Market data with price, volume, change
        """
        try:
            result = await self._request("GET", "/api/v3/ticker/24hr", symbol=symbol)
            
            if 'error' in result:
                return {'error': result['error']}
            
            return {
                'symbol': symbol,
                'price': Decimal(result.get('lastPrice', '0')),
                'bid': Decimal(result.get('bidPrice', '0')),
                'ask': Decimal(result.get('askPrice', '0')),
                'high': Decimal(result.get('highPrice', '0')),
                'low': Decimal(result.get('lowPrice', '0')),
                'volume': Decimal(result.get('volume', '0')),
                'quote_asset_volume': Decimal(result.get('quoteAssetVolume', '0')),
                'price_change': Decimal(result.get('priceChange', '0')),
                'price_change_percent': Decimal(result.get('priceChangePercent', '0')),
                'weighted_avg_price': Decimal(result.get('weightedAvgPrice', '0')),
                'count': result.get('count', 0),
                'time': datetime.fromtimestamp(result.get('closeTime', 0) / 1000)
            }
        
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {str(e)}")
            return {'error': str(e)}

    async def place_order(self,
                         symbol: str,
                         side: str,
                         order_type: str,
                         quantity: float,
                         price: Optional[float] = None,
                         time_in_force: str = "GTC") -> Dict[str, Any]:
        """
        Place a new order
        
        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            side: BUY or SELL
            order_type: LIMIT or MARKET
            quantity: Order quantity
            price: Limit price (required for LIMIT orders)
            time_in_force: GTC, IOC, FOK (default: GTC)
        
        Returns:
            Order result
        """
        try:
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': order_type.upper(),
                'quantity': quantity,
                'timeInForce': time_in_force if order_type.upper() == 'LIMIT' else None,
                'price': price if order_type.upper() == 'LIMIT' else None,
            }
            
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}
            
            result = await self._request("POST", "/api/v3/order", signed=True, **params)
            
            if 'error' in result:
                return {'status': 'ERROR', 'error': result['error']}
            
            return {
                'orderId': result.get('orderId'),
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'quantity': Decimal(result.get('origQty', '0')),
                'price': Decimal(result.get('price', '0')) if price else None,
                'status': result.get('status'),
                'executedQty': Decimal(result.get('executedQty', '0')),
                'cummulativeQuoteQty': Decimal(result.get('cummulativeQuoteQty', '0')),
                'time': datetime.fromtimestamp(result.get('time', 0) / 1000)
            }
        
        except Exception as e:
            logger.error(f"Failed to place order for {symbol}: {str(e)}")
            return {'status': 'ERROR', 'error': str(e)}

    async def cancel_order(self, symbol: str, order_id: int) -> bool:
        """
        Cancel an open order
        
        Args:
            symbol: Trading pair
            order_id: Order ID to cancel
        
        Returns:
            True if successful
        """
        try:
            result = await self._request(
                "DELETE",
                "/api/v3/order",
                signed=True,
                symbol=symbol,
                orderId=order_id
            )
            return 'error' not in result
        
        except Exception as e:
            logger.error(f"Failed to cancel order: {str(e)}")
            return False

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders
        
        Args:
            symbol: Specific symbol or None for all
        
        Returns:
            List of open orders
        """
        try:
            params = {'symbol': symbol} if symbol else {}
            result = await self._request("GET", "/api/v3/openOrders", signed=True, **params)
            
            if isinstance(result, list):
                return [
                    {
                        'orderId': o['orderId'],
                        'symbol': o['symbol'],
                        'side': o['side'],
                        'type': o['type'],
                        'quantity': Decimal(o['origQty']),
                        'price': Decimal(o['price']),
                        'status': o['status'],
                        'time': datetime.fromtimestamp(o['time'] / 1000)
                    }
                    for o in result
                ]
            return []
        
        except Exception as e:
            logger.error(f"Failed to get open orders: {str(e)}")
            return []

    async def get_order_history(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get order history for a symbol
        
        Args:
            symbol: Trading pair
            limit: Number of orders to retrieve (max 500)
        
        Returns:
            List of orders
        """
        try:
            result = await self._request(
                "GET",
                "/api/v3/allOrders",
                signed=True,
                symbol=symbol,
                limit=min(limit, 500)
            )
            
            if isinstance(result, list):
                return [
                    {
                        'orderId': o['orderId'],
                        'symbol': o['symbol'],
                        'side': o['side'],
                        'quantity': Decimal(o['origQty']),
                        'price': Decimal(o['price']),
                        'executedQty': Decimal(o['executedQty']),
                        'status': o['status'],
                        'time': datetime.fromtimestamp(o['time'] / 1000)
                    }
                    for o in result
                ]
            return []
        
        except Exception as e:
            logger.error(f"Failed to get order history: {str(e)}")
            return []

    async def get_symbols(self) -> List[str]:
        """Get all available trading symbols"""
        try:
            result = await self._request("GET", "/api/v3/exchangeInfo")
            
            symbols = []
            for symbol in result.get('symbols', []):
                if symbol['status'] == 'TRADING':
                    symbols.append(symbol['symbol'])
            
            return symbols[:20]  # Return top 20 for demo
        
        except Exception as e:
            logger.error(f"Failed to get symbols: {str(e)}")
            return [
                "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT",
                "ADAUSDT", "DOGEUSDT", "LINKUSDT", "LITUSDT",
                "MATICUSDT", "UNIUSDT"
            ]
