import json
import os
from market_watcher import MarketWatcher
import MetaTrader5 as mt5
from typing import Dict, Optional, Tuple
import time
from datetime import datetime
import logging
import traceback

class MT5Trader:
    def __init__(self, config_path: str = "config.json", status_manager=None):
        """
        Initialize MT5 trading module
        
        Args:
            config_path (str): Path to configuration file
            status_manager: BotStatusManager instance
        """
        self.config_path = config_path
        self.connected = False
        self.status_manager = status_manager
        self._start_time = datetime.now()
        self._setup_logging()
        self._initialize_mt5()
        self.market_watcher = MarketWatcher(self)

    def _check_expert_status(self) -> Dict:
        """
        Enhanced check for Expert Advisor status
        Returns Dict with status details and diagnostic info
        """
        try:
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                return {
                    'enabled': False,
                    'error': 'Could not get terminal info',
                    'diagnostics': {}
                }

            terminal_dict = terminal_info._asdict()
            
            # Direct expert check
            trade_expert = terminal_dict.get('trade_expert')
            
            # Alternative checks
            expert_enabled = True
            diagnostics = {
                'trade_expert_raw': trade_expert,
                'trade_allowed': terminal_dict.get('trade_allowed'),
                'connected': terminal_dict.get('connected'),
                'dlls_allowed': terminal_dict.get('dlls_allowed'),
                'trade_context': mt5.symbol_info_tick("EURUSD") is not None,
                'can_trade': True
            }
            
            # Test ability to place a trade
            try:
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": "EURUSD",
                    "volume": 0.01,
                    "type": mt5.ORDER_TYPE_BUY,
                    "price": mt5.symbol_info_tick("EURUSD").ask,
                    "deviation": 20,
                    "magic": 234000,
                    "comment": "Expert check",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                # Just check if order check passes, don't actually place the trade
                result = mt5.order_check(request)
                if result is None:
                    diagnostics['can_trade'] = False
                    expert_enabled = False
                else:
                    diagnostics['order_check_retcode'] = result.retcode
                    # If order check passes, experts are likely enabled
                    expert_enabled = result.retcode in [0, 10018]  # 10018 is "Market closed"
                    
            except Exception as e:
                diagnostics['order_check_error'] = str(e)
                diagnostics['can_trade'] = False
                expert_enabled = False

            # Additional context check
            try:
                positions = mt5.positions_total()
                diagnostics['positions_accessible'] = positions is not None
                expert_enabled = expert_enabled and diagnostics['positions_accessible']
            except Exception as e:
                diagnostics['positions_error'] = str(e)
                diagnostics['positions_accessible'] = False

            # Log all diagnostic information
            self.logger.info(f"""
            Expert Status Check Results:
            Trade Expert Raw Value: {trade_expert}
            Can Trade: {diagnostics['can_trade']}
            Trade Allowed: {diagnostics['trade_allowed']}
            Connected: {diagnostics['connected']}
            DLLs Allowed: {diagnostics['dlls_allowed']}
            Trade Context: {diagnostics['trade_context']}
            Positions Accessible: {diagnostics.get('positions_accessible')}
            Final Status: {'Enabled' if expert_enabled else 'Disabled'}
            """)
            
            return {
                'enabled': expert_enabled,
                'error': None,
                'diagnostics': diagnostics
            }
            
        except Exception as e:
            self.logger.error(f"Error checking expert status: {str(e)}", exc_info=True)
            return {
                'enabled': False,
                'error': str(e),
                'diagnostics': {'exception': str(e)}
            }

    def _setup_logging(self):
        from logger_config import setup_logger
        self.logger = setup_logger('MT5Trader')
        self.logger.info("MT5Trader logging system initialized")

    def _monitor_connection(self) -> bool:
        """
        Monitor and attempt to recover MT5 connection if needed
        
        Returns:
            bool: True if connection is healthy or recovered successfully
        """
        self.logger.debug("Checking MT5 connection health")
        
        try:
            # Check if terminal is accessible
            if not mt5.terminal_info():
                self.logger.error("MT5 terminal not accessible")
                return self._attempt_reconnection()
                
            # Verify account access
            account_info = mt5.account_info()
            if account_info is None:
                self.logger.error("Cannot access account information")
                return self._attempt_reconnection()
                
            # Verify market data access
            test_symbol = "EURUSD"
            if not mt5.symbol_select(test_symbol, True):
                self.logger.error(f"Cannot select symbol {test_symbol}")
                return self._attempt_reconnection()
                
            self.logger.debug("MT5 connection is healthy")
            return True
            
        except Exception as e:
            self.logger.error(f"Error monitoring connection: {str(e)}")
            return self._attempt_reconnection()

    def _attempt_reconnection(self) -> bool:
        """
        Attempt to reconnect to MT5
        
        Returns:
            bool: True if reconnection successful
        """
        max_attempts = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_attempts):
            self.logger.info(f"MT5 reconnection attempt {attempt + 1}/{max_attempts}")
            
            try:
                # Shutdown existing connection
                mt5.shutdown()
                time.sleep(retry_delay)
                
                # Reinitialize MT5
                if not mt5.initialize():
                    continue
                    
                # Attempt login
                credentials = self._load_or_create_credentials()
                if mt5.login(
                    login=int(credentials['username']),
                    password=credentials['password'],
                    server=credentials['server']
                ):
                    self.connected = True
                    self.logger.info("MT5 reconnection successful")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Reconnection attempt failed: {str(e)}")
                
            time.sleep(retry_delay)
        
        self.logger.error("All reconnection attempts failed")
        return False

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
            if not mt5.initialize():
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
            
            self.logger.debug("Market status check results: %s", status)
            return status
            
        except Exception as e:
            self.logger.exception("Error in market status check")
            return status

    @property
    def market_is_open(self) -> bool:
        """Check if market is open with enhanced connection handling"""
        if not self.connected:
            self.logger.warning("Market check failed: MT5 not connected")
            return False
                    
        try:
            # Enhanced connection verification
            if not mt5.initialize():
                self.logger.error("MT5 initialization required")
                if not self._initialize_mt5():
                    return False
            
            # Verify terminal connection first
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                self.logger.error("Cannot get terminal info")
                return False
                    
            terminal_dict = terminal_info._asdict()
            if not terminal_dict.get('connected', False):
                self.logger.error("Terminal not connected")
                return False
                    
            # Get current server time
            tick = mt5.symbol_info_tick("EURUSD")
            if tick is None:
                self.logger.error("Cannot get current server time")
                return False
                
            server_time = datetime.fromtimestamp(tick.time)
            self.logger.info(f"Current server time: {server_time}")
            self.logger.info(f"Current session: {self._get_current_session()}")
            
            # Check if market is actually receiving price updates
            initial_tick = mt5.symbol_info_tick("EURUSD")
            time.sleep(1)  # Wait a second
            second_tick = mt5.symbol_info_tick("EURUSD")
            
            if initial_tick and second_tick:
                self.logger.info(f"Price update check: Initial={initial_tick.bid}, Second={second_tick.bid}")
            else:
                self.logger.error("Failed to get price updates")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error checking market status: {str(e)}")
            return False
    
    def _get_current_session(self) -> str:
        """Get current trading session based on Costa Rica time"""
        current_hour = datetime.now().hour
        
        if 16 <= current_hour <= 23:  # 4 PM - 11 PM
            return "Sydney/Tokyo Session"
        elif 2 <= current_hour <= 11:  # 2 AM - 11 AM
            return "London Session"
        elif 7 <= current_hour <= 16:  # 7 AM - 4 PM
            return "New York Session"
        else:
            return "Between Sessions"

    def _initialize_mt5(self) -> bool:
        """Initialize connection to MT5 terminal"""
        try:
            # First shutdown any existing connection
            mt5.shutdown()
            time.sleep(2)  # Wait for clean shutdown
            
            # Initialize MT5 with extended timeout
            if not mt5.initialize(
                login=int(self._load_or_create_credentials()['username']),
                server=self._load_or_create_credentials()['server'],
                password=self._load_or_create_credentials()['password'],
                timeout=30000  # 30 second timeout
            ):
                error = mt5.last_error()
                self.logger.error(f"MT5 initialization failed. Error Code: {error[0]}, Description: {error[1]}")
                self.status_manager.update_module_status(
                    "MT5Trader",
                    "ERROR",
                    f"Failed to initialize MT5: {error[1]}"
                )
                return False

            # Get terminal info for diagnostics
            terminal_info = mt5.terminal_info()
            if terminal_info is not None:
                terminal_dict = terminal_info._asdict()
                self.logger.info(f"""
                MT5 Terminal Status:
                - Community Account: {terminal_dict.get('community_account')}
                - Connected: {terminal_dict.get('connected')}
                - Trade Allowed: {terminal_dict.get('trade_allowed')}
                - Trade Expert: {terminal_dict.get('trade_expert')}
                - Path: {terminal_dict.get('path')}
                """)

                # Check if AutoTrading is enabled
                if not terminal_dict.get('trade_allowed', False):
                    self.logger.error("AutoTrading is not enabled in MT5. Please enable it and restart.")
                    print("\nIMPORTANT: Please enable AutoTrading in MetaTrader 5:")
                    print("1. Click the 'AutoTrading' button in MT5 (top toolbar)")
                    print("2. Ensure the button is highlighted/enabled")
                    print("3. Restart this bot")
                    return False

            # Verify account access
            account_info = mt5.account_info()
            if account_info is None:
                self.logger.error("Cannot access account information")
                return False

            self.connected = True
            self.logger.info(f"""
                            Successfully connected to MT5:
                            - Account: ****{str(account_info.login)[-4:]}
                            - Server: {account_info.server}
                            - Balance: {account_info.balance}
                            - Leverage: 1:{account_info.leverage}
                            - Company: {account_info.company}
                            """)
            
            self.status_manager.update_module_status(
                "MT5Trader",
                "OK",
                "Successfully connected to MT5"
            )
            return True
                    
        except Exception as e:
            self.logger.error(f"Unexpected error during MT5 initialization: {str(e)}", exc_info=True)
            return False
        
    def check_connection_health(self) -> Dict:
        """
        Perform comprehensive connection health check
        Returns dict with health status and diagnostics
        """
        health_info = {
            'is_connected': False,
            'mt5_initialized': False,
            'can_trade': False,
            'terminal_connected': False,
            'expert_enabled': False,
            'account_accessible': False,
            'error_code': None,
            'error_message': None,
            'diagnostics': {}
        }
        
        try:
            # Check MT5 initialization
            health_info['mt5_initialized'] = mt5.initialize()
            if not health_info['mt5_initialized']:
                error = mt5.last_error()
                health_info.update({
                    'error_code': error[0],
                    'error_message': error[1]
                })
                self.logger.error(f"MT5 not initialized. Error: {error[0]} - {error[1]}")
                return health_info

            # Check terminal info
            terminal_info = mt5.terminal_info()
            if terminal_info is not None:
                terminal_dict = terminal_info._asdict()
                health_info['terminal_connected'] = terminal_dict.get('connected', False)
                health_info['expert_enabled'] = terminal_dict.get('trade_expert', False)
                health_info['can_trade'] = terminal_dict.get('trade_allowed', False)
                health_info['diagnostics']['terminal'] = {
                    'path': terminal_dict.get('path'),
                    'data_path': terminal_dict.get('data_path'),
                    'connected': terminal_dict.get('connected'),
                    'community_account': terminal_dict.get('community_account'),
                    'community_connection': terminal_dict.get('community_connection'),
                    'dlls_allowed': terminal_dict.get('dlls_allowed'),
                    'trade_allowed': terminal_dict.get('trade_allowed'),
                    'trade_expert': terminal_dict.get('trade_expert'),
                    'mqid': terminal_dict.get('mqid')
                }

            # Check account access
            account_info = mt5.account_info()
            if account_info is not None:
                health_info['account_accessible'] = True
                health_info['diagnostics']['account'] = {
                    'login': account_info.login,
                    'server': account_info.server,
                    'currency': account_info.currency,
                    'leverage': account_info.leverage,
                    'company': account_info.company,
                    'balance': account_info.balance,
                    'credit': account_info.credit,
                    'margin_free': account_info.margin_free
                }
            else:
                error = mt5.last_error()
                health_info['diagnostics']['account_error'] = f"{error[0]} - {error[1]}"

            # Update overall connection status
            health_info['is_connected'] = all([
                health_info['mt5_initialized'],
                health_info['terminal_connected'],
                health_info['expert_enabled'],
                health_info['account_accessible']
            ])

            # Log health check results
            log_level = logging.INFO if health_info['is_connected'] else logging.ERROR
            self.logger.log(log_level, f"""
            MT5 Connection Health Check Results:
            - Connected: {health_info['is_connected']}
            - MT5 Initialized: {health_info['mt5_initialized']}
            - Terminal Connected: {health_info['terminal_connected']}
            - Expert Enabled: {health_info['expert_enabled']}
            - Can Trade: {health_info['can_trade']}
            - Account Accessible: {health_info['account_accessible']}
            """)

            if not health_info['is_connected']:
                self.logger.error("Connection health check failed. See detailed diagnostics above.")
            
            return health_info
            
        except Exception as e:
            self.logger.error(f"Error during health check: {str(e)}", exc_info=True)
            health_info['error_message'] = str(e)
            return health_info

    def _load_or_create_credentials(self) -> Dict:
        """Load credentials from config file or create new ones"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        
        # If no config exists, prompt for credentials
        print("\nPlease enter your MT5 credentials:")
        print("Note: The username/login should be a number provided by your broker")
        while True:
            try:
                username = input("Enter MT5 username/login (number): ")
                # Verify username is a valid number
                int(username)
                break
            except ValueError:
                print("Username must be a number. Please try again.")
        
        credentials = {
            'username': username,
            'password': input("Enter MT5 password: "),
            'server': input("Enter MT5 server (e.g., 'ICMarketsSC-Demo'): ")
        }
        
        # Save credentials
        with open(self.config_path, 'w') as f:
            json.dump(credentials, f)
        
        return credentials

    def place_trade(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "MT5Bot"  # Default comment that is known to work
    ) -> Tuple[bool, str]:
        
        """
        Place a trade with specified parameters
        
        Args:
            symbol (str): Trading instrument symbol
            order_type (str): 'BUY' or 'SELL'
            volume (float): Trade volume in lots
            price (float, optional): Price for pending orders
            stop_loss (float, optional): Stop loss price
            take_profit (float, optional): Take profit price
            comment (str, optional): Trade comment
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        
        """Place trade with connection monitoring"""
        if not self._monitor_connection():
            return False, "MT5 connection unavailable"


        if not self.connected:
            return False, "Not connected to MT5"

        try:
            # Verify symbol is available
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return False, f"Symbol {symbol} not found"
                
            if not mt5.symbol_select(symbol, True):
                return False, f"Symbol {symbol} not selected"

            # Get current price if not provided
            if not price:
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    return False, f"Cannot get price for {symbol}"
                price = tick.ask if order_type == "BUY" else tick.bid

            # Clean and validate comment
            # Remove any special characters and limit length
            clean_comment = "".join(c for c in comment if c.isalnum() or c.isspace())[:31]

            # Prepare the trade request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),  # Ensure volume is float
                "type": mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL,
                "price": float(price),    # Ensure price is float
                "deviation": 20,
                "magic": 123456,
                "comment": clean_comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # Add stop loss and take profit if provided
            if stop_loss is not None:
                request["sl"] = float(stop_loss)
            if take_profit is not None:
                request["tp"] = float(take_profit)

            # Log the request for debugging
            self.logger.info(f"Sending trade request: {request}")

            # Send the trade request
            result = mt5.order_send(request)
            if result is None:
                error = mt5.last_error()
                error_msg = f"Trade failed. MT5 Error: {error[0]} - {error[1]}"
                self.logger.error(error_msg)
                return False, error_msg

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                error_msg = f"Trade failed. Error code: {result.retcode}"
                self.logger.error(error_msg)
                return False, error_msg
            
            success_msg = f"Trade successfully placed. Ticket: {result.order}"
            self.logger.info(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"Error placing trade: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def modify_trade(
        self,
        ticket: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Modify an existing trade's stop loss and take profit
        
        Args:
            ticket (int): Trade ticket number
            stop_loss (float, optional): New stop loss price
            take_profit (float, optional): New take profit price
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        if not self.connected:
            return False, "Not connected to MT5"

        # Prepare modification request
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False, "Position not found"

        request = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "position": ticket,
            "symbol": position[0].symbol,
            "sl": stop_loss if stop_loss else position[0].sl,
            "tp": take_profit if take_profit else position[0].tp,
        }

        # Send modification request
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return False, f"Modification failed. Error code: {result.retcode}"
        
        return True, "Trade successfully modified"

    def close_trade(self, ticket: int) -> Tuple[bool, str]:
        """
        Close a specific trade
        
        Args:
            ticket (int): Trade ticket number
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        if not self.connected:
            return False, "Not connected to MT5"

        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False, "Position not found"

        # Prepare close request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": position[0].symbol,
            "volume": position[0].volume,
            "type": mt5.ORDER_TYPE_SELL if position[0].type == 0 else mt5.ORDER_TYPE_BUY,
            "price": mt5.symbol_info_tick(position[0].symbol).bid if position[0].type == 0 else mt5.symbol_info_tick(position[0].symbol).ask,
            "deviation": 20,
            "magic": 123456,
            "comment": "Position closed",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Send close request
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return False, f"Close failed. Error code: {result.retcode}"
        
        return True, "Trade successfully closed"

    def get_account_info(self) -> Dict:
        """Get current account information with connection recovery"""
        self.logger.debug("Retrieving account information")
        
        if not self._monitor_connection():
            self.logger.error("Cannot get account info: Connection unavailable")
            return {
                "balance": 0.0,
                "equity": 0.0,
                "profit": 0.0,
                "margin": 0.0,
                "margin_free": 0.0,
                "margin_level": 0.0
            }
            
        try:
            account_info = mt5.account_info()
            if account_info is None:
                error = mt5.last_error()
                self.logger.error(f"Failed to get account info from MT5. Error code: {error[0]}, Description: {error[1]}")
                return self._get_default_account_info()
                
            return {
                "balance": float(getattr(account_info, 'balance', 0)),
                "equity": float(getattr(account_info, 'equity', 0)),
                "profit": float(getattr(account_info, 'profit', 0)),
                "margin": float(getattr(account_info, 'margin', 0)),
                "margin_free": float(getattr(account_info, 'margin_free', 0)),
                "margin_level": float(getattr(account_info, 'margin_level', 0) if getattr(account_info, 'margin_level', None) is not None else 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {str(e)}")
            return self._get_default_account_info()

    def _get_default_account_info(self) -> Dict:
        """Return default account information structure"""
        return {
            "balance": 0.0,
            "equity": 0.0,
            "profit": 0.0,
            "margin": 0.0,
            "margin_free": 0.0,
            "margin_level": 0.0
        }

    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.connected:
            mt5.shutdown()