import logging
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

    def _initialize_system_auditor(self):
        """Initialize system auditor with proper dependencies"""
        try:
            system_auditor = SystemAuditor(config_manager=self.config)
            self.logger.info("System auditor initialized")
            return system_auditor
        except Exception as e:
            self.logger.error(f"Failed to initialize system auditor: {str(e)}")
            return None
    
    def update_dashboard(self):
        """Update and display the dashboard with improved session and position timing information"""
        self.menu.clear_screen()

        print("=" * 50)
        print("Forex Trading Bot - Live Dashboard".center(50))
        print("=" * 50)
        print()

        status = self.status_manager.get_bot_status()
        print(f"System Status: {status['bot_status']['mode']}")
        print()

        session_info = self.session_manager.get_current_session_info()
        
        if session_info['active_sessions']:
            print(f"Current Sessions: {', '.join(session_info['active_sessions'])}")
        else:
            print("Current Sessions: No Major Markets Open")

        print("Next Sessions:")
        for next_session in session_info['upcoming_sessions']:
            print(f"- {next_session['name']} opens in {next_session['opens_in']}")
        print()

        print("Trading Signals:")
        print("-" * 50)
        print(f"{'Symbol':<8} {'Direction':<8} {'Strength':<8} {'Price':<12}")
        print("-" * 50)

        symbols = self.signal_manager.config_manager.get_setting('favorite_symbols', [])
        for symbol in symbols:
            signals = self.signal_manager.get_signals(symbol)
            if signals:
                consensus = self.signal_manager.get_consensus_signal(symbol)
                if consensus:
                    tick = mt5.symbol_info_tick(symbol)
                    price = f"{tick.bid:.5f}" if tick else "N/A"
                    print(f"{symbol:<8} {consensus.type.value:<8} {'Strong':<8} {price:<12}")

        positions = self.position_manager.get_open_positions()
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

        account_info = self.mt5_trader.get_account_info()
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

    def run_trading_loop(self):
        """Main trading loop logic"""
        try:
            if not self.mt5_trader.market_is_open:
                return
                
            # Run position monitoring first - Added explicit logging
            self.logger.info("[Trading Loop] Starting position duration monitoring cycle")
            self.trading_logic.monitor_positions()
            self.logger.info("[Trading Loop] Completed position duration monitoring cycle")
                
            symbols = self.config.get_setting('favorite_symbols', [])
            
            for symbol in symbols:
                try:
                    positions = self.position_manager.get_open_positions()
                    if len(positions) >= self.trading_logic.max_total_positions:
                        continue
                        
                    signals = self.signal_manager.get_signals(symbol)
                    if not signals:
                        continue
                        
                    consensus = self.signal_manager.get_consensus_signal(symbol)
                    if not consensus:
                        continue
                        
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
                    
            self.trading_logger.log_system_state()
            
        except Exception as e:
            self.logger.error(f"Error in trading loop: {str(e)}")

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
            connection_check_interval = 30  # Check connection every 30 seconds
            last_connection_check = datetime.now().replace(tzinfo=None)

            while self.running:
                try:
                    current_time = datetime.now().replace(tzinfo=None)
                    
                    # Periodic connection check
                    if (current_time - last_connection_check).total_seconds() >= connection_check_interval:
                        if not self.mt5_trader.connected:
                            self.logger.error("MT5 connection lost. Attempting reconnection...")
                            # Try to reconnect
                            if not self.mt5_trader._attempt_reconnection():
                                self.logger.error("Failed to reconnect to MT5")
                                continue
                        last_connection_check = current_time
                        self.logger.info("Connection check completed")

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

                    time.sleep(0.1)

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