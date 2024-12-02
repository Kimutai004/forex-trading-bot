import json
import os
from src.core.market.watcher import MarketWatcher
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
        Enhanced check for Expert Advisor status with actual trading capability verification
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
            
            # Test actual trading capability instead of just checking trade_expert
            diagnostics = {
                'trade_expert_raw': terminal_dict.get('trade_expert'),
                'trade_allowed': terminal_dict.get('trade_allowed', False),
                'connected': terminal_dict.get('connected', False),
                'dlls_allowed': terminal_dict.get('dlls_allowed', False),
                'trade_context': mt5.symbol_info_tick("EURUSD") is not None,
                'can_trade': False,  # Will be updated based on actual check
                'positions_accessible': False  # Will be updated based on check
            }

            # Verify ability to access positions
            try:
                positions = mt5.positions_total()
                diagnostics['positions_accessible'] = positions is not None
            except Exception as e:
                self.logger.error(f"Position access check failed: {str(e)}")
                diagnostics['positions_accessible'] = False

            # Test actual trading capability
            try:
                # Just check if order validation would pass
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
                result = mt5.order_check(request)
                diagnostics['can_trade'] = result is not None
                if result is not None:
                    diagnostics['order_check_retcode'] = result.retcode
                    # Consider it valid if order check passes or gets "market closed"
                    diagnostics['can_trade'] = result.retcode in [0, 10018]
            except Exception as e:
                self.logger.error(f"Trade capability check failed: {str(e)}")
                diagnostics['can_trade'] = False

            # Determine actual trading capability
            expert_enabled = (
                diagnostics['trade_allowed'] and
                diagnostics['connected'] and
                diagnostics['positions_accessible'] and
                diagnostics['can_trade']
            )

            self.logger.info(f"""
            Expert Status Check Results:
            Trade Expert Raw Value: {diagnostics['trade_expert_raw']}
            Can Actually Trade: {diagnostics['can_trade']}
            Trade Allowed: {diagnostics['trade_allowed']}
            Connected: {diagnostics['connected']}
            Positions Accessible: {diagnostics['positions_accessible']}
            Final Status: {'Enabled' if expert_enabled else 'Disabled'}
            Order Check Result: {diagnostics.get('order_check_retcode', 'N/A')}
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
        from src.utils.logger import setup_logger
        self.logger = setup_logger('MT5Trader')
        self.logger.info("MT5Trader logging system initialized")

    def _monitor_connection(self) -> bool:
        """
        Monitor MT5 connection status with enhanced error handling
        Returns: True if connection is healthy
        """
        try:
            self.logger.info("Checking MT5 connection status...")
            
            # First check basic initialization
            if not mt5.initialize():
                error = mt5.last_error()
                self.logger.error(f"MT5 not initialized. Error: {error[0]} - {error[1]}")
                return self._attempt_reconnection()

            # Get terminal info with retry
            terminal_info = None
            max_attempts = 3
            
            for attempt in range(max_attempts):
                terminal_info = mt5.terminal_info()
                if terminal_info is not None:
                    break
                self.logger.warning(f"Terminal info attempt {attempt + 1} failed, retrying...")
                time.sleep(1)

            if terminal_info is None:
                self.logger.error("Failed to get terminal info after retries")
                return self._attempt_reconnection()

            # Check connection status
            terminal_dict = terminal_info._asdict()
            
            self.logger.info(f"""
            MT5 Connection Check:
            Connected: {terminal_dict.get('connected', False)}
            Trade Allowed: {terminal_dict.get('trade_allowed', False)}
            Expert Enabled: {terminal_dict.get('trade_expert', False)}
            Last Connected: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """)

            if not terminal_dict.get('connected', False):
                self.logger.error("Terminal not connected to broker")
                return self._attempt_reconnection()

            # Test symbol access
            test_symbols = ['EURUSD', 'GBPUSD', 'USDJPY']
            symbol_status = []
            
            for symbol in test_symbols:
                if mt5.symbol_select(symbol, True):
                    tick = mt5.symbol_info_tick(symbol)
                    if tick is not None:
                        symbol_status.append(f"{symbol}: OK")
                    else:
                        symbol_status.append(f"{symbol}: No tick data")
                else:
                    symbol_status.append(f"{symbol}: Selection failed")

            self.logger.info(f"""
            Symbol Access Check:
            {chr(10).join(symbol_status)}
            """)

            # Check account access
            account_info = mt5.account_info()
            if account_info is None:
                self.logger.error("Cannot access account information")
                return self._attempt_reconnection()

            self.logger.info(f"""
            Account Access Check:
            Server: {account_info.server}
            Balance: ${account_info.balance}
            Leverage: 1:{account_info.leverage}
            """)

            self.connected = True
            return True

        except Exception as e:
            self.logger.error(f"Error monitoring connection: {str(e)}", exc_info=True)
            return self._attempt_reconnection()
        
    def _maintain_weekend_connection(self) -> bool:
        """
        Maintain MT5 connection during weekends
        Returns: True if connection is maintained
        """
        try:
            self.logger.info("Maintaining weekend connection...")
            
            if not mt5.initialize():
                self.logger.error("Could not initialize MT5 during weekend")
                return False

            # Verify minimal functionality
            account_info = mt5.account_info()
            if account_info is None:
                self.logger.error("Cannot access account info during weekend")
                return False

            self.logger.info(f"""
            Weekend Connection Status:
            Server: {account_info.server}
            Account: {account_info.login}
            Connected: Yes
            Last Check: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """)

            return True

        except Exception as e:
            self.logger.error(f"Weekend connection error: {str(e)}")
            return False

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
        """Check if market is open with connection stability"""
        try:
            if not self._monitor_connection():
                return False

            # Basic check first
            if not mt5.initialize():
                self.logger.error("MT5 not initialized")
                return False

            # Get a reference symbol tick
            tick = mt5.symbol_info_tick("EURUSD")
            if tick is None:
                self.logger.error("Cannot get price data")
                return False

            current_time = datetime.now()
            tick_time = datetime.fromtimestamp(tick.time)
            time_diff = (current_time - tick_time).total_seconds()

            self.logger.info(f"""
            Market Status Check:
            Current Time: {current_time}
            Last Tick Time: {tick_time}
            Time Difference: {time_diff:.1f} seconds
            Session: {self._get_current_session()}
            """)

            # Consider market closed if price is too old
            if time_diff > 180:  # 3 minutes
                self.logger.warning(f"Price data is stale ({time_diff:.1f} seconds old)")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error checking market status: {str(e)}")
            return False
    
    def _get_current_session(self) -> str:
        """Get current trading session based on server time"""
        try:
            current_hour = datetime.now().hour
            
            if 8 <= current_hour <= 16:  # London
                if 13 <= current_hour <= 16:
                    return "London-NY Overlap"
                return "London Session"
            elif 13 <= current_hour <= 21:  # New York
                return "New York Session"
            elif 0 <= current_hour <= 9:  # Tokyo
                if 8 <= current_hour <= 9:
                    return "Tokyo-London Overlap"
                return "Tokyo Session"
            elif 22 <= current_hour or current_hour <= 7:  # Sydney
                if 0 <= current_hour <= 2:
                    return "Sydney-Tokyo Overlap"
                return "Sydney Session"
            else:
                return "Between Sessions"
                
        except Exception as e:
            self.logger.error(f"Error determining current session: {str(e)}")
            return "Unknown Session"

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
        
    def log_market_state(self) -> Dict:
        """Detailed market state logging"""
        try:
            self.logger.info("""
            =============== MT5 MARKET STATE CHECK ===============
            """)
            
            # Get terminal info
            terminal_info = mt5.terminal_info()
            if terminal_info:
                terminal_dict = terminal_info._asdict()
                self.logger.info(f"""
                Terminal State:
                - Connected: {terminal_dict.get('connected')}
                - Trade Allowed: {terminal_dict.get('trade_allowed')}
                - Expert Enabled: {terminal_dict.get('trade_expert')}
                - Server Time: {datetime.now()}
                - Raw Server Time: {mt5.symbol_info_tick("EURUSD").time if mt5.symbol_info_tick("EURUSD") else 'N/A'}
                """)

            # Get session info
            current_session = self._get_current_session()
            self.logger.info(f"""
            Session Information:
            - Current Session: {current_session}
            - Server Time (Raw): {mt5.symbol_info_tick("EURUSD").time if mt5.symbol_info_tick("EURUSD") else 'N/A'}
            - Local Time: {datetime.now()}
            """)

            # Test market activity
            symbols = ["EURUSD", "GBPUSD", "USDJPY"]
            for symbol in symbols:
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    self.logger.info(f"""
                    {symbol} Activity:
                    - Last Tick Time: {datetime.fromtimestamp(tick.time)}
                    - Raw Tick Time: {tick.time}
                    - Bid: {tick.bid}
                    - Ask: {tick.ask}
                    - Volume: {tick.volume}
                    """)

            self.logger.info("=============== END MARKET STATE CHECK ===============")
            
            return {
                'session': current_session,
                'market_active': bool(mt5.symbol_info_tick("EURUSD"))
            }

        except Exception as e:
            self.logger.error(f"""
            Market State Check Error:
            Error: {str(e)}
            Traceback: {traceback.format_exc()}
            """)
            return {'error': str(e)}
        
    def check_connection_health(self) -> Dict:
        """
        Check MT5 connection health without reinitializing
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
            # Check terminal info without reinitializing
            terminal_info = mt5.terminal_info()
            if terminal_info is not None:
                terminal_dict = terminal_info._asdict()
                health_info.update({
                    'is_connected': terminal_dict.get('connected', False),
                    'terminal_connected': terminal_dict.get('connected', False),
                    'expert_enabled': terminal_dict.get('trade_expert', False),
                    'can_trade': terminal_dict.get('trade_allowed', False),
                    'mt5_initialized': True
                })
                health_info['diagnostics'].update({
                    'terminal': terminal_dict
                })

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

            # Log health check results only once
            self.logger.info(f"""
            MT5 Connection Health Check Results:
            - Connected: {health_info['is_connected']}
            - MT5 Initialized: {health_info['mt5_initialized']}
            - Terminal Connected: {health_info['terminal_connected']}
            - Expert Enabled: {health_info['expert_enabled']}
            - Can Trade: {health_info['can_trade']}
            - Account Accessible: {health_info['account_accessible']}
            """)

            return health_info
                
        except Exception as e:
            self.logger.error(f"Error during health check: {str(e)}")
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
        comment: str = "MT5Bot"
    ) -> Tuple[bool, str]:
        """Place trade with enhanced logging"""
        if not self._monitor_connection():
            return False, "MT5 connection unavailable"

        # Define error code descriptions
        ERROR_CODES = {
            10004: "Trade requote",
            10006: "Trade request rejected",
            10007: "Trade request canceled by trader",
            10008: "Trade request placed",
            10009: "Trade request executed",
            10010: "Only part of request executed",
            10011: "Trade request processing error",
            10012: "Trade request timeout",
            10013: "Invalid trade request price",
            10014: "Invalid trade request stops",
            10015: "Invalid trade request volume",
            10016: "Market closed or invalid trade parameters",
            10017: "No connection with trade server",
            10018: "Trade is blocked",
            10019: "Invalid trade order filling type",
            10020: "No connection with trade server",
            10021: "Trade request too many",
            10022: "Trade request queued",
            10023: "Trade request too many",
            10024: "Trade orders limit exceeded",
            10025: "Trade modify denied",
            10026: "Trade context busy",
            10027: "Trade expiration denied",
            10028: "Trade too many positions",
            10029: "Trade hedge prohibited",
            10030: "Trade prohibited by fifo rule"
        }
        
        try:
            self.logger.info(f"""
            ================== TRADE REQUEST START ==================
            Basic Parameters:
            - Symbol: {symbol}
            - Order Type: {order_type}
            - Volume: {volume}
            - Price: {price}
            - SL: {stop_loss}
            - TP: {take_profit}
            """)

            # Get and log symbol information
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is not None:
                symbol_dict = symbol_info._asdict()
                self.logger.info(f"""
                Symbol Information:
                - Contract Size: {symbol_dict.get('trade_contract_size')}
                - Min Volume: {symbol_dict.get('volume_min')}
                - Max Volume: {symbol_dict.get('volume_max')}
                - Volume Step: {symbol_dict.get('volume_step')}
                - Trade Stops Level: {symbol_dict.get('trade_stops_level')}
                - Points: {symbol_dict.get('point')}
                - Digits: {symbol_dict.get('digits')}
                - Trade Mode: {symbol_dict.get('trade_mode')}
                - Trade Execution Mode: {symbol_dict.get('trade_exemode')}
                - Spread: {symbol_dict.get('spread')}
                - Swap Long: {symbol_dict.get('swap_long')}
                - Swap Short: {symbol_dict.get('swap_short')}
                """)

            # Get and log tick information
            tick = mt5.symbol_info_tick(symbol)
            if tick is not None:
                tick_dict = tick._asdict()
                self.logger.info(f"""
                Current Market Data:
                - Bid: {tick_dict.get('bid')}
                - Ask: {tick_dict.get('ask')}
                - Last: {tick_dict.get('last')}
                - Volume: {tick_dict.get('volume')}
                - Time: {datetime.fromtimestamp(tick_dict.get('time', 0))}
                - Last Update: {datetime.now()}
                - Spread: {tick_dict.get('ask', 0) - tick_dict.get('bid', 0)}
                """)

            # Get and log account state
            account_info = mt5.account_info()
            if account_info is not None:
                acc_dict = account_info._asdict()
                self.logger.info(f"""
                Account State Before Trade:
                - Balance: {acc_dict.get('balance')}
                - Equity: {acc_dict.get('equity')}
                - Margin: {acc_dict.get('margin')}
                - Free Margin: {acc_dict.get('margin_free')}
                - Margin Level: {acc_dict.get('margin_level')}
                - Leverage: 1:{acc_dict.get('leverage')}
                """)

            # Prepare trade request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL,
                "price": price or (tick.ask if order_type == "BUY" else tick.bid),
                "deviation": 20,
                "magic": 123456,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            if stop_loss is not None:
                request["sl"] = float(stop_loss)
            if take_profit is not None:
                request["tp"] = float(take_profit)

            self.logger.info(f"""
            Trade Request Details:
            {json.dumps(request, indent=2)}
            """)

            # Check order before sending
            check_result = mt5.order_check(request)
            if check_result is not None:
                check_dict = check_result._asdict()
                self.logger.info(f"""
                Order Check Results:
                - Retcode: {check_dict.get('retcode')}
                - Balance: {check_dict.get('balance')}
                - Equity: {check_dict.get('equity')}
                - Margin: {check_dict.get('margin')}
                - Margin Free: {check_dict.get('margin_free')}
                - Expected Profit: {check_dict.get('profit')}
                - Comment: {check_dict.get('comment')}
                - Request ID: {check_dict.get('request_id')}
                """)

            # Send trade request
            result = mt5.order_send(request)
            if result is None:
                error = mt5.last_error()
                error_message = f"Trade failed. MT5 Error: {error[0]} - {error[1]}"
                self.logger.error(f"""
                Trade Execution Failed:
                Error Code: {error[0]}
                Description: {error[1]}
                Known Error: {ERROR_CODES.get(error[0], 'Unknown error code')}
                Time: {datetime.now()}
                """)
                return False, error_message

            # Log trade result
            result_dict = result._asdict()
            self.logger.info(f"""
            Trade Execution Result:
            - Retcode: {result_dict.get('retcode')}
            - Description: {ERROR_CODES.get(result_dict.get('retcode'), 'Unknown code')}
            - Deal ID: {result_dict.get('deal')}
            - Order ID: {result_dict.get('order')}
            - Volume: {result_dict.get('volume')}
            - Price: {result_dict.get('price')}
            - Bid: {result_dict.get('bid')}
            - Ask: {result_dict.get('ask')}
            - Comment: {result_dict.get('comment')}
            - Request ID: {result_dict.get('request_id')}
            - Retcode External: {result_dict.get('retcode_external')}
            Time: {datetime.now()}
            ================== TRADE REQUEST END ==================
            """)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                error_msg = f"Trade failed. Error code: {result.retcode} - {ERROR_CODES.get(result.retcode, 'Unknown error')}"
                self.logger.error(f"Trade execution failed: {error_msg}")
                return False, error_msg
            
            success_msg = f"Trade successfully placed. Ticket: {result.order}"
            self.logger.info(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"Error placing trade: {str(e)}\nTraceback: {traceback.format_exc()}"
            self.logger.error(error_msg)
            return False, str(e)

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