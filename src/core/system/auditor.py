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
        from src.core.system.monitor import BotStatusManager
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
            from src.core.trading.mt5 import MT5Trader
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
    
    def audit_ftmo_phase1(self) -> AuditResult:
        """
        Comprehensive audit of FTMO Phase 1 implementation
        Returns: AuditResult with detailed Phase 1 compliance status
        """
        try:
            self.logger.info("Starting FTMO Phase 1 compliance audit...")
            
            # Initialize audit details
            details = {
                'rule_engine': {'status': 'OK', 'issues': []},
                'logging_system': {'status': 'OK', 'issues': []},
                'session_management': {'status': 'OK', 'issues': []},
                'trading_days': {'status': 'OK', 'issues': []}
            }

            # 1. Rule Engine Verification
            try:
                import json
                import os
                ftmo_rules_path = os.path.join("config", "ftmo_rules.json")
                
                if not os.path.exists(ftmo_rules_path):
                    details['rule_engine']['status'] = 'ERROR'
                    details['rule_engine']['issues'].append('FTMO rules file not found')
                else:
                    with open(ftmo_rules_path, 'r') as f:
                        rules = json.load(f)
                    
                    # Verify core rules exist
                    required_rules = {
                        'max_daily_loss': rules['trading_rules'].get('max_daily_loss'),
                        'max_total_loss': rules['trading_rules'].get('max_total_loss'),
                        'position_duration': rules['time_rules'].get('max_position_duration')
                    }
                    
                    for rule, value in required_rules.items():
                        if not value:
                            details['rule_engine']['status'] = 'ERROR'
                            details['rule_engine']['issues'].append(f'Missing {rule} rule')
                        else:
                            self.logger.info(f"Rule {rule} verified: {value}")
            except Exception as e:
                details['rule_engine']['status'] = 'ERROR'
                details['rule_engine']['issues'].append(f'Rule verification error: {str(e)}')

            # 2. Logging System Verification
            log_dir = "trading_logs"
            if not os.path.exists(log_dir):
                details['logging_system']['status'] = 'ERROR'
                details['logging_system']['issues'].append('Trading logs directory not found')
            else:
                # Check for specific log files
                required_logs = ['ftmo_rule_manager', 'trading_session', 'trading_activity']
                log_files = os.listdir(log_dir)
                
                for req_log in required_logs:
                    if not any(req_log in f for f in log_files):
                        details['logging_system']['status'] = 'WARNING'
                        details['logging_system']['issues'].append(f'No recent {req_log} logs found')
                    else:
                        self.logger.info(f"Log type {req_log} verified")

            # 3. Session Management Verification
            from src.core.market.sessions import MarketSessionManager
            session_manager = MarketSessionManager()
            
            # Verify session times
            required_sessions = {
                'London': ('08:00', '16:00'),
                'NewYork': ('13:00', '21:00'),
                'Tokyo': ('00:00', '09:00'),
                'Sydney': ('22:00', '07:00')
            }
            
            market_calendar = session_manager.calendar_data.get('sessions', {})
            for session, times in required_sessions.items():
                if session not in market_calendar:
                    details['session_management']['status'] = 'ERROR'
                    details['session_management']['issues'].append(f'Missing {session} session configuration')
                elif market_calendar[session].get('open') != times[0] or market_calendar[session].get('close') != times[1]:
                    details['session_management']['status'] = 'WARNING'
                    details['session_management']['issues'].append(f'Incorrect {session} session times')
                else:
                    self.logger.info(f"Session {session} times verified")

            # 4. Trading Days Tracking Verification
            from src.core.ftmo_rule_manager import FTMORuleManager
            ftmo_manager = FTMORuleManager()
            
            if not hasattr(ftmo_manager, '_get_trading_days_count'):
                details['trading_days']['status'] = 'ERROR'
                details['trading_days']['issues'].append('Trading days tracking not implemented')
            else:
                self.logger.info("Trading days tracking method verified")

            # Generate overall status
            status = 'OK'
            if any(d['status'] == 'ERROR' for d in details.values()):
                status = 'ERROR'
            elif any(d['status'] == 'WARNING' for d in details.values()):
                status = 'WARNING'

            # Log comprehensive results
            self.logger.info(f"""
            ===== FTMO PHASE 1 AUDIT RESULTS =====
            Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            Overall Status: {status}
            
            Rule Engine Status: {details['rule_engine']['status']}
            Issues: {', '.join(details['rule_engine']['issues']) if details['rule_engine']['issues'] else 'None'}
            
            Logging System Status: {details['logging_system']['status']}
            Issues: {', '.join(details['logging_system']['issues']) if details['logging_system']['issues'] else 'None'}
            
            Session Management Status: {details['session_management']['status']}
            Issues: {', '.join(details['session_management']['issues']) if details['session_management']['issues'] else 'None'}
            
            Trading Days Status: {details['trading_days']['status']}
            Issues: {', '.join(details['trading_days']['issues']) if details['trading_days']['issues'] else 'None'}
            =====================================
            """)

            return AuditResult(
                module_name="FTMO_Phase1",
                status=status,
                message="Phase 1 audit completed",
                timestamp=datetime.now(),
                details=details
            )

        except Exception as e:
            self.logger.error(f"Error during FTMO Phase 1 audit: {str(e)}")
            return AuditResult(
                module_name="FTMO_Phase1",
                status="ERROR",
                message=f"Audit failed: {str(e)}",
                timestamp=datetime.now()
            )

    def _check_mt5_expert_status(self) -> AuditResult:
        """Check MT5 expert status directly"""
        try:
            from src.core.trading.mt5 import MT5Trader
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
            from src.core.market.watcher import MarketWatcher
            from src.core.trading.mt5 import MT5Trader
            
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
            from src.core.trading.positions import PositionManager
            from src.core.trading.mt5 import MT5Trader
            
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
            from src.core.trading.mt5 import MT5Trader
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
            from src.signals.providers.manager import SignalManager
            from src.core.trading.mt5 import MT5Trader
            
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
                from src.core.config_manager import ConfigManager
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
            from src.core.system.menu import MenuManager
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
        ftmo_status = self.audit_ftmo_phase1()
        self.results.append(ftmo_status)
        
        audit_functions = [
            self.audit_market_watcher,
            self.audit_position_manager,
            self.audit_signal_manager,
            self.audit_config_manager,
            self.audit_menu_manager
        ]
        
        self.results = [mt5_status, ftmo_status]
        
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