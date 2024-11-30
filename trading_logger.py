from datetime import datetime
import os
import json
from typing import Dict, List, Optional
import logging
from signals.signal_provider import SignalType, Signal
from core.mt5_trader import MT5Trader
from core.position_manager import PositionManager
from signals.signal_manager import SignalManager
from core.config_manager import ConfigManager
import MetaTrader5 as mt5

class TradingLogger:
    """Handles generation and management of trading logs"""
    
    def __init__(self, mt5_trader, position_manager, signal_manager, config_manager, ftmo_manager):
        """
        Initialize Trading Logger
        
        Args:
            mt5_trader: MT5Trader instance
            position_manager: PositionManager instance
            signal_manager: SignalManager instance
            config_manager: ConfigManager instance
            ftmo_manager: FTMORuleManager instance
        """
        self.mt5_trader = mt5_trader
        self.position_manager = position_manager
        self.signal_manager = signal_manager
        self.config_manager = config_manager
        self.ftmo_manager = ftmo_manager
        
        # Create logs directory if it doesn't exist
        self.logs_dir = "trading_logs"
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
            
        # Initialize current log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.current_log_file = os.path.join(self.logs_dir, f"trading_activity_{timestamp}.log")
            
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging configuration"""
        from logger_config import setup_logger
        self.logger = setup_logger('TradingLogger')
        self.logger.info("TradingLogger initialized")
        self.logger.info(f"Trading activity will be logged to: {self.current_log_file}")

    def log_system_state(self):
        """Log detailed system state"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Get account information
            account_info = self.mt5_trader.get_account_info()
            
            # Get market state
            market_session = self.mt5_trader._get_current_session()
            
            # Get symbol prices
            symbol_prices = {}
            for symbol in self.config_manager.get_setting('favorite_symbols', []):
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    symbol_prices[symbol] = {
                        'bid': tick.bid,
                        'ask': tick.ask,
                        'spread': tick.ask - tick.bid,
                        'time': datetime.fromtimestamp(tick.time).strftime('%H:%M:%S')
                    }

            # Get open positions with duration checks
            positions = self.position_manager.get_open_positions()
            
            # Write detailed log entry
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"SYSTEM STATE UPDATE - {timestamp}\n")
                f.write(f"{'='*50}\n\n")
                
                # Market Information
                f.write("MARKET INFORMATION:\n")
                f.write(f"Current Session: {market_session}\n")
                f.write(f"Market Status: {'Open' if self.mt5_trader.market_is_open else 'Closed'}\n")
                f.write("\nSYMBOL PRICES:\n")
                for symbol, data in symbol_prices.items():
                    f.write(f"{symbol}:\n")
                    f.write(f"  Bid: {data['bid']}\n")
                    f.write(f"  Ask: {data['ask']}\n")
                    f.write(f"  Spread: {data['spread']}\n")
                    f.write(f"  Last Update: {data['time']}\n")
                
                # Account Information
                f.write("\nACCOUNT INFORMATION:\n")
                f.write(f"Balance: ${account_info['balance']:.2f}\n")
                f.write(f"Equity: ${account_info['equity']:.2f}\n")
                f.write(f"Profit: ${account_info['profit']:.2f}\n")
                f.write(f"Margin Level: {account_info.get('margin_level', 0)}%\n")
                
                # Position Information with Duration Checks
                f.write("\nOPEN POSITIONS:\n")
                if positions:
                    for pos in positions:
                        # Get duration check for each position
                        duration_check = self.ftmo_manager.check_position_duration(pos)
                        f.write(f"Symbol: {pos['symbol']}\n")
                        f.write(f"  Type: {pos['type']}\n")
                        f.write(f"  Volume: {pos['volume']}\n")
                        f.write(f"  Open Price: {pos['open_price']}\n")
                        f.write(f"  Current Price: {pos['current_price']}\n")
                        f.write(f"  Profit: ${pos['profit']:.2f}\n")
                        f.write(f"  Pips: {pos['pips']:.1f}\n")
                        f.write(f"  Duration: {duration_check['duration']}\n")
                        f.write(f"  Time Limit Status: {'WARNING' if duration_check['warning'] else 'OK'}\n")
                        if duration_check['needs_closure']:
                            f.write(f"  *** EXCEEDED TIME LIMIT ***\n")
                else:
                    f.write("No open positions\n")
                
                f.write(f"\n{'='*50}\n")
                
            self.logger.info(f"System state logged successfully at {timestamp}")
                
        except Exception as e:
            self.logger.error(f"Error logging system state: {str(e)}")

    def log_trade(self, trade_info: Dict):
        """Log trade execution details"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*30} TRADE EXECUTION {'='*30}\n")
                f.write(f"Time: {timestamp}\n")
                for key, value in trade_info.items():
                    f.write(f"{key}: {value}\n")
                f.write(f"{'='*78}\n")
                
            self.logger.info(f"Trade logged successfully: {trade_info.get('symbol')} {trade_info.get('type')}")
            
        except Exception as e:
            self.logger.error(f"Error logging trade: {str(e)}")

    def log_error(self, error_message: str, error_details: Optional[Dict] = None):
        """Log error information"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*30} ERROR {'='*30}\n")
                f.write(f"Time: {timestamp}\n")
                f.write(f"Error: {error_message}\n")
                if error_details:
                    f.write("Details:\n")
                    for key, value in error_details.items():
                        f.write(f"  {key}: {value}\n")
                f.write(f"{'='*70}\n")
                
            self.logger.error(f"Error logged: {error_message}")
            
        except Exception as e:
            self.logger.error(f"Error logging error: {str(e)}")