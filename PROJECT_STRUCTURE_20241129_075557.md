# Project Documentation

Generated on: 2024-11-29 07:55:57

## Directory Structure
forex
├── .pytest_cache/
│   ├── v/
│   │   └── cache/
│   │       ├── lastfailed
│   │       ├── nodeids
│   │       └── stepwise
│   ├── .gitignore
│   ├── CACHEDIR.TAG
│   └── README.md
├── config/
│   ├── ftmo_rules.json
│   ├── market_calendar.json
│   └── settings.json
├── core/
│   ├── __init__.py
│   ├── bot_status_manager.py
│   ├── config_manager.py
│   ├── ftmo_rule_manager.py
│   ├── market_session_manager.py
│   ├── menu_manager.py
│   ├── mt5_trader.py
│   ├── position_manager.py
│   ├── system_auditor.py
│   └── trading_logic.py
├── signals/
│   ├── __init__.py
│   ├── moving_average_provider.py
│   ├── signal_evaluator.py
│   ├── signal_manager.py
│   └── signal_provider.py
├── tests/
│   └── __init__.py
├── trading_logs/
│   ├── forexbot_20241129_071541.log
│   ├── forexbot_20241129_071651.log
│   ├── forexbot_20241129_072215.log
│   ├── mt5trader_20241129_071541.log
│   ├── mt5trader_20241129_071651.log
│   ├── mt5trader_20241129_072215.log
│   ├── trading_activity_20241129_071543.log
│   ├── trading_activity_20241129_071653.log
│   ├── trading_activity_20241129_072217.log
│   ├── trading_session_20241129_071541.log
│   ├── trading_session_20241129_071651.log
│   ├── trading_session_20241129_072215.log
│   ├── tradinglogger_20241129_071543.log
│   ├── tradinglogger_20241129_071653.log
│   └── tradinglogger_20241129_072217.log
├── PROJECT_STRUCTURE_20241129_075557.md
├── config.json
├── forex_bot.py
├── generate_file_structure.py
├── logger_config.py
├── market_watcher.py
├── notes
├── run_tests.py
└── trading_logger.py

## File Contents


### config.json (82.00 B)

```json
{"username": "61294775", "password": "Jarelis@2024", "server": "Pepperstone-Demo"}
```

### forex_bot.py (27.39 KB)

```py
import logging
import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import msvcrt  # for Windows
import select
import sys
from core.mt5_trader import MT5Trader
from core.position_manager import PositionManager
from core.config_manager import ConfigManager
from core.menu_manager import MenuManager
from core.trading_logic import TradingLogic
from signals.signal_manager import SignalManager
from signals.signal_provider import SignalType
from core.system_auditor import SystemAuditor
from core.bot_status_manager import BotStatusManager
from core.ftmo_rule_manager import FTMORuleManager
from trading_logger import TradingLogger 
from core.market_session_manager import MarketSessionManager
from signals.signal_evaluator import SignalEvaluator
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
            self.trading_logic = TradingLogic(self.mt5_trader, self.signal_manager, self.position_manager)
            self.logger.info("Trading logic initialized")

            # Update signal manager with trading logic and initialize evaluator
            self.signal_manager.trading_logic = self.trading_logic
            self.signal_manager.signal_evaluator = SignalEvaluator(self.signal_manager, self.trading_logic)

            # Initialize menu and other components
            self.menu = self._initialize_menu_manager()
            self.system_auditor = self._initialize_system_auditor()
            if not self.system_auditor:
                raise RuntimeError("Failed to initialize system auditor")
            self.trading_logger = TradingLogger(self.mt5_trader, self.position_manager, self.signal_manager, self.config)
            
            self.running = True
            self.logger.info("ForexBot initialization completed successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize ForexBot: {str(e)}")
            raise RuntimeError(f"Bot initialization failed: {str(e)}")

    def _setup_logging(self):
        from logger_config import setup_logger
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
```

### generate_file_structure.py (10.28 KB)

```py
import os
import sys
from datetime import datetime
from typing import Set, Optional
import argparse
import logging

class ProjectDocumentGenerator:
    def __init__(
        self,
        base_path: str,
        output_file: str,
        ignored_dirs: Optional[Set[str]] = None,
        text_extensions: Optional[Set[str]] = None,
        max_file_size: int = 10 * 1024 * 1024  # 10 MB
    ):
        self.base_path = os.path.abspath(base_path)
        self.output_file = os.path.abspath(output_file)
        self.ignored_dirs = ignored_dirs or {'venv', '__pycache__', '.git', 'node_modules'}
        self.text_extensions = text_extensions or {
            '.py', '.txt', '.md', '.json', '.yaml', '.yml',
            '.js', '.jsx', '.ts', '.tsx', '.css', '.scss',
            '.html', '.htm', '.xml', '.csv', '.ini', '.cfg'
        }
        self.stats = {
            'total_files': 0,
            'text_files': 0,
            'binary_files': 0,
            'total_size': 0
        }

        # Store the output file's relative path to base_path
        if os.path.commonpath([self.output_file, self.base_path]) == self.base_path:
            self.output_file_rel = os.path.relpath(self.output_file, self.base_path)
        else:
            self.output_file_rel = None  # Output file is outside base_path

        self.max_file_size = max_file_size  # Maximum file size to include (in bytes)

    def format_size(self, size: int) -> str:
        """Convert size in bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    def is_text_file(self, filename: str) -> bool:
        """Determine if a file is a text file based on its extension."""
        return os.path.splitext(filename)[1].lower() in self.text_extensions

    def generate_documentation(self):
        """Generate the project documentation."""
        with open(self.output_file, 'w', encoding='utf-8') as doc:
            # Write header
            doc.write("# Project Documentation\n\n")
            doc.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Write base directory name
            base_dir_name = os.path.basename(self.base_path)
            doc.write(f"## Directory Structure\n{base_dir_name}\n")
            tree_lines = []
            self._generate_directory_structure(self.base_path, tree_lines, prefix="")
            doc.writelines(tree_lines)

            # Generate file contents
            doc.write("\n## File Contents\n\n")
            self._generate_file_contents(doc)

            # Write statistics
            self._write_statistics(doc)

    def _generate_directory_structure(self, current_path: str, tree_lines: list, prefix: str):
        """Recursively generate the directory structure."""
        # Get list of directories and files
        try:
            entries = os.listdir(current_path)
        except PermissionError as e:
            logging.warning(f"Permission denied: {current_path}")
            return
        except Exception as e:
            logging.warning(f"Error accessing {current_path}: {e}")
            return

        # Separate directories and files, excluding ignored directories
        dirs = [d for d in entries if os.path.isdir(os.path.join(current_path, d)) and d not in self.ignored_dirs]
        files = [f for f in entries if os.path.isfile(os.path.join(current_path, f))]

        # Sort directories and files for consistent ordering
        dirs.sort()
        files.sort()

        # Combine directories and files
        all_entries = dirs + files
        total_entries = len(all_entries)

        for index, entry in enumerate(all_entries):
            path = os.path.join(current_path, entry)
            is_last = index == (total_entries - 1)
            connector = "└── " if is_last else "├── "
            if os.path.isdir(path):
                # Append directory name with connector
                tree_lines.append(f"{prefix}{connector}{entry}/\n")
                # Determine the new prefix for the next level
                new_prefix = prefix + ("    " if is_last else "│   ")
                # Recursive call
                self._generate_directory_structure(path, tree_lines, new_prefix)
            else:
                # Append file name with connector
                tree_lines.append(f"{prefix}{connector}{entry}\n")

    def _generate_file_contents(self, doc_file):
        """Generate the contents of each file in a separate section."""
        for root, dirs, files in os.walk(self.base_path):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]

            for file in sorted(files):
                file_path = os.path.join(root, file)

                # Skip the output file if it's inside base_path
                if self.output_file_rel and os.path.normpath(os.path.relpath(file_path, self.base_path)) == os.path.normpath(self.output_file_rel):
                    logging.info(f"Skipping output file from file contents: {file_path}")
                    continue

                try:
                    file_size = os.path.getsize(file_path)
                except OSError as e:
                    logging.warning(f"Cannot access file {file_path}: {e}")
                    continue

                rel_path = os.path.relpath(file_path, self.base_path)

                # Update statistics
                self.stats['total_files'] += 1
                self.stats['total_size'] += file_size

                doc_file.write(f"\n### {rel_path} ({self.format_size(file_size)})\n\n")

                if self.is_text_file(file):
                    self.stats['text_files'] += 1
                    if file_size > self.max_file_size:
                        doc_file.write("*File too large to display.*\n")
                        logging.info(f"Skipped large file: {file_path}")
                        continue
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            doc_file.write("```")
                            # Specify language based on file extension for syntax highlighting
                            lang = os.path.splitext(file)[1][1:]
                            if lang:
                                doc_file.write(lang)
                            doc_file.write("\n")
                            doc_file.write(content)
                            doc_file.write("\n```\n")
                    except Exception as e:
                        doc_file.write(f"Error reading file: {str(e)}\n")
                        logging.error(f"Error reading file {file_path}: {e}")
                else:
                    self.stats['binary_files'] += 1
                    doc_file.write("*Binary or unsupported file format*\n")

    def _write_statistics(self, doc_file):
        """Write project statistics."""
        doc_file.write("\n## Project Statistics\n\n")
        doc_file.write(f"- Total Files: {self.stats['total_files']}\n")
        doc_file.write(f"- Text Files: {self.stats['text_files']}\n")
        doc_file.write(f"- Binary Files: {self.stats['binary_files']}\n")
        doc_file.write(f"- Total Size: {self.format_size(self.stats['total_size'])}\n")

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate project documentation.")
    parser.add_argument(
        "base_path",
        nargs='?',
        default=".",
        help="Base directory of the project to document."
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=".",
        help="Output directory for the Markdown file."
    )
    parser.add_argument(
        "-i", "--ignore",
        nargs='*',
        default=['venv', '__pycache__', '.git', 'node_modules'],
        help="List of directories to ignore."
    )
    parser.add_argument(
        "-e", "--extensions",
        nargs='*',
        default=[
            '.py', '.txt', '.md', '.json', '.yaml', '.yml',
            '.js', '.jsx', '.ts', '.tsx', '.css', '.scss',
            '.html', '.htm', '.xml', '.csv', '.ini', '.cfg'
        ],
        help="List of file extensions to consider as text files."
    )
    parser.add_argument(
        "-m", "--max-size",
        type=int,
        default=10 * 1024 * 1024,  # 10 MB
        help="Maximum file size (in bytes) to include content."
    )
    parser.add_argument(
        "--verbose",
        action='store_true',
        help="Enable verbose logging."
    )
    return parser.parse_args()

def setup_logging(verbose: bool):
    """Configure logging settings."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='[%(levelname)s] %(message)s'
    )

def generate_timestamped_filename(base_dir: str, base_name: str = "PROJECT_STRUCTURE", extension: str = "md") -> str:
    """Generate a filename with the current date and time appended."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{base_name}_{timestamp}.{extension}"
    return os.path.join(base_dir, filename)

def main():
    """Main function to run the documentation generator."""
    args = parse_arguments()
    setup_logging(args.verbose)

    try:
        # Generate a unique output file name with timestamp
        output_file = generate_timestamped_filename(args.output_dir)

        generator = ProjectDocumentGenerator(
            base_path=args.base_path,
            output_file=output_file,
            ignored_dirs=set(args.ignore),
            text_extensions=set(args.extensions),
            max_file_size=args.max_size
        )
        generator.generate_documentation()
        print(f"\nDocumentation generated successfully!")
        print(f"Output file: {os.path.abspath(generator.output_file)}")
    except ValueError as ve:
        logging.error(ve)
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

```

### logger_config.py (2.18 KB)

```py
import logging
from datetime import datetime
import os
from typing import Optional

def setup_logger(name: str, log_dir: str = 'trading_logs') -> logging.Logger:
    """
    Standardized logger setup for all components
    
    Args:
        name: Logger name (e.g., 'ForexBot', 'MT5Trader')
        log_dir: Directory for log files
        
    Returns:
        logging.Logger: Configured logger instance
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
        
    # Create timestamp for this session
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        # Console Handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        
        # File Handler
        log_file = os.path.join(log_dir, f'{name.lower()}_{timestamp}.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s\n'
            'File: %(filename)s:%(lineno)d\n'
            'Function: %(funcName)s\n'
            '----------------------------------------'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        
        # Add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        
        # Log initial setup
        logger.info(f"Logger initialized for {name}")
        logger.info(f"Detailed logs will be saved to: {log_file}")
        
        return logger
        
    except Exception as e:
        # Fallback basic logger if something goes wrong
        logging.basicConfig(level=logging.INFO)
        basic_logger = logging.getLogger(name)
        basic_logger.error(f"Error setting up logger: {str(e)}")
        return basic_logger
```

### market_watcher.py (10.25 KB)

```py
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
```

### notes (37.00 B)

*Binary or unsupported file format*

### run_tests.py (573.00 B)

```py
import unittest
import logging

def run_tests():
    # Suppress logging output during tests
    logging.getLogger().setLevel(logging.CRITICAL)

    # Discover all tests in the 'tests' directory
    loader = unittest.TestLoader()
    suite = loader.discover('tests')

    # Open a file to write the test results
    with open('test_results.txt', 'w') as f:
        # Create a test runner that writes to the file
        runner = unittest.TextTestRunner(stream=f, verbosity=2)
        result = runner.run(suite)

if __name__ == '__main__':
    run_tests()

```

### trading_logger.py (7.49 KB)

```py
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
    
    def __init__(self, mt5_trader, position_manager, signal_manager, config_manager):
        """
        Initialize Trading Logger
        
        Args:
            mt5_trader: MT5Trader instance
            position_manager: PositionManager instance
            signal_manager: SignalManager instance
            config_manager: ConfigManager instance
        """
        self.mt5_trader = mt5_trader
        self.position_manager = position_manager
        self.signal_manager = signal_manager
        self.config_manager = config_manager
        
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

            # Get open positions
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
                
                # Position Information
                f.write("\nOPEN POSITIONS:\n")
                if positions:
                    for pos in positions:
                        f.write(f"Symbol: {pos['symbol']}\n")
                        f.write(f"  Type: {pos['type']}\n")
                        f.write(f"  Volume: {pos['volume']}\n")
                        f.write(f"  Open Price: {pos['open_price']}\n")
                        f.write(f"  Current Price: {pos['current_price']}\n")
                        f.write(f"  Profit: ${pos['profit']:.2f}\n")
                        f.write(f"  Pips: {pos['pips']:.1f}\n")
                else:
                    f.write("No open positions\n")
                
                # Signal Information
                f.write("\nSIGNAL STATUS:\n")
                for symbol in self.config_manager.get_setting('favorite_symbols', []):
                    signals = self.signal_manager.get_signals(symbol)
                    f.write(f"{symbol}:\n")
                    if signals:
                        for signal in signals:
                            f.write(f"  Type: {signal.type.value}\n")
                            f.write(f"  Entry: {signal.entry_price}\n")
                            f.write(f"  SL: {signal.stop_loss}\n")
                            f.write(f"  TP: {signal.take_profit}\n")
                            f.write(f"  Time: {signal.timestamp}\n")
                    else:
                        f.write("  No active signals\n")
                
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
```

### .pytest_cache\.gitignore (39.00 B)

*Binary or unsupported file format*

### .pytest_cache\CACHEDIR.TAG (191.00 B)

*Binary or unsupported file format*

### .pytest_cache\README.md (310.00 B)

```md
# pytest cache directory #

This directory contains data from the pytest's cache plugin,
which provides the `--lf` and `--ff` options, as well as the `cache` fixture.

**Do not** commit this to version control.

See [the docs](https://docs.pytest.org/en/stable/how-to/cache.html) for more information.

```

### .pytest_cache\v\cache\lastfailed (123.00 B)

*Binary or unsupported file format*

### .pytest_cache\v\cache\nodeids (2.12 KB)

*Binary or unsupported file format*

### .pytest_cache\v\cache\stepwise (2.00 B)

*Binary or unsupported file format*

### config\ftmo_rules.json (730.00 B)

```json
{
    "account_type": "100k",
    "trading_rules": {
        "max_daily_loss": -5000,
        "max_total_loss": -10000,
        "profit_target": 10000,
        "max_positions": 3,
        "scaling_rules": {
            "initial_lots": 0.01,
            "max_lots": 1.0
        }
    },
    "time_rules": {
        "max_position_duration": 120, 
        "restricted_hours": {
            "start": "22:00",
            "end": "23:00"
        }
    },
    "risk_parameters": {
        "max_risk_per_trade": 1.0,  
        "position_scaling": false,
        "max_correlation_positions": 2
    },
    "monitoring": {
        "warning_threshold_daily": -4000,
        "warning_threshold_total": -8000
    }
}
```

### config\market_calendar.json (3.61 KB)

```json
{
    "sessions": {
        "Sydney": {
            "open": "21:00",
            "close": "06:00",
            "timezone": "UTC"
        },
        "Tokyo": {
            "open": "00:00",
            "close": "09:00",
            "timezone": "UTC"
        },
        "London": {
            "open": "08:00",
            "close": "17:00",
            "timezone": "UTC"
        },
        "NewYork": {
            "open": "13:00",
            "close": "22:00",
            "timezone": "UTC"
        }
    },
    "holidays": {
        "2024": {
            "NewYork": [
                {"date": "2024-01-01", "name": "New Year's Day"},
                {"date": "2024-01-15", "name": "Martin Luther King Jr. Day"},
                {"date": "2024-02-19", "name": "Presidents Day"},
                {"date": "2024-03-29", "name": "Good Friday"},
                {"date": "2024-05-27", "name": "Memorial Day"},
                {"date": "2024-06-19", "name": "Juneteenth"},
                {"date": "2024-07-04", "name": "Independence Day"},
                {"date": "2024-09-02", "name": "Labor Day"},
                {"date": "2024-11-28", "name": "Thanksgiving Day"},
                {"date": "2024-12-25", "name": "Christmas Day"}
            ],
            "London": [
                {"date": "2024-01-01", "name": "New Year's Day"},
                {"date": "2024-03-29", "name": "Good Friday"},
                {"date": "2024-04-01", "name": "Easter Monday"},
                {"date": "2024-05-06", "name": "Early May Bank Holiday"},
                {"date": "2024-05-27", "name": "Spring Bank Holiday"},
                {"date": "2024-08-26", "name": "Summer Bank Holiday"},
                {"date": "2024-12-25", "name": "Christmas Day"},
                {"date": "2024-12-26", "name": "Boxing Day"}
            ],
            "Tokyo": [
                {"date": "2024-01-01", "name": "New Year's Day"},
                {"date": "2024-01-02", "name": "Bank Holiday"},
                {"date": "2024-01-03", "name": "Bank Holiday"},
                {"date": "2024-01-08", "name": "Coming of Age Day"},
                {"date": "2024-02-11", "name": "National Foundation Day"},
                {"date": "2024-02-23", "name": "Emperor's Birthday"},
                {"date": "2024-03-20", "name": "Vernal Equinox"},
                {"date": "2024-04-29", "name": "Showa Day"},
                {"date": "2024-05-03", "name": "Constitution Day"},
                {"date": "2024-05-04", "name": "Greenery Day"},
                {"date": "2024-05-05", "name": "Children's Day"},
                {"date": "2024-07-15", "name": "Marine Day"},
                {"date": "2024-08-11", "name": "Mountain Day"},
                {"date": "2024-09-16", "name": "Respect for the Aged Day"},
                {"date": "2024-09-23", "name": "Autumn Equinox"},
                {"date": "2024-10-14", "name": "Sports Day"},
                {"date": "2024-11-03", "name": "Culture Day"},
                {"date": "2024-11-23", "name": "Labor Thanksgiving Day"}
            ],
            "Sydney": [
                {"date": "2024-01-01", "name": "New Year's Day"},
                {"date": "2024-01-26", "name": "Australia Day"},
                {"date": "2024-03-29", "name": "Good Friday"},
                {"date": "2024-04-01", "name": "Easter Monday"},
                {"date": "2024-04-25", "name": "ANZAC Day"},
                {"date": "2024-06-10", "name": "King's Birthday"},
                {"date": "2024-12-25", "name": "Christmas Day"},
                {"date": "2024-12-26", "name": "Boxing Day"}
            ]
        }
    }
}
```

### config\settings.json (319.00 B)

```json
{
    "default_symbol": "EURUSD",
    "default_volume": 0.01,
    "default_sl_pips": 50,
    "default_tp_pips": 100,
    "risk_percent": 1.0,
    "favorite_symbols": [
        "EURUSD",
        "GBPUSD",
        "USDJPY"
    ],
    "last_modified": "2024-11-29 07:22:26",
    "test_setting": "test_value"
}
```

### core\__init__.py (0.00 B)

```py

```

### core\bot_status_manager.py (6.06 KB)

```py
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
import logging

@dataclass
class ModuleStatus:
    """Status information for a single module"""
    name: str
    status: str  # 'OK', 'WARNING', 'ERROR'
    last_update: datetime
    details: Optional[Dict] = None
    message: Optional[str] = None

@dataclass
class BotStatus:
    """Overall bot status information"""
    is_active: bool
    mode: str  # 'AUTOMATED', 'MANUAL'
    started_at: datetime
    last_action_time: Optional[datetime] = None
    last_action: Optional[str] = None
    current_operation: Optional[str] = None
    error_count: int = 0
    warnings_count: int = 0

class BotStatusManager:
    """Manages and tracks the status of all bot components"""
    
    def __init__(self, config_manager=None):
        """Initialize Bot Status Manager"""
        self.config_manager = config_manager
        self._setup_logging()
        self.bot_status = BotStatus(
            is_active=False,
            mode='AUTOMATED',  # Change default mode to AUTOMATED
            started_at=datetime.now()
        )
        self.module_statuses: Dict[str, ModuleStatus] = {}
        self.activity_log: List[str] = []
        
    def _setup_logging(self):
        """Setup logging for status manager"""
        self.logger = logging.getLogger('BotStatusManager')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def start_bot(self):
        """Mark bot as active"""
        self.bot_status.is_active = True
        self.bot_status.started_at = datetime.now()
        self._log_activity("Bot started")
        self.logger.info("Bot started")

    def stop_bot(self):
        """Mark bot as inactive"""
        self.bot_status.is_active = False
        self._log_activity("Bot stopped")
        self.logger.info("Bot stopped")

    def set_mode(self, mode: str):
        """Set bot operation mode"""
        if mode not in ['AUTOMATED', 'MANUAL']:
            raise ValueError("Invalid mode. Must be 'AUTOMATED' or 'MANUAL'")
        self.bot_status.mode = mode
        self._log_activity(f"Mode changed to {mode}")
        self.logger.info(f"Bot mode changed to {mode}")

    def update_module_status(self, module_name: str, status: str, message: str = None, details: Dict = None):
        """Update status for a specific module"""
        self.module_statuses[module_name] = ModuleStatus(
            name=module_name,
            status=status,
            last_update=datetime.now(),
            message=message,
            details=details
        )
        
        if status == 'ERROR':
            self.bot_status.error_count += 1
        elif status == 'WARNING':
            self.bot_status.warnings_count += 1
            
        self.logger.info(f"Module {module_name} status updated: {status}")

    def log_action(self, action: str, operation: str = None):
        """Log bot action"""
        self.bot_status.last_action = action
        self.bot_status.last_action_time = datetime.now()
        if operation:
            self.bot_status.current_operation = operation
        self._log_activity(action)
        self.logger.info(f"Action logged: {action}")

    def _log_activity(self, activity: str):
        """Add activity to log with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"{timestamp} - {activity}"
        self.activity_log.append(log_entry)
        
        # Keep only last 1000 entries
        if len(self.activity_log) > 1000:
            self.activity_log = self.activity_log[-1000:]

    def get_bot_status(self) -> Dict:
        """Get comprehensive bot status report"""
        return {
            'bot_status': {
                'active': self.bot_status.is_active,
                'mode': self.bot_status.mode,
                'uptime': (datetime.now() - self.bot_status.started_at).total_seconds(),
                'last_action': self.bot_status.last_action,
                'last_action_time': self.bot_status.last_action_time,
                'current_operation': self.bot_status.current_operation,
                'error_count': self.bot_status.error_count,
                'warnings_count': self.bot_status.warnings_count
            },
            'module_statuses': {
                name: {
                    'status': status.status,
                    'last_update': status.last_update,
                    'message': status.message,
                    'details': status.details
                }
                for name, status in self.module_statuses.items()
            },
            'recent_activity': self.activity_log[-10:]  # Last 10 activities
        }

    def get_module_status(self, module_name: str) -> Optional[ModuleStatus]:
        """Get status for specific module"""
        return self.module_statuses.get(module_name)

    def get_activity_log(self, limit: int = 100) -> List[str]:
        """Get recent activity log entries"""
        return self.activity_log[-limit:]

    def clear_error_counts(self):
        """Reset error and warning counts"""
        self.bot_status.error_count = 0
        self.bot_status.warnings_count = 0
        self._log_activity("Error counts cleared")
        self.logger.info("Error counts cleared")

    def is_healthy(self) -> bool:
        """Check if bot is in a healthy state"""
        if not self.bot_status.is_active:
            return False
            
        # Check for recent errors
        if self.bot_status.error_count > 0:
            return False
            
        # Check module statuses
        for status in self.module_statuses.values():
            if status.status == 'ERROR':
                return False
            
        return True
```

### core\config_manager.py (3.90 KB)

```py
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime

class ConfigManager:
    def __init__(self, config_dir: str = "config"):
        """
        Initialize Configuration Manager
        
        Args:
            config_dir (str): Directory to store configuration files
        """
        self.config_dir = config_dir
        self.settings_file = os.path.join(config_dir, "settings.json")
        self.credentials_file = os.path.join(config_dir, "credentials.json")
        
        # Create config directory if it doesn't exist
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        # Load or create default settings
        self.settings = self._load_or_create_settings()

    def _load_or_create_settings(self) -> Dict:
        """Load existing settings or create with defaults"""
        default_settings = {
            'default_symbol': 'EURUSD',
            'default_volume': 0.01,
            'default_sl_pips': 50,
            'default_tp_pips': 100,
            'risk_percent': 1.0,
            'favorite_symbols': ['EURUSD', 'GBPUSD', 'USDJPY'],
            'last_modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return default_settings
        else:
            self.save_settings(default_settings)
            return default_settings

    def save_settings(self, settings: Dict) -> bool:
        """Save settings to file"""
        try:
            settings['last_modified'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            self.settings = settings
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get specific setting value"""
        return self.settings.get(key, default)

    def update_setting(self, key: str, value: Any) -> bool:
        """Update specific setting"""
        self.settings[key] = value
        return self.save_settings(self.settings)

    def get_credentials(self) -> Optional[Dict]:
        """Get MT5 credentials if they exist"""
        if os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return None
        return None

    def save_credentials(self, credentials: Dict) -> bool:
        """Save MT5 credentials"""
        try:
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f)
            return True
        except Exception as e:
            print(f"Error saving credentials: {e}")
            return False

    def clear_credentials(self) -> bool:
        """Remove saved credentials"""
        try:
            if os.path.exists(self.credentials_file):
                os.remove(self.credentials_file)
            return True
        except Exception as e:
            print(f"Error clearing credentials: {e}")
            return False

    def get_all_settings(self) -> Dict:
        """Get all settings"""
        return self.settings.copy()

    def reset_to_defaults(self) -> bool:
        """Reset settings to defaults"""
        try:
            if os.path.exists(self.settings_file):
                os.remove(self.settings_file)
            self.settings = self._load_or_create_settings()
            return True
        except Exception as e:
            print(f"Error resetting settings: {e}")
            return False
```

### core\ftmo_rule_manager.py (4.43 KB)

```py
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

class FTMORuleManager:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.rules_file = os.path.join(config_dir, "ftmo_rules.json")
        self.rules = self._load_rules()
        self._setup_logging()
        self.daily_stats = {
            'total_profit': 0,
            'positions_opened': 0,
            'max_drawdown': 0
        }
        self.last_reset = datetime.now()

    def _setup_logging(self):
        self.logger = logging.getLogger('FTMORuleManager')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _load_rules(self) -> Dict:
        try:
            with open(self.rules_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise RuntimeError("FTMO rules configuration file not found")

    def check_position_allowed(self, account_info: Dict, position_size: float) -> tuple[bool, str]:
        if account_info['profit'] <= self.rules['trading_rules']['max_daily_loss']:
            return False, "Daily loss limit reached"

        if account_info['balance'] <= self.rules['trading_rules']['max_total_loss']:
            return False, "Total loss limit reached"

        if position_size > self.rules['trading_rules']['scaling_rules']['max_lots']:
            return False, "Position size exceeds maximum allowed"

        return True, "Position allowed"

    def get_position_metrics(self, position: Dict) -> Dict:
        """Calculate position metrics with proper timestamp handling"""
        try:
            # Handle timestamp conversion
            if isinstance(position['time'], str):
                # If it's already a datetime string, parse it
                try:
                    open_time = datetime.strptime(position['time'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # If the format is different, try to convert from timestamp string
                    open_time = datetime.fromtimestamp(float(position['time']))
            else:
                # If it's already a number (int or float)
                open_time = datetime.fromtimestamp(position['time'])
            
            current_time = datetime.now()
            duration = current_time - open_time
            
            total_minutes = int(duration.total_seconds() / 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            duration_str = f"{hours}h {minutes}m"

            max_duration = self.rules['time_rules']['max_position_duration']
            within_limit = total_minutes <= max_duration

            return {
                'duration': duration_str,
                'open_time': open_time.strftime('%H:%M:%S'),
                'within_time_limit': within_limit,
                'total_minutes': total_minutes
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating position metrics: {str(e)}")
            return {
                'duration': "0h 0m",
                'open_time': "00:00:00",
                'within_time_limit': True,
                'total_minutes': 0
            }

    def monitor_daily_performance(self, account_info: Dict):
        current_time = datetime.now()
        
        if current_time.date() > self.last_reset.date():
            self.daily_stats = {
                'total_profit': 0,
                'positions_opened': 0,
                'max_drawdown': 0
            }
            self.last_reset = current_time

        self.daily_stats['total_profit'] = account_info['profit']
        if account_info['profit'] < self.daily_stats['max_drawdown']:
            self.daily_stats['max_drawdown'] = account_info['profit']

        if account_info['profit'] <= self.rules['monitoring']['warning_threshold_daily']:
            self.logger.warning("Approaching daily loss limit")
        if account_info['balance'] <= self.rules['monitoring']['warning_threshold_total']:
            self.logger.warning("Approaching total loss limit")
```

### core\market_session_manager.py (4.33 KB)

```py
import json
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
import os

class MarketSessionManager:
    def __init__(self, config_dir: str = "config"):
        """Initialize market session manager with calendar data"""
        self.config_dir = config_dir
        self.calendar_file = os.path.join(config_dir, "market_calendar.json")
        self.calendar_data = self._load_calendar()
        self.sessions = self.calendar_data.get("sessions", {})
        self.holidays = self.calendar_data.get("holidays", {})

    def _load_calendar(self) -> Dict:
        """Load market calendar from JSON file"""
        try:
            with open(self.calendar_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"sessions": {}, "holidays": {}}

    def is_holiday(self, session: str, date: Optional[datetime] = None) -> bool:
        """Check if given date is a holiday for the specified session"""
        if date is None:
            date = datetime.now()

        year = str(date.year)
        date_str = date.strftime("%Y-%m-%d")

        if year in self.holidays and session in self.holidays[year]:
            return any(holiday["date"] == date_str 
                      for holiday in self.holidays[year][session])
        return False

    def is_session_open(self, session: str) -> bool:
        """Check if a trading session is currently open"""
        if session not in self.sessions:
            return False

        now = datetime.now(ZoneInfo("UTC"))
        
        # Check for holidays
        if self.is_holiday(session):
            return False

        session_times = self.sessions[session]
        open_time = datetime.strptime(session_times["open"], "%H:%M").time()
        close_time = datetime.strptime(session_times["close"], "%H:%M").time()
        current_time = now.time()

        # Handle sessions that cross midnight
        if open_time > close_time:
            return current_time >= open_time or current_time <= close_time
        else:
            return open_time <= current_time <= close_time

    def get_current_session_info(self) -> Dict:
        """Get comprehensive session information"""
        now = datetime.now(ZoneInfo("UTC"))
        active_sessions = []
        upcoming_sessions = []

        # Check active sessions
        for session in self.sessions:
            if self.is_session_open(session):
                active_sessions.append(session)

        # Calculate upcoming sessions, including holiday-affected ones
        for session, times in self.sessions.items():
            if session not in active_sessions:
                open_time = datetime.strptime(times["open"], "%H:%M").time()
                minutes_until = self._calculate_minutes_until(now.time(), open_time)
                
                # Adjust for holidays
                if self.is_holiday(session):
                    next_opening = now + timedelta(days=1)
                    while self.is_holiday(session, next_opening):
                        next_opening += timedelta(days=1)
                        minutes_until += 24 * 60  # Add a day's worth of minutes

                upcoming_sessions.append({
                    'name': session,
                    'opens_in': f"{minutes_until // 60}h {minutes_until % 60}m"
                })

        # Sort upcoming sessions by time until opening
        upcoming_sessions.sort(key=lambda x: self._parse_time_string(x['opens_in']))

        return {
            'active_sessions': active_sessions,
            'upcoming_sessions': upcoming_sessions
        }

    def _parse_time_string(self, time_str: str) -> int:
        """Convert time string (e.g., '6h 30m') to minutes"""
        hours = int(time_str.split('h')[0])
        minutes = int(time_str.split('h')[1].strip().split('m')[0])
        return hours * 60 + minutes

    def _calculate_minutes_until(self, current: time, target: time) -> int:
        """Calculate minutes until target time"""
        current_minutes = current.hour * 60 + current.minute
        target_minutes = target.hour * 60 + target.minute
        
        if target_minutes <= current_minutes:
            target_minutes += 24 * 60
            
        return target_minutes - current_minutes
```

### core\menu_manager.py (11.96 KB)

```py
import os
from typing import Dict, List, Any
import time
from datetime import datetime

class MenuManager:
    def __init__(self):
        """Initialize Menu Manager"""
        self.running = True
        self.current_menu = "main"

    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self, title: str):
        """Print menu header"""
        self.clear_screen()
        print("=" * 50)
        print(f"{title:^50}")
        print("=" * 50)
        print()

    def print_menu_options(self, options: Dict[str, str]):
        """Print menu options"""
        for key, value in options.items():
            print(f"{key}. {value}")
        print()

    def get_user_input(self, prompt: str = "Enter your choice: ") -> str:
        """Get user input"""
        return input(prompt).strip()

    def show_main_menu(self) -> str:
        """Display main menu and get user choice"""
        self.print_header("Forex Trading Bot - Automated Mode")
        
        options = {
            "1": "Account Information",
            "2": "Open Positions",
            "3": "System Status",
            "4": "Run System Audit",
            "5": "Generate Trading Log",
            "0": "Exit"
        }
        
        self.print_menu_options(options)
        return self.get_user_input()

    def show_trade_management_menu(self) -> str:
        """Display trade management menu and get user choice"""
        self.print_header("Trade Management Menu")
        
        options = {
            "1": "Show Open Positions",
            "2": "Modify Stop Loss/Take Profit",
            "3": "Close Specific Position",
            "4": "Close All Positions",
            "5": "Position Summary",
            "0": "Back to Main Menu"
        }
        
        self.print_menu_options(options)
        return self.get_user_input()

    def show_market_watch_menu(self) -> str:
        """Display market watch menu and get user choice"""
        self.print_header("Market Watch Menu")
        
        options = {
            "1": "Show Specific Symbol Price",
            "2": "Watch List",
            "3": "Symbol Information",
            "4": "Set Price Alerts",
            "5": "View Active Alerts",
            "6": "Clear Alerts",
            "0": "Back to Main Menu"
        }
        
        self.print_menu_options(options)
        return self.get_user_input()

    def show_signal_management_menu(self) -> str:
        """Display signal management menu and get user choice"""
        self.print_header("Signal Management Menu")
        
        options = {
            "1": "Show Active Signals",
            "2": "Signal Provider Status",
            "3": "Configure Signal Providers",
            "4": "View Signal History",
            "5": "Add/Remove Providers",
            "6": "Provider Performance",
            "0": "Back to Main Menu"
        }
        
        self.print_menu_options(options)
        return self.get_user_input()

    def show_risk_management_menu(self) -> str:
        """Display risk management menu and get user choice"""
        self.print_header("Risk Management Menu")
        
        options = {
            "1": "Position Size Calculator",
            "2": "Risk Per Trade Settings",
            "3": "Account Risk Analysis",
            "4": "Trading Rules Status",
            "5": "Risk Reports",
            "0": "Back to Main Menu"
        }
        
        self.print_menu_options(options)
        return self.get_user_input()

    def show_trading_journal_menu(self) -> str:
        """Display trading journal menu and get user choice"""
        self.print_header("Trading Journal Menu")
        
        options = {
            "1": "View Journal Entries",
            "2": "Add New Entry",
            "3": "Performance Analysis",
            "4": "Export Trading Data",
            "5": "Trade Statistics",
            "0": "Back to Main Menu"
        }
        
        self.print_menu_options(options)
        return self.get_user_input()

    def show_audit_results(self, audit_report: str):
        """Display system audit results"""
        self.print_header("System Audit Results")
        print(audit_report)
        self.wait_for_enter()

    def display_positions(self, positions: List[Dict]):
        """Display open positions in a formatted table"""
        if not positions:
            print("\nNo open positions.")
            return

        print("\nOpen Positions:")
        print("-" * 100)
        print(f"{'Ticket':^10} {'Symbol':^10} {'Type':^6} {'Volume':^8} {'Open Price':^12} "
              f"{'Current':^12} {'Profit':^10} {'Pips':^8}")
        print("-" * 100)

        for pos in positions:
            print(f"{pos['ticket']:^10} {pos['symbol']:^10} {pos['type']:^6} {pos['volume']:^8} "
                  f"{pos['open_price']:^12.5f} {pos['current_price']:^12.5f} "
                  f"{pos['profit']:^10.2f} {pos['pips']:^8.1f}")
        print("-" * 100)

    def display_account_info(self, info: Dict):
        """Display account information"""
        self.print_header("Account Information")
        
        print(f"Balance: ${info['balance']:.2f}")
        print(f"Equity: ${info['equity']:.2f}")
        print(f"Profit: ${info['profit']:.2f}")
        print(f"Margin: ${info['margin']:.2f}")
        print(f"Free Margin: ${info['margin_free']:.2f}")
        print(f"Margin Level: {info['margin_level']:.2f}%")

    def display_position_summary(self, summary: Dict):
        """Display position summary"""
        self.print_header("Position Summary")
        
        print(f"Total Positions: {summary['total_positions']}")
        print(f"Total Profit: ${summary['total_profit']:.2f}")
        print(f"Buy Positions: {summary['buy_positions']}")
        print(f"Sell Positions: {summary['sell_positions']}")
        print(f"Total Volume: {summary['total_volume']:.2f} lots")
        print("\nActive Symbols:")
        for symbol in summary['symbols']:
            print(f"- {symbol}")

    def show_active_signals(self):
        """Display current signals"""
        try:
            response = self.signal_manager.show_active_signals()
            print(f"\n{response}")
        except Exception as e:
            self.display_error_message(f"Error showing signals: {str(e)}")
        self.wait_for_enter()

    def display_signals(self, signals: List[Dict]):
        """Display trading signals"""
        if not signals:
            print("\nNo active signals.")
            return

        print("\nCurrent Trading Signals:")
        print("-" * 80)
        print(f"{'Symbol':^10} {'Provider':^15} {'Type':^8} {'Entry':^10} "
              f"{'SL':^10} {'TP':^10} {'Time':^15}")
        print("-" * 80)

        for signal in signals:
            print(
                f"{signal['symbol']:^10} "
                f"{signal['provider']:^15} "
                f"{signal['type']:^8} "
                f"{signal.get('entry_price', 'N/A'):^10} "
                f"{signal.get('stop_loss', 'N/A'):^10} "
                f"{signal.get('take_profit', 'N/A'):^10} "
                f"{signal['timestamp'].strftime('%H:%M:%S'):^15}"
            )
        print("-" * 80)

    def display_provider_status(self, providers: Dict):
        """Display signal provider status"""
        print("\nSignal Provider Status:")
        print("-" * 50)
        print(f"{'Provider':^20} {'Active':^10} {'Symbols':^20}")
        print("-" * 50)
        
        for name, provider in providers.items():
            symbols = ', '.join(provider['symbols'][:3])
            if len(provider['symbols']) > 3:
                symbols += '...'
            print(f"{name:^20} {'Yes' if provider['active'] else 'No':^10} {symbols:^20}")
        print("-" * 50)

    def prompt_for_trade_details(self) -> Dict:
        """Get trade details from user"""
        self.print_header("New Trade")
        
        details = {}
        details['symbol'] = input("Enter symbol (e.g., EURUSD): ").upper()
        details['order_type'] = input("Enter order type (BUY/SELL): ").upper()
        
        while True:
            try:
                details['volume'] = float(input("Enter volume (lots): "))
                break
            except ValueError:
                print("Invalid volume. Please enter a number.")

        use_sl = input("Add Stop Loss? (y/n): ").lower() == 'y'
        if use_sl:
            details['stop_loss'] = float(input("Enter Stop Loss price: "))
            
        use_tp = input("Add Take Profit? (y/n): ").lower() == 'y'
        if use_tp:
            details['take_profit'] = float(input("Enter Take Profit price: "))

        return details

    def display_market_prices(self, prices: Dict):
        """Display market prices"""
        print("\nCurrent Market Prices:")
        print("-" * 50)
        print(f"{'Symbol':^10} {'Bid':^12} {'Ask':^12} {'Spread':^10}")
        print("-" * 50)
        
        for symbol, price in prices.items():
            print(f"{symbol:^10} {price['bid']:^12.5f} {price['ask']:^12.5f} "
                  f"{price['spread']:^10.5f}")
        print("-" * 50)

    def display_error_message(self, message: str):
        """Display error message to user"""
        print(f"\nError: {message}")
        self.wait_for_enter()

    def display_success_message(self, message: str):
        """Display success message to user"""
        print(f"\nSuccess: {message}")
        self.wait_for_enter()

    def wait_for_enter(self):
        """Wait for user to press enter"""
        input("\nPress Enter to continue...")

    def show_bot_status_menu(self) -> str:
        """Display bot status menu and get user choice"""
        self.print_header("Bot Status Menu")
        
        options = {
            "1": "View Current Status",
            "2": "View Module Status",
            "3": "View Activity Log",
            "4": "Change Operation Mode",
            "5": "Start/Stop Bot",
            "0": "Back to Main Menu"
        }
        
        self.print_menu_options(options)
        return self.get_user_input()

    def display_bot_status(self, status: dict):
        """Display comprehensive bot status"""
        self.print_header("Current Bot Status")
        
        # Bot Status
        bot_status = status['bot_status']
        print(f"Active: {'Yes' if bot_status['active'] else 'No'}")
        print(f"Mode: {bot_status['mode']}")
        print(f"Uptime: {bot_status['uptime']:.2f} seconds")
        print(f"Last Action: {bot_status['last_action']}")
        if bot_status['last_action_time']:
            print(f"Last Action Time: {bot_status['last_action_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Current Operation: {bot_status['current_operation']}")
        print(f"Error Count: {bot_status['error_count']}")
        print(f"Warnings Count: {bot_status['warnings_count']}")
        
        print("\nRecent Activity:")
        for activity in status['recent_activity']:
            print(f"  {activity}")
        
        self.wait_for_enter()

    def display_module_status(self, module_statuses: dict):
        """Display status of all modules"""
        self.print_header("Module Status")
        
        print(f"{'Module':<20} {'Status':<10} {'Last Update':<20} {'Message'}")
        print("-" * 70)
        
        for name, status in module_statuses.items():
            print(f"{name:<20} {status['status']:<10} "
                  f"{status['last_update'].strftime('%Y-%m-%d %H:%M:%S'):<20} "
                  f"{status['message'] if status['message'] else ''}")
        
        self.wait_for_enter()

    def display_activity_log(self, activities: list):
        """Display bot activity log"""
        self.print_header("Activity Log")
        
        for activity in activities:
            print(activity)
        
        self.wait_for_enter()
```

### core\mt5_trader.py (29.69 KB)

```py
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
```

### core\position_manager.py (3.80 KB)

```py
from typing import List, Dict, Tuple, Optional
import MetaTrader5 as mt5
from datetime import datetime

class PositionManager:
    def __init__(self, mt5_instance):
        """
        Initialize Position Manager
        
        Args:
            mt5_instance: Instance of MT5Trader class
        """
        self.mt5_instance = mt5_instance

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions with formatted information"""
        if not self.mt5_instance.connected:
            return []

        positions = mt5.positions_get()
        if positions is None:
            return []

        formatted_positions = []
        for position in positions:
            current_price = self._get_current_price(position.symbol, position.type)
            profit = position.profit
            pips = self._calculate_pips(position.symbol, position.price_open, current_price)

            formatted_positions.append({
                'ticket': position.ticket,
                'symbol': position.symbol,
                'type': 'BUY' if position.type == 0 else 'SELL',
                'volume': position.volume,
                'open_price': position.price_open,
                'current_price': current_price,
                'sl': position.sl,
                'tp': position.tp,
                'profit': profit,
                'pips': pips,
                'comment': position.comment,
                'time': datetime.fromtimestamp(position.time).strftime('%Y-%m-%d %H:%M:%S')
            })

        return formatted_positions

    def _get_current_price(self, symbol: str, position_type: int) -> float:
        """Get current bid/ask price based on position type"""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return 0.0
        return tick.ask if position_type == 1 else tick.bid

    def _calculate_pips(self, symbol: str, open_price: float, current_price: float) -> float:
        """Calculate profit/loss in pips"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return 0.0
        
        digits = symbol_info.digits
        multiplier = 1 if digits == 3 or digits == 5 else 100
        
        return ((current_price - open_price) * multiplier) if digits == 3 or digits == 5 else \
               ((current_price - open_price) * multiplier)

    def close_position(self, ticket: int) -> Tuple[bool, str]:
        """Close specific position by ticket"""
        return self.mt5_instance.close_trade(ticket)

    def close_all_positions(self) -> List[Tuple[int, bool, str]]:
        """Close all open positions"""
        results = []
        positions = self.get_open_positions()
        
        for position in positions:
            success, message = self.close_position(position['ticket'])
            results.append((position['ticket'], success, message))
        
        return results

    def modify_position(
        self,
        ticket: int,
        sl: Optional[float] = None,
        tp: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Modify position's SL/TP"""
        return self.mt5_instance.modify_trade(ticket, stop_loss=sl, take_profit=tp)

    def get_position_summary(self) -> Dict:
        """Get summary of all open positions"""
        positions = self.get_open_positions()
        
        return {
            'total_positions': len(positions),
            'total_profit': sum(pos['profit'] for pos in positions),
            'buy_positions': len([pos for pos in positions if pos['type'] == 'BUY']),
            'sell_positions': len([pos for pos in positions if pos['type'] == 'SELL']),
            'symbols': list(set(pos['symbol'] for pos in positions)),
            'total_volume': sum(pos['volume'] for pos in positions)
        }
```

### core\system_auditor.py (22.10 KB)

```py
import logging
from typing import Dict, List, Optional
from datetime import datetime
import importlib
import inspect
import os
from dataclasses import dataclass
import MetaTrader5 as mt5

@dataclass
class AuditResult:
    """Container for module audit results"""
    module_name: str
    status: str  # 'OK', 'WARNING', 'ERROR'
    message: str
    timestamp: datetime
    details: Optional[Dict] = None

class SystemAuditor:
    """System-wide audit functionality"""
    
    def __init__(self, config_manager=None):
        """Initialize System Auditor"""
        self.config_manager = config_manager
        self._setup_logging()
        self.results: List[AuditResult] = []
        
        # Initialize status manager
        from core.bot_status_manager import BotStatusManager
        self.status_manager = BotStatusManager(config_manager)
        
    def _setup_logging(self):
        """Setup logging for auditor"""
        self.logger = logging.getLogger('SystemAuditor')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def audit_mt5_connection(self) -> AuditResult:
        """Audit MT5 connection status"""
        try:
            from core.mt5_trader import MT5Trader
            trader = MT5Trader(status_manager=self.status_manager)
            
            # First check basic connection
            if not trader.connected:
                self.logger.error("Not connected to MT5 terminal")
                return AuditResult(
                    module_name="MT5Trader",
                    status="ERROR",
                    message="Not connected to MT5 terminal",
                    timestamp=datetime.now()
                )
                
            # Check terminal state
            terminal_info = mt5.terminal_info()
            if terminal_info is not None:
                terminal_dict = terminal_info._asdict()
                
                # Log detailed terminal state
                self.logger.info(f"""
                MT5 Terminal State:
                Connected: {terminal_dict.get('connected', False)}
                Trade Allowed: {terminal_dict.get('trade_allowed', False)}
                Expert Enabled: {terminal_dict.get('trade_expert', False)}
                DLLs Allowed: {terminal_dict.get('dlls_allowed', False)}
                Trade Context: {mt5.symbol_info_tick("EURUSD") is not None}
                """)
                
                # Modified validation logic
                if not terminal_dict.get('connected', False):
                    self.logger.error("MT5 terminal not connected")
                    return AuditResult(
                        module_name="MT5Trader",
                        status="ERROR",
                        message="MT5 terminal not connected to broker",
                        timestamp=datetime.now(),
                        details=terminal_dict
                    )
                
                # Change Expert Advisor check to warning instead of error
                if not terminal_dict.get('trade_expert', False):
                    self.logger.warning("Expert Advisors are disabled")
                    return AuditResult(
                        module_name="MT5Trader",
                        status="WARNING",  # Changed from ERROR to WARNING
                        message="Expert Advisors are disabled. Enable AutoTrading in MT5 if automated trading is needed",
                        timestamp=datetime.now(),
                        details=terminal_dict
                    )
            
            # Test account info access
            account_info = trader.get_account_info()
            if "error" in account_info:
                self.logger.error(f"Account info error: {account_info['error']}")
                return AuditResult(
                    module_name="MT5Trader",
                    status="ERROR",
                    message=f"Cannot access account info: {account_info['error']}",
                    timestamp=datetime.now()
                )
                
            # All checks passed
            self.logger.info(f"""
            MT5 Audit Passed:
            Balance: ${account_info['balance']}
            Server: {mt5.account_info().server}
            Company: {mt5.account_info().company}
            Expert Advisors: {terminal_dict.get('trade_expert', False)}
            Trading: {terminal_dict.get('trade_allowed', False)}
            """)
            
            return AuditResult(
                module_name="MT5Trader",
                status="OK",
                message="MT5 connection operational",
                timestamp=datetime.now(),
                details={
                    "account_info": account_info,
                    "terminal_info": terminal_dict,
                    "trade_enabled": True
                }
            )
                
        except Exception as e:
            self.logger.error(f"Error during MT5 audit: {str(e)}", exc_info=True)
            return AuditResult(
                module_name="MT5Trader",
                status="ERROR",
                message=f"Error during MT5 audit: {str(e)}",
                timestamp=datetime.now()
            )  

    def _check_mt5_expert_status(self) -> AuditResult:
        """Check MT5 expert status directly"""
        try:
            from core.mt5_trader import MT5Trader
            trader = MT5Trader(status_manager=self.status_manager)
            
            if not trader.connected:
                return AuditResult(
                    module_name="MT5Trader",
                    status="ERROR",
                    message="Not connected to MT5 terminal",
                    timestamp=datetime.now()
                )
            
            expert_status = trader._check_expert_status()
            
            # If diagnostics show we can trade, expert is enabled
            if expert_status['diagnostics'].get('can_trade') and \
            expert_status['diagnostics'].get('positions_accessible'):
                return AuditResult(
                    module_name="MT5Trader",
                    status="OK",
                    message="MT5 connection operational",
                    timestamp=datetime.now()
                )
                
            return AuditResult(
                module_name="MT5Trader",
                status="WARNING",
                message="Some trading features may be limited",
                timestamp=datetime.now()
            )
            
        except Exception as e:
            return AuditResult(
                module_name="MT5Trader",
                status="ERROR",
                message=f"Error checking MT5 status: {str(e)}",
                timestamp=datetime.now()
            )          

    def audit_market_watcher(self) -> AuditResult:
        """Audit Market Watcher functionality"""
        try:
            from market_watcher import MarketWatcher
            from core.mt5_trader import MT5Trader
            
            trader = MT5Trader(status_manager=self.status_manager)
            watcher = MarketWatcher(trader)
            
            # Test price data retrieval
            symbol = "EURUSD"
            data = watcher.get_ohlcv_data(symbol, "H1", 10)
            
            if not data:
                self.status_manager.update_module_status(
                    "MarketWatcher",
                    "WARNING",
                    f"No data available for {symbol}"
                )
                return AuditResult(
                    module_name="MarketWatcher",
                    status="WARNING",
                    message=f"No data available for {symbol}",
                    timestamp=datetime.now()
                )
            
            # Test price alerts
            alert_set = watcher.setup_price_alert(symbol, 1.0000, ">")
            if not alert_set:
                self.status_manager.update_module_status(
                    "MarketWatcher",
                    "WARNING",
                    "Could not set price alert"
                )
                return AuditResult(
                    module_name="MarketWatcher",
                    status="WARNING",
                    message="Could not set price alert",
                    timestamp=datetime.now()
                )
                    
            self.status_manager.update_module_status(
                "MarketWatcher",
                "OK",
                "Market Watcher working properly"
            )
            return AuditResult(
                module_name="MarketWatcher",
                status="OK",
                message="Market Watcher working properly",
                timestamp=datetime.now(),
                details={"data_points": len(data)}
            )
                
        except Exception as e:
            self.status_manager.update_module_status(
                "MarketWatcher",
                "ERROR",
                f"Error during Market Watcher audit: {str(e)}"
            )
            return AuditResult(
                module_name="MarketWatcher",
                status="ERROR",
                message=f"Error during Market Watcher audit: {str(e)}",
                timestamp=datetime.now()
            )
        
    def audit_position_manager(self) -> AuditResult:
        """Audit Position Manager functionality"""
        try:
            from core.position_manager import PositionManager
            from core.mt5_trader import MT5Trader
            
            trader = MT5Trader(status_manager=self.status_manager)
            manager = PositionManager(trader)
            
            # Test position retrieval
            positions = manager.get_open_positions()
            summary = manager.get_position_summary()
            
            self.status_manager.update_module_status(
                "PositionManager",
                "OK",
                "Position Manager working properly"
            )
            return AuditResult(
                module_name="PositionManager",
                status="OK",
                message="Position Manager working properly",
                timestamp=datetime.now(),
                details={
                    "open_positions": len(positions),
                    "summary": summary
                }
            )
        except Exception as e:
            self.status_manager.update_module_status(
                "PositionManager",
                "ERROR",
                f"Error during Position Manager audit: {str(e)}"
            )
            return AuditResult(
                module_name="PositionManager",
                status="ERROR",
                message=f"Error during Position Manager audit: {str(e)}",
                timestamp=datetime.now()
            )
                
        except Exception as e:
            return AuditResult(
                module_name="PositionManager",
                status="ERROR",
                message=f"Error during Position Manager audit: {str(e)}",
                timestamp=datetime.now()
            )
        
    def audit_mt5_connection(self) -> AuditResult:
        """Audit MT5 connection status"""
        try:
            from core.mt5_trader import MT5Trader
            trader = MT5Trader(status_manager=self.status_manager)
            
            # First check basic connection
            if not trader.connected:
                self.logger.error("Not connected to MT5 terminal")
                return AuditResult(
                    module_name="MT5Trader",
                    status="ERROR",
                    message="Not connected to MT5 terminal",
                    timestamp=datetime.now()
                )
                
            # Check terminal state
            terminal_info = mt5.terminal_info()
            if terminal_info is not None:
                terminal_dict = terminal_info._asdict()
                
                # Log detailed terminal state
                self.logger.info(f"""
                MT5 Terminal State:
                Connected: {terminal_dict.get('connected', False)}
                Trade Allowed: {terminal_dict.get('trade_allowed', False)}
                Expert Enabled: {terminal_dict.get('trade_expert', False)}
                DLLs Allowed: {terminal_dict.get('dlls_allowed', False)}
                Trade Context: {mt5.symbol_info_tick("EURUSD") is not None}
                """)
                
                # Check critical conditions
                if not terminal_dict.get('trade_expert', False):
                    self.logger.error("Expert Advisors are disabled in MT5")
                    return AuditResult(
                        module_name="MT5Trader",
                        status="ERROR",
                        message="Expert Advisors are disabled. Enable AutoTrading in MT5",
                        timestamp=datetime.now(),
                        details=terminal_dict
                    )
                    
                if not terminal_dict.get('trade_allowed', False):
                    self.logger.error("Trading not allowed in MT5")
                    return AuditResult(
                        module_name="MT5Trader",
                        status="ERROR",
                        message="Trading not allowed in MT5. Check permissions",
                        timestamp=datetime.now(),
                        details=terminal_dict
                    )
                    
                if not terminal_dict.get('connected', False):
                    self.logger.error("MT5 terminal not connected")
                    return AuditResult(
                        module_name="MT5Trader",
                        status="ERROR",
                        message="MT5 terminal not connected to broker",
                        timestamp=datetime.now(),
                        details=terminal_dict
                    )
            
            # Test account info access
            account_info = trader.get_account_info()
            if "error" in account_info:
                self.logger.error(f"Account info error: {account_info['error']}")
                return AuditResult(
                    module_name="MT5Trader",
                    status="ERROR",
                    message=f"Cannot access account info: {account_info['error']}",
                    timestamp=datetime.now()
                )
                
            # All checks passed
            self.logger.info(f"""
            MT5 Audit Passed:
            Balance: ${account_info['balance']}
            Server: {mt5.account_info().server}
            Company: {mt5.account_info().company}
            Expert Advisors: Enabled
            Trading: Allowed
            """)
            
            return AuditResult(
                module_name="MT5Trader",
                status="OK",
                message="MT5 connection fully operational",
                timestamp=datetime.now(),
                details={
                    "account_info": account_info,
                    "terminal_info": terminal_dict,
                    "trade_enabled": True
                }
            )
                
        except Exception as e:
            self.logger.error(f"Error during MT5 audit: {str(e)}", exc_info=True)
            return AuditResult(
                module_name="MT5Trader",
                status="ERROR",
                message=f"Error during MT5 audit: {str(e)}",
                timestamp=datetime.now()
            )

    def audit_signal_manager(self) -> AuditResult:
        """Audit Signal Manager functionality"""
        try:
            from signals.signal_manager import SignalManager
            from core.mt5_trader import MT5Trader
            
            trader = MT5Trader(status_manager=self.status_manager)
            manager = SignalManager(trader, self.config_manager)
            
            # Check if we can get signals
            symbol = "EURUSD"
            signals = manager.get_signals(symbol)
            
            self.status_manager.update_module_status(
                "SignalManager",
                "OK",
                "Signal Manager working properly"
            )
            return AuditResult(
                module_name="SignalManager",
                status="OK",
                message="Signal Manager working properly",
                timestamp=datetime.now(),
                details={"active_signals": len(signals)}
            )
                
        except Exception as e:
            self.status_manager.update_module_status(
                "SignalManager",
                "ERROR",
                f"Error during Signal Manager audit: {str(e)}"
            )
            return AuditResult(
                module_name="SignalManager",
                status="ERROR",
                message=f"Error during Signal Manager audit: {str(e)}",
                timestamp=datetime.now()
            )

    def audit_config_manager(self) -> AuditResult:
        """Audit Configuration Manager"""
        try:
            if not self.config_manager:
                from core.config_manager import ConfigManager
                self.config_manager = ConfigManager()
            
            # Test settings access
            settings = self.config_manager.get_all_settings()
            if not settings:
                return AuditResult(
                    module_name="ConfigManager",
                    status="WARNING",
                    message="No settings available",
                    timestamp=datetime.now()
                )
            
            # Test settings modification
            test_key = "test_setting"
            test_value = "test_value"
            self.config_manager.update_setting(test_key, test_value)
            
            if self.config_manager.get_setting(test_key) != test_value:
                return AuditResult(
                    module_name="ConfigManager",
                    status="ERROR",
                    message="Settings update failed",
                    timestamp=datetime.now()
                )
            
            return AuditResult(
                module_name="ConfigManager",
                status="OK",
                message="Configuration Manager working properly",
                timestamp=datetime.now(),
                details={"settings_count": len(settings)}
            )
            
        except Exception as e:
            return AuditResult(
                module_name="ConfigManager",
                status="ERROR",
                message=f"Error during Config Manager audit: {str(e)}",
                timestamp=datetime.now()
            )

    def audit_menu_manager(self) -> AuditResult:
        """Audit Menu Manager"""
        try:
            from core.menu_manager import MenuManager
            menu = MenuManager()
            
            # Test menu creation
            if not hasattr(menu, 'show_main_menu'):
                return AuditResult(
                    module_name="MenuManager",
                    status="ERROR",
                    message="Missing main menu functionality",
                    timestamp=datetime.now()
                )
            
            return AuditResult(
                module_name="MenuManager",
                status="OK",
                message="Menu Manager working properly",
                timestamp=datetime.now()
            )
            
        except Exception as e:
            return AuditResult(
                module_name="MenuManager",
                status="ERROR",
                message=f"Error during Menu Manager audit: {str(e)}",
                timestamp=datetime.now()
            )

    def run_full_audit(self) -> List[AuditResult]:
        """Run full system audit"""
        # First check MT5 status directly
        mt5_status = self._check_mt5_expert_status()
        
        audit_functions = [
            self.audit_market_watcher,
            self.audit_position_manager,
            self.audit_signal_manager,
            self.audit_config_manager,
            self.audit_menu_manager
        ]
        
        self.results = []
        
        # Add MT5 status first
        self.results.append(mt5_status)
        
        # Run other audits
        for audit_func in audit_functions:
            result = audit_func()
            self.results.append(result)
            self.logger.info(f"{result.module_name}: {result.status} - {result.message}")
        
        return self.results

    def generate_audit_report(self) -> str:
        """Generate formatted audit report"""
        if not self.results:
            self.run_full_audit()
            
        report = ["System Audit Report", "=" * 50, ""]
        
        status_count = {"OK": 0, "WARNING": 0, "ERROR": 0}
        
        for result in self.results:
            status_count[result.status] += 1
            report.append(f"Module: {result.module_name}")
            report.append(f"Status: {result.status}")
            report.append(f"Message: {result.message}")
            if result.details:
                report.append("Details:")
                for key, value in result.details.items():
                    report.append(f"  {key}: {value}")
            report.append("-" * 30)
        
        report.append("\nSummary:")
        report.append(f"Total Modules: {len(self.results)}")
        for status, count in status_count.items():
            report.append(f"{status}: {count}")
            
        return "\n".join(report)

def main():
    """Run system audit"""
    auditor = SystemAuditor()
    auditor.run_full_audit()
    print(auditor.generate_audit_report())

if __name__ == "__main__":
    main()
```

### core\trading_logic.py (5.68 KB)

```py
# In core/trading_logic.py

from typing import Dict, Optional
from datetime import datetime
import logging
from signals.signal_provider import Signal, SignalType

class TradingLogic:
    """Handles automated trading decisions and execution"""
    
    def __init__(self, mt5_trader, signal_manager, position_manager):
        """
        Initialize Trading Logic
        
        Args:
            mt5_trader: MT5Trader instance for trade execution
            signal_manager: SignalManager for getting trading signals
            position_manager: PositionManager for position handling
        """
        self.mt5_trader = mt5_trader
        self.signal_manager = signal_manager
        self.position_manager = position_manager
        self._setup_logging()
        
        # Trading parameters
        self.min_risk_reward = 2.0  # Minimum risk/reward ratio
        self.max_positions_per_symbol = 1  # Maximum positions per symbol
        self.max_total_positions = 3  # Maximum total positions
        self.required_signal_strength = 0.7  # Required signal strength (70%)

    def _setup_logging(self):
        """Setup logging for trading logic"""
        self.logger = logging.getLogger('TradingLogic')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
    def _validate_trading_conditions(self, symbol: str, signal: Signal) -> bool:
        """Validate if trading conditions are met"""
        # Check if we already have maximum positions
        current_positions = self.position_manager.get_open_positions()
        if len(current_positions) >= self.max_total_positions:
            self.logger.info(f"Maximum total positions ({self.max_total_positions}) reached")
            return False
            
        # Check symbol-specific position limit
        symbol_positions = [p for p in current_positions if p['symbol'] == symbol]
        if len(symbol_positions) >= self.max_positions_per_symbol:
            self.logger.info(f"Maximum positions for {symbol} reached")
            return False
            
        # Calculate Risk/Reward ratio
        if signal.entry_price and signal.stop_loss and signal.take_profit:
            risk = abs(signal.entry_price - signal.stop_loss)
            reward = abs(signal.take_profit - signal.entry_price)
            rr_ratio = reward / risk if risk > 0 else 0
            
            if rr_ratio < self.min_risk_reward:
                self.logger.info(f"Risk/Reward ratio ({rr_ratio:.2f}) below minimum ({self.min_risk_reward})")
                return False
        
        return True

    def process_symbol(self, symbol: str) -> Optional[Dict]:
        """Process trading logic for a symbol"""
        try:
            # Get all signals for the symbol
            signals = self.signal_manager.get_signals(symbol)
            if not signals:
                return None
                
            # Get consensus signal (strong agreement among providers)
            consensus = self.signal_manager.get_consensus_signal(symbol)
            if not consensus or consensus.type == SignalType.NONE:
                return None
                
            # Check if we have a strong enough signal
            signal_strength = len([s for s in signals if s.type == consensus.type]) / len(signals)
            if signal_strength < self.required_signal_strength:
                self.logger.info(f"Signal strength ({signal_strength:.2f}) below required ({self.required_signal_strength})")
                return None
                
            # Validate trading conditions
            if not self._validate_trading_conditions(symbol, consensus):
                return None
                
            # Prepare trade parameters
            volume = consensus.volume or 0.01  # Default to minimum if not specified
            
            # Create a simple comment without special characters
            comment = f"MT5Bot_{consensus.type.value}"
            
            # Execute the trade
            success, message = self.mt5_trader.place_trade(
                symbol=symbol,
                order_type=consensus.type.value,
                volume=volume,
                price=consensus.entry_price,
                stop_loss=consensus.stop_loss,
                take_profit=consensus.take_profit,
                comment=comment
            )
            
            if success:
                self.logger.info(f"Trade executed for {symbol}: {message}")
                return {
                    'symbol': symbol,
                    'signal': consensus,
                    'execution': 'success',
                    'message': message
                }
            else:
                self.logger.error(f"Trade execution failed: {message}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing {symbol}: {str(e)}")
            return None

    def get_position_summary(self) -> Dict:
        """Get summary of current positions and trading status"""
        positions = self.position_manager.get_open_positions()
        
        return {
            'total_positions': len(positions),
            'symbols_traded': list(set(pos['symbol'] for pos in positions)),
            'total_profit': sum(pos['profit'] for pos in positions),
            'positions_available': self.max_total_positions - len(positions)
        }
```

### signals\__init__.py (202.00 B)

```py
from .signal_provider import Signal, SignalType, SignalProvider
from .signal_manager import SignalManager

__all__ = [
    'Signal',
    'SignalType',
    'SignalProvider',
    'SignalManager'
]
```

### signals\moving_average_provider.py (4.26 KB)

```py
from datetime import datetime
from typing import List, Dict
from .signal_provider import SignalProvider, Signal, SignalType

class MovingAverageProvider(SignalProvider):
    """Simple Moving Average crossover signal provider"""
    
    def __init__(self, name: str, symbols: List[str], timeframe: str):
        """
        Initialize Moving Average signal provider
        
        Args:
            name: Provider name
            symbols: List of symbols to monitor
            timeframe: Timeframe to analyze
        """
        super().__init__(name, symbols, timeframe)
        self._parameters = {
            'fast_period': 10,
            'slow_period': 20
        }
    
    def calculate_signal(self, symbol: str, candles: List[Dict]) -> Signal:
        """
        Calculate signal based on moving average crossover
        
        Args:
            symbol: Trading symbol
            candles: List of OHLCV candles
            
        Returns:
            Signal based on MA crossover
        """
        if not candles or len(candles) < self._parameters['slow_period']:
            return Signal(
                type=SignalType.NONE,
                symbol=symbol,
                timestamp=datetime.now(),
                provider=self.name,
                comment="Insufficient data"
            )

        # Calculate fast MA
        fast_ma = sum(c['close'] for c in candles[-self._parameters['fast_period']:]) / self._parameters['fast_period']
        
        # Calculate slow MA
        slow_ma = sum(c['close'] for c in candles[-self._parameters['slow_period']:]) / self._parameters['slow_period']
        
        current_price = candles[-1]['close']

        # Determine signal type
        if fast_ma > slow_ma:
            signal_type = SignalType.BUY
            stop_loss = min(c['low'] for c in candles[-5:]) - 0.0010  # 10 pips below recent low
            take_profit = current_price + (current_price - stop_loss) * 2  # 2:1 reward ratio
        elif fast_ma < slow_ma:
            signal_type = SignalType.SELL
            stop_loss = max(c['high'] for c in candles[-5:]) + 0.0010  # 10 pips above recent high
            take_profit = current_price - (stop_loss - current_price) * 2  # 2:1 reward ratio
        else:
            signal_type = SignalType.NONE
            stop_loss = take_profit = None

        # Create and validate signal
        signal = Signal(
            type=signal_type,
            symbol=symbol,
            timestamp=datetime.now(),
            provider=self.name,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=0.01,  # Default small volume
            comment=f"MA{self._parameters['fast_period']}/{self._parameters['slow_period']} Crossover"
        )
        
        # Store and return if valid
        if signal.is_valid():
            self._update_last_signal(symbol, signal)
        return signal

    def validate_parameters(self, parameters: Dict) -> bool:
        """
        Validate strategy parameters
        
        Args:
            parameters: Dictionary with fast_period and slow_period
            
        Returns:
            True if parameters are valid
        """
        if not all(key in parameters for key in ['fast_period', 'slow_period']):
            return False
            
        if not all(isinstance(val, int) and val > 0 for val in parameters.values()):
            return False
            
        if parameters['fast_period'] >= parameters['slow_period']:
            return False
            
        return True

    def update_parameters(self, fast_period: int = None, slow_period: int = None) -> bool:
        """
        Update MA parameters
        
        Args:
            fast_period: Period for fast MA
            slow_period: Period for slow MA
            
        Returns:
            True if parameters were updated successfully
        """
        new_params = self._parameters.copy()
        
        if fast_period is not None:
            new_params['fast_period'] = fast_period
        if slow_period is not None:
            new_params['slow_period'] = slow_period
            
        return super().update_parameters(new_params)
```

### signals\signal_evaluator.py (8.53 KB)

```py
import logging
from typing import List, Dict
from .signal_provider import SignalProvider, Signal, SignalType
from datetime import datetime


class SignalEvaluator:
    """Enhanced signal evaluation system incorporating all trading criteria"""
    
    def __init__(self, signal_manager, trading_logic):
        self.signal_manager = signal_manager
        self.trading_logic = trading_logic
        self.position_manager = trading_logic.position_manager
        self._setup_logging()
        self.logger.info("SignalEvaluator initialized with signal manager and trading logic")
        
    def _setup_logging(self):
        """Setup logging configuration"""
        self.logger = logging.getLogger('SignalEvaluator')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s\n'
                'File: %(filename)s:%(lineno)d\n'
                'Function: %(funcName)s\n'
                '----------------------------------------'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

    def evaluate_signal(self, symbol: str, signals: List[Signal]) -> dict:
        """
        Comprehensive signal evaluation incorporating all trading criteria
        """
        self.logger.info(f"Starting signal evaluation for {symbol}")
        
        # Create evaluation result
        evaluation = {
            'signal_strength': 0.0,
            'trading_eligible': False,
            'status': 'WEAK',
            'details': {},
            'timestamp': datetime.now()
        }
        
        try:
            if not signals:
                self.logger.info(f"No signals provided for {symbol}")
                evaluation['details']['reason'] = 'No signals available'
                return evaluation
                
            # Calculate provider consensus
            signal_counts = self._calculate_signal_counts(signals)
            self.logger.debug(f"Signal counts for {symbol}: {signal_counts}")
            
            consensus_strength = self._calculate_consensus_strength(signal_counts)
            self.logger.info(f"Calculated consensus strength for {symbol}: {consensus_strength}")
            evaluation['signal_strength'] = consensus_strength
            
            # Evaluate trading conditions
            position_check = self._check_position_limits(symbol)
            self.logger.debug(f"Position limit check for {symbol}: {position_check}")
            
            risk_reward_check = self._check_risk_reward_ratio(signals)
            self.logger.debug(f"Risk/Reward check for {symbol}: {risk_reward_check}")
            
            # Store detailed results
            evaluation['details'].update({
                'consensus_strength': consensus_strength,
                'position_limits': position_check,
                'risk_reward': risk_reward_check,
                'total_signals': len(signals)
            })
            
            # Determine final status
            evaluation.update(
                self._determine_final_status(
                    consensus_strength,
                    position_check,
                    risk_reward_check
                )
            )
            
            self.logger.info(f"Completed evaluation for {symbol}: Status={evaluation['status']}, Eligible={evaluation['trading_eligible']}")
            return evaluation
            
        except Exception as e:
            self.logger.error(f"Error during signal evaluation for {symbol}: {str(e)}", exc_info=True)
            evaluation['details']['error'] = str(e)
            return evaluation
        
    def _calculate_signal_counts(self, signals: list) -> dict:
        """Calculate the number of each signal type"""
        try:
            counts = {'BUY': 0, 'SELL': 0, 'NONE': 0}
            for signal in signals:
                counts[signal.type.value] += 1
            self.logger.debug(f"Calculated signal counts: {counts}")
            return counts
        except Exception as e:
            self.logger.error(f"Error calculating signal counts: {str(e)}")
            return {'BUY': 0, 'SELL': 0, 'NONE': 0}
        
    def _calculate_consensus_strength(self, counts: dict) -> float:
        """Calculate signal strength based on provider consensus"""
        try:
            total_signals = sum(counts.values())
            if total_signals == 0:
                self.logger.debug("No signals to calculate consensus strength")
                return 0.0
                
            max_count = max(counts.values())
            strength = max_count / total_signals
            self.logger.debug(f"Calculated consensus strength: {strength}")
            return strength
        except Exception as e:
            self.logger.error(f"Error calculating consensus strength: {str(e)}")
            return 0.0
        
    def _check_position_limits(self, symbol: str) -> dict:
        """Check if position limits allow new trades"""
        try:
            current_positions = self.position_manager.get_open_positions()
            symbol_positions = [p for p in current_positions if p['symbol'] == symbol]
            
            result = {
                'passed': len(symbol_positions) < self.trading_logic.max_positions_per_symbol,
                'current_positions': len(symbol_positions),
                'max_allowed': self.trading_logic.max_positions_per_symbol
            }
            self.logger.debug(f"Position limits check result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error checking position limits: {str(e)}")
            return {'passed': False, 'error': str(e)}
        
    def _check_risk_reward_ratio(self, signals: list) -> dict:
        """Validate risk/reward ratios for signals"""
        try:
            for signal in signals:
                if not all([signal.entry_price, signal.stop_loss, signal.take_profit]):
                    continue
                    
                risk = abs(signal.entry_price - signal.stop_loss)
                reward = abs(signal.take_profit - signal.entry_price)
                if risk == 0:
                    continue
                    
                ratio = reward / risk
                if ratio >= self.trading_logic.min_risk_reward:
                    result = {
                        'passed': True,
                        'ratio': ratio,
                        'minimum_required': self.trading_logic.min_risk_reward
                    }
                    self.logger.debug(f"Risk/Reward check passed: {result}")
                    return result
            
            result = {
                'passed': False,
                'ratio': 0.0,
                'minimum_required': self.trading_logic.min_risk_reward
            }
            self.logger.debug(f"Risk/Reward check failed: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error checking risk/reward ratio: {str(e)}")
            return {'passed': False, 'error': str(e)}
        
    def _determine_final_status(
        self,
        consensus_strength: float,
        position_check: dict,
        risk_reward_check: dict
    ) -> dict:
        """Determine final signal status and trading eligibility"""
        try:
            # Signal must be strong enough and meet all trading criteria
            trading_eligible = (
                consensus_strength >= self.trading_logic.required_signal_strength and
                position_check['passed'] and
                risk_reward_check['passed']
            )
            
            # Determine status based on consensus strength and trading eligibility
            if trading_eligible and consensus_strength >= 0.8:
                status = 'STRONG'
            elif trading_eligible and consensus_strength >= 0.6:
                status = 'MODERATE'
            else:
                status = 'WEAK'
                
            result = {
                'trading_eligible': trading_eligible,
                'status': status
            }
            self.logger.info(f"Final status determination: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error determining final status: {str(e)}")
            return {'trading_eligible': False, 'status': 'WEAK'}
```

### signals\signal_manager.py (13.76 KB)

```py
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging
from .signal_provider import SignalProvider, Signal, SignalType
from .signal_evaluator import SignalEvaluator


class SignalManager:
    """Manages and coordinates multiple signal providers"""
    
    def __init__(self, mt5_trader, config_manager, trading_logic=None):
        """
        Initialize Signal Manager
        
        Args:
            mt5_trader: MT5Trader instance for market data
            config_manager: ConfigManager instance for settings
            trading_logic: Optional TradingLogic instance
        """
        self.mt5_trader = mt5_trader
        self.config_manager = config_manager
        self.trading_logic = trading_logic
        self.providers: Dict[str, SignalProvider] = {}
        self.active_symbols: Set[str] = set()
        self._setup_logging()
        self._initialize_default_providers()
        self._signal_cache = {}
        self._last_evaluation_time = {}
        
        # Only initialize signal evaluator if trading_logic is provided
        self.signal_evaluator = None
        if trading_logic:
            self.signal_evaluator = SignalEvaluator(self, trading_logic)

        
    def _setup_logging(self):
        """Setup logging for signal manager"""
        self.logger = logging.getLogger('SignalManager')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
    def _initialize_default_providers(self):
        """Initialize default signal providers"""
        favorite_symbols = self.config_manager.get_setting('favorite_symbols', [])
        if not favorite_symbols:
            self.logger.warning("No favorite symbols configured")
            return
            
        try:
            from .moving_average_provider import MovingAverageProvider
            
            # Add Moving Average provider
            ma_provider = MovingAverageProvider(
                name="MA Crossover",
                symbols=favorite_symbols,
                timeframe="H1"
            )
            self.add_provider(ma_provider)
            self.logger.info(f"Added default MA Crossover provider for symbols: {favorite_symbols}")
            
        except Exception as e:
            self.logger.error(f"Error initializing default providers: {str(e)}")
    
    def add_provider(self, provider: SignalProvider) -> bool:
        """
        Add new signal provider
        
        Args:
            provider: SignalProvider instance
            
        Returns:
            True if provider was added successfully
        """
        if provider.name in self.providers:
            self.logger.warning(f"Provider {provider.name} already exists")
            return False
            
        self.providers[provider.name] = provider
        self.active_symbols.update(provider.symbols)
        self.logger.info(f"Added provider: {provider.name}")
        return True
    
    def remove_provider(self, provider_name: str) -> bool:
        """
        Remove signal provider
        
        Args:
            provider_name: Name of provider to remove
            
        Returns:
            True if provider was removed successfully
        """
        if provider_name not in self.providers:
            self.logger.warning(f"Provider {provider_name} not found")
            return False
            
        provider = self.providers.pop(provider_name)
        self._update_active_symbols()
        self.logger.info(f"Removed provider: {provider_name}")
        return True
    
    def _update_active_symbols(self):
        """Update set of active symbols from all providers"""
        self.active_symbols = set()
        for provider in self.providers.values():
            if provider.is_active:
                self.active_symbols.update(provider.symbols)
    
    def get_signals(self, symbol: str) -> List[Signal]:
        """Get signals from all active providers for symbol"""
        current_time = datetime.now()
        
        # Check cache first (valid for 1 minute)
        if (symbol in self._signal_cache and symbol in self._last_evaluation_time and
            (current_time - self._last_evaluation_time[symbol]).total_seconds() < 60):
            return self._signal_cache[symbol]
            
        if not self.providers:
            self.logger.warning("No signal providers configured")
            return []
            
        if symbol not in self.active_symbols:
            self.logger.warning(f"No active providers for symbol {symbol}")
            return []
            
        signals = []
        
        # Get market data
        candles = self._get_market_data(symbol)
        if not candles:
            self.logger.warning(f"No market data available for {symbol}")
            return signals
        
        # Get signals from each active provider
        for provider in self.providers.values():
            if not provider.is_active or symbol not in provider.symbols:
                continue
                
            try:
                signal = provider.calculate_signal(symbol, candles)
                if signal and signal.is_valid():
                    signals.append(signal)
                    
            except Exception as e:
                self.logger.error(
                    f"Error getting signal from {provider.name}: {str(e)}"
                )
        
        # Only evaluate signals if we have a signal evaluator
        if signals and self.signal_evaluator:
            try:
                evaluation = self.signal_evaluator.evaluate_signal(symbol, signals)
                
                # Update signal strengths based on evaluation
                for signal in signals:
                    signal.strength = evaluation['signal_strength']
                    signal.trading_eligible = evaluation['trading_eligible']
                    signal.evaluation_details = evaluation['details']
                    
                self.logger.info(
                    f"Got signals for {symbol}: Strength={evaluation['signal_strength']:.2f}, "
                    f"Status={evaluation['status']}, Eligible={evaluation['trading_eligible']}"
                )
            except Exception as e:
                self.logger.error(f"Error evaluating signals: {str(e)}")
        
        # Update cache
        self._signal_cache[symbol] = signals
        self._last_evaluation_time[symbol] = current_time
        
        return signals
    
    def _get_market_data(self, symbol: str) -> List[Dict]:
        """
        Get market data for symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of OHLCV candles with indicators
        """
        try:
            # Get data from market watcher
            candles = self.mt5_trader.market_watcher.get_ohlcv_data(
                symbol=symbol,
                timeframe="H1",  # Default timeframe
                bars=100,
                include_incomplete=False
            )
            
            if not candles:
                self.logger.warning(f"No market data available for {symbol}")
                return []
            
            # Convert MarketData objects to dictionaries
            return [
                {
                    'timestamp': candle.timestamp,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume,
                    'tick_volume': candle.tick_volume,
                    'spread': candle.spread
                }
                for candle in candles
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting market data for {symbol}: {str(e)}")
            return []
    
    def get_consensus_signal(self, symbol: str) -> Optional[Signal]:
        """
        Get consensus signal from all providers
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Signal based on consensus or None
        """
        signals = self.get_signals(symbol)
        if not signals:
            return None
            
        # Count signal types
        signal_counts = {
            SignalType.BUY: 0,
            SignalType.SELL: 0,
            SignalType.CLOSE: 0,
            SignalType.NONE: 0
        }
        
        for signal in signals:
            signal_counts[signal.type] += 1
        
        # Get majority signal type
        total_signals = len(signals)
        consensus_threshold = self.config_manager.get_setting(
            'signal_consensus_threshold', 0.66
        )
        
        for signal_type, count in signal_counts.items():
            if count / total_signals >= consensus_threshold:
                return self._create_consensus_signal(
                    signal_type, symbol, signals
                )
        
        return None
    
    def _create_consensus_signal(
        self, 
        signal_type: SignalType,
        symbol: str,
        signals: List[Signal]
    ) -> Signal:
        """Create consensus signal from multiple signals"""
        matching_signals = [s for s in signals if s.type == signal_type]
        
        if not matching_signals:
            return Signal(
                type=SignalType.NONE,
                symbol=symbol,
                timestamp=datetime.now()
            )
        
        # Average the entry, sl, and tp prices
        if signal_type in [SignalType.BUY, SignalType.SELL]:
            entry_prices = [s.entry_price for s in matching_signals if s.entry_price]
            sl_prices = [s.stop_loss for s in matching_signals if s.stop_loss]
            tp_prices = [s.take_profit for s in matching_signals if s.take_profit]
            volumes = [s.volume for s in matching_signals if s.volume]
            
            return Signal(
                type=signal_type,
                symbol=symbol,
                timestamp=datetime.now(),
                entry_price=sum(entry_prices) / len(entry_prices) if entry_prices else None,
                stop_loss=sum(sl_prices) / len(sl_prices) if sl_prices else None,
                take_profit=sum(tp_prices) / len(tp_prices) if tp_prices else None,
                volume=sum(volumes) / len(volumes) if volumes else None,
                comment="Consensus signal"
            )
        
        return Signal(
            type=signal_type,
            symbol=symbol,
            timestamp=datetime.now(),
            comment="Consensus signal"
        )
    
    def get_active_providers(self) -> List[str]:
        """Get list of active provider names"""
        return [name for name, provider in self.providers.items() 
                if provider.is_active]
    
    def get_provider_signals(self, provider_name: str, symbol: str) -> Optional[Signal]:
        """
        Get signals from specific provider
        
        Args:
            provider_name: Name of provider
            symbol: Trading symbol
            
        Returns:
            Signal from provider or None
        """
        if provider_name not in self.providers:
            self.logger.warning(f"Provider {provider_name} not found")
            return None
            
        provider = self.providers[provider_name]
        if not provider.is_active or symbol not in provider.symbols:
            return None
            
        candles = self._get_market_data(symbol)
        if not candles:
            return None
            
        try:
            return provider.calculate_signal(symbol, candles)
        except Exception as e:
            self.logger.error(
                f"Error getting signal from {provider_name}: {str(e)}"
            )
            return None

    def show_active_signals(self) -> str:
        """Display current signals for all active symbols"""
        if not self.providers:
            return "No signal providers configured. Please add providers first."
            
        if not self.active_symbols:
            return "No active symbols configured. Please check provider configuration."
            
        symbols = self.config_manager.get_setting('favorite_symbols', [])
        signals_found = False
        output = []
        
        for symbol in symbols:
            signals = self.get_signals(symbol)
            if signals:
                signals_found = True
                evaluation = self.signal_evaluator.evaluate_signal(symbol)
                
                output.append(f"\nSignals for {symbol}:")
                output.append(f"Signal Strength: {evaluation['signal_strength']:.2f}")
                output.append(f"Status: {evaluation['status']}")
                output.append(f"Trading Eligible: {'Yes' if evaluation['trading_eligible'] else 'No'}")
                
                if not evaluation['trading_eligible'] and evaluation['details']:
                    output.append("Reason not eligible:")
                    for key, value in evaluation['details'].items():
                        if isinstance(value, dict) and 'passed' in value:
                            if not value['passed']:
                                output.append(f"- Failed {key} check")
        
        if not signals_found:
            return "No active signals at this time."
        
        return "\n".join(output)
```

### signals\signal_provider.py (4.18 KB)

```py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

class SignalType(Enum):
    """Type of trading signal"""
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    NONE = "NONE"

@dataclass
class Signal:
    """Trading signal data structure"""
    type: SignalType
    symbol: str
    timestamp: datetime
    provider: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    volume: Optional[float] = None
    comment: Optional[str] = None
    extra_data: Optional[Dict] = None

    def is_valid(self) -> bool:
        """Check if signal has all required fields"""
        if self.type == SignalType.NONE:
            return True
        
        if not all([self.symbol, self.timestamp]):
            return False
            
        if self.type in [SignalType.BUY, SignalType.SELL]:
            return all([
                self.entry_price is not None,
                self.stop_loss is not None,
                self.take_profit is not None,
                self.volume is not None
            ])
            
        return True

class SignalProvider(ABC):
    """Base class for all signal providers/strategies"""
    
    def __init__(self, name: str, symbols: List[str], timeframe: str):
        """
        Initialize signal provider
        
        Args:
            name: Provider/strategy name
            symbols: List of symbols to monitor
            timeframe: Timeframe to analyze (e.g., "1H", "4H", "1D")
        """
        self.name = name
        self.symbols = symbols
        self.timeframe = timeframe
        self.is_active = True
        self._last_signal: Dict[str, Signal] = {}
        self._parameters: Dict = {}
        
    @abstractmethod
    def calculate_signal(self, symbol: str, candles: List[Dict]) -> Signal:
        """
        Calculate trading signal based on market data
        
        Args:
            symbol: Trading symbol
            candles: List of OHLCV candles with indicators
            
        Returns:
            Signal instance with trading decision
        """
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict) -> bool:
        """
        Validate strategy parameters
        
        Args:
            parameters: Dictionary of parameters to validate
            
        Returns:
            True if parameters are valid
        """
        pass
    
    def update_parameters(self, parameters: Dict) -> bool:
        """
        Update strategy parameters
        
        Args:
            parameters: New parameter values
            
        Returns:
            True if parameters were updated successfully
        """
        if not self.validate_parameters(parameters):
            return False
            
        self._parameters.update(parameters)
        return True
    
    def get_parameters(self) -> Dict:
        """Get current strategy parameters"""
        return self._parameters.copy()
    
    def get_last_signal(self, symbol: str) -> Optional[Signal]:
        """
        Get last signal for symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Last signal generated for symbol or None
        """
        return self._last_signal.get(symbol)
    
    def set_active(self, active: bool):
        """Enable/disable signal provider"""
        self.is_active = active
    
    def _update_last_signal(self, symbol: str, signal: Signal):
        """Update last signal for symbol"""
        self._last_signal[symbol] = signal
    
    def _validate_signal(self, signal: Signal) -> bool:
        """
        Validate signal before returning
        
        Args:
            signal: Signal to validate
            
        Returns:
            True if signal is valid
        """
        if not signal.is_valid():
            return False
            
        # Store valid signal
        self._update_last_signal(signal.symbol, signal)
        return True
```

### tests\__init__.py (0.00 B)

```py

```

### trading_logs\forexbot_20241129_071541.log (4.21 KB)

*Binary or unsupported file format*

### trading_logs\forexbot_20241129_071651.log (4.21 KB)

*Binary or unsupported file format*

### trading_logs\forexbot_20241129_072215.log (4.21 KB)

*Binary or unsupported file format*

### trading_logs\mt5trader_20241129_071541.log (6.32 KB)

*Binary or unsupported file format*

### trading_logs\mt5trader_20241129_071651.log (6.32 KB)

*Binary or unsupported file format*

### trading_logs\mt5trader_20241129_072215.log (6.32 KB)

*Binary or unsupported file format*

### trading_logs\trading_activity_20241129_071543.log (23.17 KB)

*Binary or unsupported file format*

### trading_logs\trading_activity_20241129_071653.log (136.85 KB)

*Binary or unsupported file format*

### trading_logs\trading_activity_20241129_072217.log (15.91 KB)

*Binary or unsupported file format*

### trading_logs\trading_session_20241129_071541.log (1.58 KB)

*Binary or unsupported file format*

### trading_logs\trading_session_20241129_071651.log (1.58 KB)

*Binary or unsupported file format*

### trading_logs\trading_session_20241129_072215.log (1.58 KB)

*Binary or unsupported file format*

### trading_logs\tradinglogger_20241129_071543.log (4.03 KB)

*Binary or unsupported file format*

### trading_logs\tradinglogger_20241129_071653.log (20.00 KB)

*Binary or unsupported file format*

### trading_logs\tradinglogger_20241129_072217.log (3.02 KB)

*Binary or unsupported file format*

## Project Statistics

- Total Files: 48
- Text Files: 27
- Binary Files: 21
- Total Size: 427.85 KB
