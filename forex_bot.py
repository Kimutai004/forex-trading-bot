import logging
from zoneinfo import ZoneInfo
import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import msvcrt  # for Windows
import select
import sys
from src.core.trading.mt5 import MT5Trader
from src.core.trading.positions import PositionManager
from src.core.config_manager import ConfigManager
from src.core.system.menu import MenuManager
from src.core.trading_logic import TradingLogic
from src.signals.providers.manager import SignalManager
from src.signals.providers.base import SignalType
from src.core.system.auditor import SystemAuditor
from src.core.system.monitor import BotStatusManager
from src.core.ftmo_rule_manager import FTMORuleManager
from src.utils.trading_logger import TradingLogger 
from src.core.market.sessions import MarketSessionManager
from src.signals.providers.evaluator import SignalEvaluator
import time
import keyboard
import os

class ForexBot:
    def __init__(self):
        """Initialize Forex Bot with System Auditor"""
        try:
            # Setup logging first
            self._setup_logging()
            self.logger.info("Starting ForexBot initialization...")

            # Setup trading logs
            self.log_file = self._setup_trading_logs()

            # Initialize configuration
            self.config = ConfigManager()
            self.logger.info("Configuration manager initialized")

            # Initialize FTMO rule manager
            self.ftmo_manager = FTMORuleManager()
            self.logger.info("FTMO rule manager initialized")

            # Initialize status manager
            self.status_manager = BotStatusManager(self.config)
            self.logger.info("Status manager initialized")

            # Initialize MT5 trader
            self.mt5_trader = MT5Trader(status_manager=self.status_manager)
            if not self.mt5_trader.connected:
                raise RuntimeError("Failed to connect to MT5")
            self.logger.info("MT5 trader initialized and connected")
            self.ftmo_manager.set_mt5_trader(self.mt5_trader)

            # Initialize position manager
            self.position_manager = PositionManager(self.mt5_trader)
            self.logger.info("Position manager initialized")

            # Initialize signal manager first without trading logic
            self.signal_manager = SignalManager(self.mt5_trader, self.config)
            self.logger.info("Signal manager initialized")

            # Initialize trading logic
            self.trading_logic = TradingLogic(
                self.mt5_trader, 
                self.signal_manager, 
                self.position_manager,
                self.ftmo_manager  # Pass the FTMO manager here
            )
            self.logger.info("Trading logic initialized")

            # Update signal manager with trading logic and initialize evaluator
            self.signal_manager.trading_logic = self.trading_logic
            self.signal_manager.signal_evaluator = SignalEvaluator(
                signal_manager=self.signal_manager,
                trading_logic=self.trading_logic,
                ftmo_manager=self.ftmo_manager
            )

            # Initialize menu and other components
            self.menu = self._initialize_menu_manager()
            self.system_auditor = self._initialize_system_auditor()
            if not self.system_auditor:
                raise RuntimeError("Failed to initialize system auditor")
            self.trading_logger = TradingLogger(self.mt5_trader, self.position_manager, self.signal_manager, self.config, self.ftmo_manager)
            
            self.running = True
            self.logger.info("ForexBot initialization completed successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize ForexBot: {str(e)}")
            raise RuntimeError(f"Bot initialization failed: {str(e)}")

    def _setup_logging(self):
        from src.utils.logger import setup_logger
        self.logger = setup_logger('ForexBot')
        self.logger.info("ForexBot logging system initialized")

    def _setup_trading_logs(self):
        """Initialize trading logs directory and system"""
        try:
            if not os.path.exists("trading_logs"):
                os.makedirs("trading_logs")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = f"trading_logs/trading_session_{timestamp}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(file_handler)
            self.logger.info("=== New Trading Session Started ===")
            self.logger.info(f"Session ID: {timestamp}")
            self.logger.info(f"Log File: {log_file}")
            return log_file
        except Exception as e:
            self.logger.error(f"Failed to setup trading logs: {str(e)}")
            return None

    def _initialize_menu_manager(self) -> MenuManager:
        """Initialize and setup menu manager with required dependencies"""
        try:
            menu = MenuManager()
            menu.signal_manager = self.signal_manager
            menu.config_manager = self.config
            menu.status_manager = self.status_manager
            menu.position_manager = self.position_manager
            menu.trading_logic = self.trading_logic
            self.logger.info("Menu manager initialized with all dependencies")
            return menu
        except Exception as e:
            self.logger.error(f"Failed to initialize menu manager: {str(e)}")
            raise RuntimeError(f"Menu initialization failed: {str(e)}")

    def _log_session_status(self):
        """Log detailed session status without MT5 health check"""
        try:
            self.logger.info("\n=== Session Status Check ===")
            
            # Get raw session data
            session_data = self.session_manager.calendar_data.get("sessions", {})
            self.logger.info(f"""
            Raw Session Configuration:
            Sydney: {session_data.get('Sydney', 'Not configured')}
            Tokyo: {session_data.get('Tokyo', 'Not configured')}
            London: {session_data.get('London', 'Not configured')}
            NewYork: {session_data.get('NewYork', 'Not configured')}
            """)

            # Get current session status
            current_time = datetime.now()
            utc_time = datetime.now(ZoneInfo("UTC"))
            self.logger.info(f"""
            Time Information:
            Local Time: {current_time}
            UTC Time: {utc_time}
            Weekday: {utc_time.strftime('%A')}
            Hour: {utc_time.hour}
            """)

            # Check individual sessions
            for session in ['Sydney', 'Tokyo', 'London', 'NewYork']:
                is_open = self.session_manager.is_session_open(session)
                self.logger.info(f"Session {session}: {'OPEN' if is_open else 'CLOSED'}")

            # Log session manager's current info
            session_info = self.session_manager.get_current_session_info()
            self.logger.info(f"""
            Session Manager Status:
            Active Sessions: {session_info['active_sessions']}
            Upcoming Sessions: {session_info['upcoming_sessions']}
            Market Status: {session_info['market_status']}
            """)

        except Exception as e:
            self.logger.error(f"Error logging session status: {str(e)}")

    def _initialize_system_auditor(self):
        """Initialize system auditor with proper dependencies"""
        try:
            system_auditor = SystemAuditor(config_manager=self.config)
            self.logger.info("System auditor initialized")
            return system_auditor
        except Exception as e:
            self.logger.error(f"Failed to initialize system auditor: {str(e)}")
            return None
    
    def _create_error_log(self, error_messages: List[str]) -> Optional[str]:
        """Create error log file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            error_log_path = os.path.join(self.logs_dir, f"startup_errors_{timestamp}.log")
            
            with open(error_log_path, 'w') as f:
                f.write("=== STARTUP ERRORS ===\n")
                f.write(f"Time: {datetime.now()}\n\n")
                for error in error_messages:
                    f.write(f"ERROR: {error}\n")
                    
            self.logger.info(f"Created error log at: {error_log_path}")
            return error_log_path
            
        except Exception as e:
            self.logger.error(f"Failed to create error log: {str(e)}")
            return None
    
    def update_dashboard(self):
        """Update and display the dashboard with improved session and timing information"""
        self.logger.info("\n=== Dashboard Update Started ===")
        self.menu.clear_screen()

        print("=" * 50)
        print("Forex Trading Bot - Live Dashboard".center(50))
        print("=" * 50)
        print()

        status = self.status_manager.get_bot_status()
        self.logger.info(f"Bot Status Retrieved: {status}")
        print(f"System Status: {status['bot_status']['mode']}")
        print()

        # Get and log session info
        session_info = self.session_manager.get_current_session_info()
        self.logger.info(f"Session Info Retrieved: {session_info}")
        
        if session_info['active_sessions']:
            self.logger.info(f"Active Sessions: {session_info['active_sessions']}")
            print(f"Current Sessions: {', '.join(session_info['active_sessions'])}")
        else:
            self.logger.info("No active sessions")
            print("Current Sessions: No Major Markets Open")

        self.logger.info(f"Upcoming Sessions: {session_info['upcoming_sessions']}")
        print("Next Sessions:")
        for next_session in session_info['upcoming_sessions']:
            print(f"- {next_session['name']} opens in {next_session['opens_in']}")
        print()

        # Get and log trading signals
        self.logger.info("Retrieving trading signals")
        print("Trading Signals:")
        print("-" * 50)
        print(f"{'Symbol':<8} {'Direction':<8} {'Strength':<8} {'Price':<12}")
        print("-" * 50)

        symbols = self.signal_manager.config_manager.get_setting('favorite_symbols', [])
        self.logger.info(f"Processing symbols: {symbols}")
        
        for symbol in symbols:
            signals = self.signal_manager.get_signals(symbol)
            self.logger.info(f"Signals for {symbol}: {len(signals) if signals else 0} signals")
            if signals:
                consensus = self.signal_manager.get_consensus_signal(symbol)
                if consensus:
                    tick = mt5.symbol_info_tick(symbol)
                    price = f"{tick.bid:.5f}" if tick else "N/A"
                    self.logger.info(f"Consensus for {symbol}: {consensus.type.value}, Price: {price}")
                    print(f"{symbol:<8} {consensus.type.value:<8} {'Strong':<8} {price:<12}")

        # Get and log position information
        positions = self.position_manager.get_open_positions()
        self.logger.info(f"Open Positions: {len(positions)}/{self.trading_logic.max_total_positions}")
        
        if len(positions) >= self.trading_logic.max_total_positions:
            print(f"\nNote: All new positions temporarily on hold "
                f"({len(positions)}/{self.trading_logic.max_total_positions} maximum positions reached)")

        print(f"\nOpen Positions ({len(positions)}/{self.trading_logic.max_total_positions}):")
        print("-" * 90)
        print(f"{'Symbol':<8} {'Type':<6} {'Entry':<10} {'Current':<10} {'P/L':<12} "
            f"{'Take Profit':<14} {'Stop Loss':<12} {'Duration':<12}")
        print("-" * 90)

        for pos in positions:
            metrics = self.ftmo_manager.get_position_metrics(pos)
            self.logger.info(f"Position Metrics for {pos['ticket']}: {metrics}")
            
            print(f"\n{pos['symbol']:<8} {pos['type']:<6} {pos['open_price']:.5f} "
                f"{pos['current_price']:.5f} {'+' if pos['profit'] >= 0 else ''}"
                f"${pos['profit']:.2f}{'':8} {pos['tp']:.5f}     {pos['sl']:.5f}     "
                f"{metrics['duration']}")
            
            potential_tp = abs(pos['tp'] - pos['current_price']) * pos['volume'] * 100000
            potential_sl = abs(pos['sl'] - pos['current_price']) * pos['volume'] * 100000
            print(f"         {pos['volume']:.2f}{'':31} "
                f"(+${potential_tp:.2f}*){'':4} (-${potential_sl:.2f}*)   "
                f"Opened: {metrics['open_time']}")
            
            print()

        print("\n* Potential profit/loss if TP/SL hit")

        # Get and log account information
        account_info = self.mt5_trader.get_account_info()
        self.logger.info(f"Account Info: {account_info}")
        
        print("\nAccount Summary:")
        print("-" * 50)
        print(f"Balance: ${account_info['balance']:.2f}")
        print(f"Current P/L: ${account_info['profit']:.2f}")
        print(f"Free Margin: ${account_info['margin_free']:.2f}")
        print()

        print(f"Last update: {datetime.now().strftime('%H:%M:%S')}")
        print()

        print("Options:")
        print("1. View Logs")
        print("0. Exit")
        
        self.logger.info("=== Dashboard Update Completed ===\n")

    def run_trading_loop(self):
        """Main trading loop with continuous FTMO monitoring"""
        try:
            self._log_session_status()  # Add detailed session status logging
            self._log_market_status()  # Add detailed market status logging
            self.logger.info("\n=== Trading Loop Iteration Start ===")
            self.logger.info(f"""
            Current Time: {datetime.now()}
            UTC Time: {datetime.now().replace(tzinfo=None)}
            Market Status Check Starting
            """)

            # Always monitor FTMO status, even during closed markets
            ftmo_status = self.ftmo_manager.monitor_ftmo_status()
            if 'error' in ftmo_status:
                self.logger.error(f"FTMO monitoring error: {ftmo_status['error']}")
                return

            # Get account info for FTMO monitoring
            account_info = self.mt5_trader.get_account_info()
            
            # Log FTMO metrics even during closed market
            if self.ftmo_manager:
                self.ftmo_manager.ftmo_logger.log_daily_loss(
                    account_info['profit'],
                    self.ftmo_manager.rules['trading_rules']['max_daily_loss']
                )
                
                self.ftmo_manager.ftmo_logger.log_profit_update(
                    account_info['profit'],
                    self.ftmo_manager.rules['trading_rules']['profit_target']
                )

                # Track trading days requirement
                trading_days_status = self.ftmo_manager.track_trading_days_requirement()
                self.logger.info(f"""
                Trading Days Requirement Status:
                Status: {trading_days_status['status']}
                Progress: {trading_days_status['days_completed']}/{trading_days_status['days_required']} days
                Remaining: {trading_days_status['days_remaining']} days
                """)

            # Track FTMO metrics (even during closed market)
            trading_days = self.ftmo_manager.track_trading_days()
            drawdown = self.ftmo_manager.monitor_drawdown()
            profit = self.ftmo_manager.track_profit_target()
            
            # Log comprehensive status
            self.logger.info(f"""
            FTMO Status Update:
            Trading Days: {trading_days['status']} ({trading_days['days_completed']}/{trading_days['days_required']})
            Drawdown: {drawdown['status']} ({drawdown['drawdown_percent']:.2f}%)
            Profit: {profit['status']} (${profit['current_profit']:.2f})
            """)

            # Check market status
            try:
                # Get current session info
                session_info = self.session_manager.get_current_session_info()
                market_open = len(session_info['active_sessions']) > 0

                # Log detailed market status
                self.logger.info(f"""
                Market Status Check:
                Current Time: {datetime.now()}
                UTC Time: {datetime.now().replace(tzinfo=None)}
                Market Open: {market_open}
                Active Sessions: {session_info['active_sessions'] if market_open else 'None'}
                Session Info: {session_info}
                MT5 Connection: {self.mt5_trader.connected}
                """)

                # Log trading cycle start
                self.logger.info(f"""
                Trading Cycle Status:
                Market Status: {'OPEN' if market_open else 'CLOSED'}
                Active Sessions: {', '.join(session_info['active_sessions']) if market_open else 'None'}
                FTMO Status: {ftmo_status.get('market_status', 'Unknown')}
                """)

                # Check existing positions regardless of market status
                positions = self.position_manager.get_open_positions()
                self.logger.info(f"Checking {len(positions)} positions for FTMO compliance")

                for position in positions:
                    duration_check = self.ftmo_manager.check_position_duration(position)
                    if duration_check.get('needs_closure', False):
                        if not market_open:
                            self.logger.warning(f"""
                            Position Duration Check:
                            Ticket: {position['ticket']}
                            Symbol: {position['symbol']}
                            Duration: {duration_check['duration']}
                            Status: MARKET CLOSED - Cannot close position
                            Action: Will attempt closure when market opens
                            """)
                            self.ftmo_manager.ftmo_logger.log_warning(
                                "Position Duration",
                                f"Cannot close position {position['ticket']} - Market Closed"
                            )
                        else:
                            self.logger.warning(f"""
                            Position Duration Check:
                            Ticket: {position['ticket']}
                            Symbol: {position['symbol']}
                            Duration: {duration_check['duration']}
                            Status: Attempting closure
                            """)
                            success, message = self.mt5_trader.close_trade(position['ticket'])
                            self.logger.info(f"Position closure attempt: {success}, Message: {message}")
                            if not success:
                                self.ftmo_manager.ftmo_logger.log_violation(
                                    "Position Duration",
                                    f"Failed to close position {position['ticket']}: {message}"
                                )

                # If market is closed, only monitor
                if not market_open:
                    self.logger.info("""
                    Market CLOSED - Monitoring Mode:
                    - Position management active
                    - FTMO compliance tracking active
                    - Will resume trading when market opens
                    """)
                    return

                # Run position monitoring if market is open
                self.logger.info("[Trading Loop] Starting position duration monitoring cycle")
                self.trading_logic.monitor_positions()
                self.logger.info("[Trading Loop] Completed position duration monitoring cycle")

                # Process new trades only if market is open
                symbols = self.config.get_setting('favorite_symbols', [])
                for symbol in symbols:
                    try:
                        # Check FTMO position limits
                        positions = self.position_manager.get_open_positions()
                        if len(positions) >= self.trading_logic.max_total_positions:
                            continue

                        # Get and evaluate signals
                        signals = self.signal_manager.get_signals(symbol)
                        if not signals:
                            continue

                        consensus = self.signal_manager.get_consensus_signal(symbol)
                        if not consensus:
                            continue

                        # Prepare and execute trade decision
                        decision = {
                            'symbol': symbol,
                            'signal': consensus,
                            'open_positions': len([p for p in positions if p['symbol'] == symbol])
                        }

                        if self.execute_trade(decision):
                            self.logger.info(f"Trade executed for {symbol}")
                            self.trading_logger.log_trade({
                                'symbol': symbol,
                                'type': consensus.type.value,
                                'entry_price': consensus.entry_price,
                                'stop_loss': consensus.stop_loss,
                                'take_profit': consensus.take_profit,
                                'volume': consensus.volume
                            })

                    except Exception as e:
                        self.logger.error(f"Error processing symbol {symbol}: {str(e)}")
                        continue

                # End of cycle logging
                self.trading_logger.log_system_state()

            except Exception as e:
                self.logger.error(f"Error in market operations: {str(e)}")
                return

        except Exception as e:
            self.logger.error(f"Critical error in trading loop: {str(e)}")

    def _log_market_status(self):
        """Log detailed market status information"""
        try:
            self.logger.info("\n=== Market Status Check ===")
            
            # Get raw session data
            session_data = self.session_manager.calendar_data.get("sessions", {})
            self.logger.info(f"""
            Raw Session Configuration:
            Sydney: {session_data.get('Sydney', 'Not configured')}
            Tokyo: {session_data.get('Tokyo', 'Not configured')}
            London: {session_data.get('London', 'Not configured')}
            NewYork: {session_data.get('NewYork', 'Not configured')}
            """)

            # Get current session status
            current_time = datetime.now()
            utc_time = datetime.now(ZoneInfo("UTC"))
            self.logger.info(f"""
            Time Information:
            Local Time: {current_time}
            UTC Time: {utc_time}
            Weekday: {utc_time.strftime('%A')}
            Hour: {utc_time.hour}
            """)

            # Check MT5 status
            mt5_status = self.mt5_trader.check_connection_health()
            self.logger.info(f"""
            MT5 Status:
            Connected: {mt5_status['is_connected']}
            Can Trade: {mt5_status['can_trade']}
            Terminal Connected: {mt5_status['terminal_connected']}
            Expert Enabled: {mt5_status['expert_enabled']}
            """)

            # Check individual sessions
            for session in ['Sydney', 'Tokyo', 'London', 'NewYork']:
                is_open = self.session_manager.is_session_open(session)
                self.logger.info(f"Session {session}: {'OPEN' if is_open else 'CLOSED'}")

            # Log session manager's current info
            session_info = self.session_manager.get_current_session_info()
            self.logger.info(f"""
            Session Manager Status:
            Active Sessions: {session_info['active_sessions']}
            Upcoming Sessions: {session_info['upcoming_sessions']}
            Market Status: {session_info['market_status']}
            """)

        except Exception as e:
            self.logger.error(f"Error logging market status: {str(e)}")

    def run(self):
        """Main bot loop with auto-refreshing dashboard"""
        try:
            if not self.startup_sequence():
                self.logger.error("Startup sequence failed")
                return

            if not self.mt5_trader.connected:
                self.logger.error("MetaTrader 5 is not connected")
                print("\nError: MetaTrader 5 is not connected. Please:")
                print("1. Make sure MetaTrader 5 is running")
                print("2. Enable AutoTrading")
                print("3. Check your credentials")
                print("4. Restart the bot")
                return

            self.session_manager = MarketSessionManager()
            
            # Set logging levels
            self.logger.setLevel(logging.ERROR)
            self.mt5_trader.logger.setLevel(logging.ERROR)
            self.signal_manager.logger.setLevel(logging.ERROR)
            self.mt5_trader.market_watcher.logger.setLevel(logging.ERROR)
            
            self.status_manager.log_action("Bot started in automated mode")
            
            refresh_interval = 5  # seconds
            last_update = datetime.now().replace(tzinfo=None)
            last_session_check = datetime.now().replace(tzinfo=None)
            session_check_interval = 60  # Check session every minute

            while self.running:
                try:
                    current_time = datetime.now().replace(tzinfo=None)
                    
                    # Session status check (once per minute)
                    if (current_time - last_session_check).total_seconds() >= session_check_interval:
                        self.logger.info(f"""
                        === Session Status Check ===
                        Current Time: {current_time}
                        UTC Time: {datetime.now(ZoneInfo("UTC"))}
                        Session Info: {self.session_manager.get_current_session_info()}
                        """)
                        last_session_check = current_time

                    # Verify market state before processing
                    try:
                        market_open = bool(self.mt5_trader.market_is_open)
                        self.logger.debug(f"Market state check: {'Open' if market_open else 'Closed'}")
                    except Exception as e:
                        self.logger.error(f"Error checking market state: {str(e)}")
                        market_open = False

                    if market_open:
                        try:
                            self.run_trading_loop()
                        except Exception as e:
                            self.logger.error(f"Error in trading loop: {str(e)}", exc_info=True)
                            self.status_manager.update_module_status(
                                "TradingLogic",
                                "ERROR",
                                f"Trading loop error: {str(e)}"
                            )

                    # Dashboard update with error handling
                    try:
                        time_diff = (current_time - last_update).total_seconds()
                        if time_diff >= refresh_interval:
                            self.logger.debug("Updating dashboard...")
                            self.update_dashboard()
                            last_update = current_time
                    except Exception as e:
                        self.logger.error(f"Dashboard update error: {str(e)}", exc_info=True)
                        self.status_manager.update_module_status(
                            "Dashboard",
                            "WARNING",
                            f"Dashboard update failed: {str(e)}"
                        )

                    # Handle keyboard input with type checking
                    if os.name == 'nt':  # Windows
                        if msvcrt.kbhit():
                            try:
                                choice = msvcrt.getch().decode()
                                self.logger.debug(f"Received keyboard input: {choice}")
                                self._handle_user_input(choice)
                            except Exception as e:
                                self.logger.error(f"Error handling keyboard input: {str(e)}")
                    else:  # Unix-like systems
                        i, o, e = select.select([sys.stdin], [], [], 0.1)
                        if i:
                            try:
                                choice = sys.stdin.readline().strip()
                                self.logger.debug(f"Received keyboard input: {choice}")
                                self._handle_user_input(choice)
                            except Exception as e:
                                self.logger.error(f"Error handling keyboard input: {str(e)}")

                    time.sleep(1)  # Reduced polling frequency to 1 second

                except Exception as e:
                    self.logger.error(f"Error in main loop iteration: {str(e)}", exc_info=True)
                    self.status_manager.update_module_status(
                        "MainLoop",
                        "ERROR",
                        f"Main loop error: {str(e)}"
                    )
                    time.sleep(1)  # Prevent rapid error loops

            self.logger.info("Bot stopping...")
            self.status_manager.log_action("Bot stopped")
            mt5.shutdown()

        except Exception as e:
            self.logger.critical(f"Critical error in run method: {str(e)}", exc_info=True)
            self.status_manager.log_action(f"Bot crashed: {str(e)}")
            mt5.shutdown()

    def _handle_user_input(self, choice: str):
        """Handle user input with proper logging"""
        try:
            if choice == '1':
                self.logger.info("User requested logs view")
                self.logger.setLevel(logging.INFO)
                self.mt5_trader.logger.setLevel(logging.INFO)
                self.signal_manager.logger.setLevel(logging.INFO)
                self.mt5_trader.market_watcher.logger.setLevel(logging.INFO)
                self.view_logs()
                self.logger.setLevel(logging.ERROR)
                self.mt5_trader.logger.setLevel(logging.ERROR)
                self.signal_manager.logger.setLevel(logging.ERROR)
                self.mt5_trader.market_watcher.logger.setLevel(logging.ERROR)
            elif choice == '0':
                self.logger.info("User requested bot stop")
                self.running = False
                print("\nStopping Forex Bot...")
                self.status_manager.log_action("Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Error handling user input '{choice}': {str(e)}")


    def execute_trade(self, decision: Dict) -> bool:
        """Execute trading decision"""
        if not decision or not decision['signal']:
            return False
            
        signal = decision['signal']
        symbol = decision['symbol']
        current_positions = decision['open_positions']
        
        if current_positions > 0:
            self.logger.info(f"Already have {current_positions} positions for {symbol}")
            return False
            
        try:
            if signal.type not in [SignalType.BUY, SignalType.SELL]:
                return False
                
            volume = signal.volume or 0.01
            
            success, message = self.mt5_trader.place_trade(
                symbol=symbol,
                order_type=signal.type.value,
                volume=volume,
                price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                comment=f"Auto trade: {signal.type.value}"
            )
            
            if success:
                self.logger.info(f"Successfully executed {signal.type.value} trade for {symbol}")
            else:
                self.logger.error(f"Failed to execute trade: {message}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error executing trade: {str(e)}")
            return False
        
    def _get_next_market_open(self):
        """Calculate next market open time"""
        now = datetime.now()
        if now.weekday() == 5:  # Saturday
            days_to_add = 1
        elif now.weekday() == 6:  # Sunday
            days_to_add = 0
        else:
            days_to_add = 0
        next_open = now.replace(hour=17, minute=0, second=0) + timedelta(days=days_to_add)
        return next_open.strftime("%Y-%m-%d %H:%M:%S ET")
        
    def startup_sequence(self):
        """Run startup checks and display status"""
        try:
            self.logger.info("Starting bot startup sequence...")
            
            print("=" * 50)
            print("Forex Trading Bot - Starting...".center(50))
            print("=" * 50)
            print("\nRunning system audit...")

            self.logger.info("Running system audit...")
            results = self.system_auditor.run_full_audit()
            
            warnings = []
            operational_issues = []
            
            for result in results:
                if result.module_name == "MT5Trader":
                    # Handle MT5 status separately
                    if result.status == "ERROR":
                        warnings.append(result)
                        self.logger.warning(f"MT5 Warning: {result.message}")
                        print(f"[!] MT5 WARNING: {result.message}")
                else:
                    # Handle other modules
                    if result.status == "ERROR":
                        operational_issues.append(result)
                        self.logger.error(f"System Error: {result.message}")
                        print(f"[-] {result.message}")
                    elif result.status == "WARNING":
                        warnings.append(result)
                        self.logger.warning(f"Warning: {result.message}")
                        print(f"[!] WARNING: {result.message}")
                    else:
                        self.logger.info(f"Audit OK: {result.module_name}")
                        print(f"[+] {result.module_name} - OK")

            # Initialize FTMO monitoring
            if self.ftmo_manager:
                if not self.ftmo_manager.initialize_monitoring():
                    warnings.append("FTMO monitoring initialization failed")
                    self.logger.warning("Failed to initialize FTMO monitoring")
                else:
                    self.logger.info("FTMO monitoring initialized successfully")

            # Handle operational issues
            if operational_issues:
                error_messages = [error.message for error in operational_issues]
                log_path = self._create_error_log(error_messages)
                self.logger.critical("Critical system errors found during startup")
                print("\nCRITICAL SYSTEM ERROR(S) FOUND:")
                for error in operational_issues:
                    print(f"- {error.message}")
                if log_path:
                    print(f"\nLogs have been generated at: {log_path}")
                else:
                    print("\nFailed to create error log file.")
                print("Exiting program for safety. Please check logs for details.")
                return False

            # Handle warnings
            if warnings:
                self.logger.warning("Startup warnings found")
                print("\nWarnings found:")
                for warning in warnings:
                    print(f"- {warning.message}")
                    if "market" in warning.message.lower():
                        next_open = self._get_next_market_open()
                        print(f"  * Market opens: {next_open}")
                        print(f"  * Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                try:
                    print("\nPress SPACE to continue or ESC to exit...")
                    while True:
                        if keyboard.is_pressed('space'):
                            self.logger.info("User chose to continue despite warnings")
                            break
                        elif keyboard.is_pressed('esc'):
                            self.logger.info("User chose to exit due to warnings")
                            return False
                        time.sleep(0.1)
                except (ImportError, AttributeError):
                    response = input("\nPress ENTER to continue or type 'exit' to quit: ")
                    if response.lower() == 'exit':
                        self.logger.info("User chose to exit due to warnings")
                        return False

            # Initialize trading mode
            self.status_manager.set_mode('AUTOMATED')
            self.status_manager.start_bot()
            
            # Set up initial trading parameters
            self.trading_logic.max_positions_per_symbol = self.config.get_setting('max_positions_per_symbol', 1)
            self.trading_logic.max_total_positions = self.config.get_setting('max_total_positions', 3)
            self.trading_logic.required_signal_strength = self.config.get_setting('required_signal_strength', 0.7)
            
            # Initialize market data monitoring
            symbols = self.config.get_setting('favorite_symbols', [])
            for symbol in symbols:
                self.mt5_trader.market_watcher.setup_price_alert(
                    symbol=symbol,
                    price=0,  # Will be updated with current price
                    condition=">",
                    callback=None
                )
            
            # Log successful startup
            self.logger.info("Startup sequence completed successfully")
            self.status_manager.log_action("Bot initialized and ready for trading")
            
            return True
                
        except Exception as e:
            self.logger.error(f"Error during startup sequence: {str(e)}")
            print(f"\nError during startup: {str(e)}")
            return False

    def view_logs(self):
        """Display recent trading logs"""
        self.menu.print_header("Recent Trading Logs")
        
        try:
            log_dir = "trading_logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            log_files = []
            for file in os.listdir(log_dir):
                if file.endswith('.log'):
                    file_path = os.path.join(log_dir, file)
                    log_files.append((file, os.path.getmtime(file_path)))
                    
            log_files.sort(key=lambda x: x[1], reverse=True)
            
            if not log_files:
                print("No log files found.")
                self.menu.wait_for_enter()
                return
                
            print("\nMost recent log files:")
            for i, (log_file, _) in enumerate(log_files[:5], 1):
                print(f"{i}. {log_file}")
                
            choice = input("\nEnter number to view log (or Enter to return): ")
            if not choice:
                return
                
            try:
                index = int(choice) - 1
                if 0 <= index < len(log_files):
                    log_path = os.path.join(log_dir, log_files[index][0])
                    with open(log_path, 'r') as f:
                        print("\n" + "=" * 50)
                        print(f"Log File: {log_files[index][0]}")
                        print("=" * 50 + "\n")
                        print(f.read())
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")
                
        except Exception as e:
            print(f"Error viewing logs: {str(e)}")
            
        self.menu.wait_for_enter()

def main():
    if not mt5.initialize():
        print("Failed to initialize MT5. Error:", mt5.last_error())
        return

    bot = ForexBot()
    bot.run()

    mt5.shutdown()

if __name__ == "__main__":
    main()