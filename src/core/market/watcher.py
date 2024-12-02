import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import time

@dataclass
class MarketData:
    """Container for OHLCV data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    tick_volume: Optional[float] = None
    spread: Optional[float] = None

class MarketWatcher:
    """Handles market data monitoring and retrieval"""
    
    def __init__(self, mt5_instance):
        """
        Initialize Market Watcher
        
        Args:
            mt5_instance: Instance of MT5Trader class
        """
        self.mt5_instance = mt5_instance
        self._setup_logging()
        self.data_cache: Dict[str, Dict] = {}
        self.timeframes = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1
        }
        
    def _setup_logging(self):
        """Setup logging for market watcher"""
        self.logger = logging.getLogger('MarketWatcher')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def get_ohlcv_data(self, symbol: str, timeframe: str, bars: int = 100, include_incomplete: bool = False) -> List[MarketData]:
        """Get OHLCV data for symbol"""
        self.logger.debug(f"Attempting to get data for {symbol} on {timeframe} timeframe")
        
        if not self.mt5_instance.connected:
            self.logger.warning(f"MT5 not connected when fetching data for {symbol}")
            return []
                
        try:
            # Ensure symbol is selected in Market Watch
            if not mt5.symbol_select(symbol, True):
                self.logger.error(f"Failed to select symbol {symbol}")
                return []
                    
            # Get MT5 timeframe constant
            mt5_timeframe = self.timeframes.get(timeframe)
            if mt5_timeframe is None:
                self.logger.error(f"Invalid timeframe: {timeframe}")
                return []
            
            # Log attempt to get rates
            self.logger.debug(f"Requesting {bars} bars of data")
            
            # Try different methods to get data
            rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, bars)
            if rates is None or len(rates) == 0:
                error = mt5.last_error()
                self.logger.error(f"Failed to get rates: Error code {error[0]}, {error[1]}")
                # Try alternative method
                rates = mt5.copy_rates_from(symbol, mt5_timeframe, 
                                        datetime.now(), bars)
                    
            if rates is None or len(rates) == 0:
                self.logger.warning(f"No data available for {symbol} {timeframe}")
                return []
                
            self.logger.debug(f"Received {len(rates)} bars of data")
            
            # Convert to MarketData objects
            market_data = []
            for rate in rates:
                try:
                    data = MarketData(
                        timestamp=datetime.fromtimestamp(rate['time']),
                        open=float(rate['open']),
                        high=float(rate['high']),
                        low=float(rate['low']),
                        close=float(rate['close']),
                        volume=float(rate['real_volume']),
                        tick_volume=float(rate['tick_volume']),
                        spread=float(rate['spread'])
                    )
                    market_data.append(data)
                except (KeyError, ValueError) as e:
                    self.logger.error(f"Error converting rate data: {e}")
                    continue
                
            # Log successful data retrieval
            self.logger.info(f"Retrieved {len(market_data)} candles for {symbol} {timeframe}")
            
            return market_data
                    
        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return []

    def _get_timeframe_delta(self, timeframe: str) -> timedelta:
        """Get timedelta for timeframe"""
        if timeframe.startswith('M'):
            return timedelta(minutes=int(timeframe[1:]))
        elif timeframe.startswith('H'):
            return timedelta(hours=int(timeframe[1:]))
        elif timeframe == 'D1':
            return timedelta(days=1)
        return timedelta(minutes=1)

    def get_current_price(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Get current bid/ask prices
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Tuple of (bid, ask) prices or (None, None) if unavailable
        """
        if not self.mt5_instance.connected:
            return None, None
            
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                self.logger.warning(f"No tick data for {symbol}")
                return None, None
            return tick.bid, tick.ask
            
        except Exception as e:
            self.logger.error(f"Error getting price for {symbol}: {str(e)}")
            return None, None

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get symbol information
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary with symbol information or None
        """
        if not self.mt5_instance.connected:
            return None
            
        try:
            info = mt5.symbol_info(symbol)._asdict()
            # Cache the info
            self.data_cache[symbol] = {
                'info': info,
                'timestamp': datetime.now()
            }
            return info
            
        except Exception as e:
            self.logger.error(f"Error getting info for {symbol}: {str(e)}")
            return None

    def setup_price_alert(
        self,
        symbol: str,
        price: float,
        condition: str,
        callback = None
    ) -> bool:
        """
        Setup price alert for symbol
        
        Args:
            symbol: Trading symbol
            price: Alert price level
            condition: Alert condition ('>', '<', '>=', '<=')
            callback: Optional callback function when alert triggers
            
        Returns:
            True if alert was set successfully
        """
        if not self.mt5_instance.connected:
            return False
            
        try:
            # Store alert in cache
            alert_key = f"{symbol}_{condition}_{price}"
            self.data_cache[alert_key] = {
                'symbol': symbol,
                'price': price,
                'condition': condition,
                'callback': callback,
                'active': True
            }
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting alert for {symbol}: {str(e)}")
            return False

    def check_alerts(self) -> List[Dict]:
        """
        Check and process active price alerts
        
        Returns:
            List of triggered alerts
        """
        if not self.mt5_instance.connected:
            return []
            
        triggered = []
        for key, alert in list(self.data_cache.items()):
            if not key.count('_') == 2:  # Not an alert key
                continue
                
            if not alert.get('active', False):
                continue
                
            symbol = alert['symbol']
            condition = alert['condition']
            alert_price = alert['price']
            
            current_bid, current_ask = self.get_current_price(symbol)
            if current_bid is None or current_ask is None:
                continue
                
            # Check if alert should trigger
            price = current_bid if condition in ['<', '<='] else current_ask
            should_trigger = False
            
            if condition == '>' and price > alert_price:
                should_trigger = True
            elif condition == '<' and price < alert_price:
                should_trigger = True
            elif condition == '>=' and price >= alert_price:
                should_trigger = True
            elif condition == '<=' and price <= alert_price:
                should_trigger = True
                
            if should_trigger:
                triggered.append(alert)
                # Call callback if provided
                if alert['callback']:
                    try:
                        alert['callback'](symbol, price, alert_price)
                    except Exception as e:
                        self.logger.error(f"Error in alert callback: {str(e)}")
                # Deactivate alert
                alert['active'] = False
                
        return triggered

    def clear_alerts(self, symbol: Optional[str] = None):
        """
        Clear price alerts
        
        Args:
            symbol: Optional symbol to clear alerts for.
                   If None, clears all alerts.
        """
        if symbol:
            # Clear alerts for specific symbol
            for key in list(self.data_cache.keys()):
                if key.startswith(f"{symbol}_"):
                    del self.data_cache[key]
        else:
            # Clear all alerts
            for key in list(self.data_cache.keys()):
                if key.count('_') == 2:  # Alert key
                    del self.data_cache[key]

    def clear_cache(self):
        """Clear all cached data"""
        self.data_cache.clear()

    def _check_market_status(self) -> dict:
        """Detailed market status check with comprehensive logging"""
        status = {
            'is_open': False,
            'connection_status': False,
            'price_feed_status': False,
            'login_status': False,
            'details': {}
        }
        
        try:
            # Check MT5 initialization
            init_status = mt5.initialize()
            self.logger.info(f"""
            Market Status Check Debug:
            =========================
            MT5 Initialization: {init_status}
            Terminal Info: {mt5.terminal_info()._asdict() if mt5.terminal_info() else 'None'}
            Symbol Info (EURUSD): {mt5.symbol_info("EURUSD")._asdict() if mt5.symbol_info("EURUSD") else 'None'}
            Latest Tick: {mt5.symbol_info_tick("EURUSD")._asdict() if mt5.symbol_info_tick("EURUSD") else 'None'}
            """)

            if not init_status:
                error = mt5.last_error()
                self.logger.error("MT5 initialization failed: %s (%d)", error[1], error[0])
                return status
                
            status['connection_status'] = True
            
            # Verify login
            account_info = mt5.account_info()
            if account_info is None:
                error = mt5.last_error()
                self.logger.error("Login verification failed: %s (%d)", error[1], error[0])
                return status
                
            status['login_status'] = True
            status['details']['account'] = {
                'login': account_info.login,
                'server': account_info.server,
                'balance': account_info.balance
            }
            
            # Check price feed
            symbol = "EURUSD"
            if not mt5.symbol_select(symbol, True):
                self.logger.error("Failed to select symbol: %s", symbol)
                return status
                
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                error = mt5.last_error()
                self.logger.error("Failed to get tick data: %s (%d)", error[1], error[0])
                return status
                
            status['price_feed_status'] = True
            status['details']['market'] = {
                'symbol': symbol,
                'bid': tick.bid,
                'ask': tick.ask,
                'time': datetime.fromtimestamp(tick.time).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.logger.info("Market status check results: %s", status)
            return status
                
        except Exception as e:
            self.logger.exception("Error in market status check")
            return status