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