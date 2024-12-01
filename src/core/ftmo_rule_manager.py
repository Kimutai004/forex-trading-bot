from typing import Dict, List, Optional
from datetime import datetime
import logging
import json
import os

class FTMORuleManager:
    def __init__(self, config_dir: str = "config"):
        """Initialize FTMO Rule Manager"""
        # Setup logging first
        self._setup_logging()
        self.logger.info("Initializing FTMO Rule Manager...")
        
        # Initialize attributes
        self.config_dir = config_dir
        self.rules_file = os.path.join(config_dir, "ftmo_rules.json")
        self.mt5_trader = None
        
        # Load rules
        self.rules = self._load_rules()
        self.logger.info("FTMO rules loaded successfully")
        
        # Initialize stats
        self.daily_stats = {
            'total_profit': 0,
            'positions_opened': 0,
            'max_drawdown': 0
        }
        self.last_reset = datetime.now()
        
        # Log initialization details
        self.logger.info(f"""
        FTMO Manager Initialized:
        Max Position Duration: {self.rules['time_rules']['max_position_duration']} minutes
        Daily Loss Limit: ${abs(self.rules['trading_rules']['max_daily_loss'])}
        Total Loss Limit: ${abs(self.rules['trading_rules']['max_total_loss'])}
        Position Duration Warning: {self.rules['trading_rules']['position_duration']['warning_threshold'] * 100}%
        """)

    def set_mt5_trader(self, mt5_trader):
        """Set MT5 trader instance for position management"""
        self.mt5_trader = mt5_trader
        self.logger.info("MT5 trader instance set in FTMO rule manager")

    def _setup_logging(self):
        """Setup centralized logging for FTMO rule manager"""
        from src.utils.logger import setup_logger, get_implementation_logger
        self.logger = setup_logger('FTMORuleManager')
        impl_logger = get_implementation_logger()
        impl_logger.info("FTMORuleManager logging configured with centralized system")

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
    
    def check_position_duration(self, position: Dict) -> Dict:
        """
        Enhanced position duration check with automatic closure and market status awareness
        
        Args:
            position: Position dictionary from PositionManager
                
        Returns:
            Dict with status and duration information
        """
        try:
            self.logger.info(f"Checking duration for position {position['ticket']}")
            current_time = datetime.now()
            
            # Get max duration from rules
            max_duration_minutes = self.rules['time_rules']['max_position_duration']
            warning_threshold = self.rules['trading_rules']['position_duration']['warning_threshold']
            
            # Convert timestamp to datetime
            if isinstance(position['time'], str):
                try:
                    open_time = datetime.strptime(position['time'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    open_time = datetime.fromtimestamp(float(position['time']))
            else:
                open_time = datetime.fromtimestamp(position['time'])

            duration = current_time - open_time
            duration_minutes = duration.total_seconds() / 60
            
            # Format duration string
            hours = int(duration_minutes // 60)
            minutes = int(duration_minutes % 60)
            duration_str = f"{hours}h {minutes}m"
            
            result = {
                'needs_closure': duration_minutes >= max_duration_minutes,
                'duration': duration_str,
                'duration_minutes': duration_minutes,
                'max_duration': max_duration_minutes,
                'open_time': open_time.strftime('%Y-%m-%d %H:%M:%S'),
                'warning': duration_minutes >= (max_duration_minutes * warning_threshold)
            }

            # Log appropriate warnings and take action
            if result['warning'] and not result['needs_closure']:
                warning_msg = f"Position {position['ticket']} approaching time limit. Duration: {duration_str}, Max: {max_duration_minutes}min"
                self.logger.warning(warning_msg)
                result['warning_message'] = warning_msg
                
            if result['needs_closure']:
                closure_msg = f"Position {position['ticket']} exceeded time limit. Duration: {duration_str}, Max: {max_duration_minutes}min"
                self.logger.warning(closure_msg)
                result['closure_message'] = closure_msg
                
                # Check market status first
                if hasattr(self, 'mt5_trader'):
                    if self.mt5_trader.market_is_open:
                        try:
                            success, message = self.mt5_trader.close_trade(position['ticket'])
                            result['closure_attempt'] = {
                                'success': success,
                                'message': message,
                                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
                            }
                            
                            if success:
                                self.logger.info(f"Successfully closed position {position['ticket']} due to duration limit")
                            else:
                                self.logger.error(f"Failed to close position {position['ticket']}: {message}")
                        except Exception as e:
                            self.logger.error(f"Error attempting to close position {position['ticket']}: {str(e)}")
                            result['closure_attempt'] = {
                                'success': False,
                                'message': str(e),
                                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
                            }
                    else:
                        market_status_msg = f"Market CLOSED - Cannot close position {position['ticket']} now. Will attempt closure when market opens."
                        self.logger.warning(market_status_msg)
                        result['market_closed'] = True
                        result['closure_queued'] = True
                        result['market_status_message'] = market_status_msg
                        
                        # Add to queued closures
                        self._add_to_queued_closures(position['ticket'])
                else:
                    self.logger.warning(f"MT5 trader not initialized - Cannot close position {position['ticket']}")

            # Log detailed duration check results
            self.logger.info(f"""
            Position Duration Check Results:
            Ticket: {position['ticket']}
            Symbol: {position['symbol']}
            Duration: {duration_str}
            Max Allowed: {max_duration_minutes} minutes
            Needs Closure: {result['needs_closure']}
            Warning Level: {result['warning']}
            Open Time: {result['open_time']}
            Market Status: {'OPEN' if hasattr(self, 'mt5_trader') and self.mt5_trader.market_is_open else 'CLOSED'}
            """)

            return result
                
        except Exception as e:
            error_msg = f"Error checking position duration for ticket {position.get('ticket', 'unknown')}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'needs_closure': False,
                'duration': "0h 0m",
                'duration_minutes': 0,
                'max_duration': self.rules['time_rules']['max_position_duration'],
                'open_time': "Unknown",
                'warning': False,
                'error': error_msg
            }

    def _add_to_queued_closures(self, ticket: int):
        """Add position to queued closures list"""
        if not hasattr(self, '_queued_closures'):
            self._queued_closures = set()
        self._queued_closures.add(ticket)
        self.logger.info(f"Added position {ticket} to queued closures")

    def process_queued_closures(self) -> List[Dict]:
        """
        Process positions queued for closure when market opens
        Returns: List of closure attempts and their results
        """
        if not hasattr(self, '_queued_closures') or not self._queued_closures:
            return []
            
        if not hasattr(self, 'mt5_trader') or not self.mt5_trader.market_is_open:
            self.logger.info("Market still closed - keeping positions in queue")
            return []
            
        results = []
        for ticket in list(self._queued_closures):
            try:
                success, message = self.mt5_trader.close_trade(ticket)
                result = {
                    'ticket': ticket,
                    'success': success,
                    'message': message,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                results.append(result)
                
                if success:
                    self._queued_closures.remove(ticket)
                    self.logger.info(f"Successfully closed queued position {ticket}")
                else:
                    self.logger.error(f"Failed to close queued position {ticket}: {message}")
                    
            except Exception as e:
                self.logger.error(f"Error processing queued closure for position {ticket}: {str(e)}")
                results.append({
                    'ticket': ticket,
                    'success': False,
                    'message': str(e),
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
        return results

    def get_queued_closures(self) -> List[Dict]:
        """Get list of positions queued for closure"""
        try:
            queued_closures = []
            positions = self.mt5_trader.get_positions()
            
            for position in positions:
                duration_check = self.check_position_duration(position)
                if duration_check.get('needs_closure', False):
                    queued_closures.append({
                        'ticket': position['ticket'],
                        'symbol': position['symbol'],
                        'duration': duration_check['duration'],
                        'queued_since': duration_check['open_time']
                    })
                    
            self.logger.info(f"Found {len(queued_closures)} positions queued for closure")
            return queued_closures
            
        except Exception as e:
            self.logger.error(f"Error getting queued closures: {str(e)}")
            return []

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
    
    def check_ftmo_compliance(self, account_info: Dict, position: Dict = None) -> Dict:
        """
        Comprehensive FTMO rule check
        
        Args:
            account_info: Current account information
            position: Optional current position being considered
            
        Returns:
            Dict with compliance status and details
        """
        try:
            self.logger.info("Starting FTMO compliance check...")
            
            # Initialize compliance result
            compliance = {
                'compliant': True,
                'violations': [],
                'warnings': [],
                'daily_loss_status': {
                    'current': account_info['profit'],
                    'limit': self.rules['trading_rules']['max_daily_loss'],
                    'remaining': abs(self.rules['trading_rules']['max_daily_loss']) - abs(account_info['profit'])
                },
                'total_loss_status': {
                    'current': account_info['balance'] - account_info['equity'],
                    'limit': self.rules['trading_rules']['max_total_loss'],
                    'remaining': abs(self.rules['trading_rules']['max_total_loss']) - abs(account_info['balance'] - account_info['equity'])
                },
                'trading_days': self._get_trading_days_count()
            }

            # Check daily loss
            if abs(account_info['profit']) >= abs(self.rules['trading_rules']['max_daily_loss']):
                compliance['compliant'] = False
                violation = "Daily loss limit exceeded"
                compliance['violations'].append(violation)
                self.logger.error(f"FTMO Violation: {violation}")
            elif abs(account_info['profit']) >= abs(self.rules['trading_rules']['max_daily_loss'] * 0.8):
                warning = "Approaching daily loss limit"
                compliance['warnings'].append(warning)
                self.logger.warning(f"FTMO Warning: {warning}")

            # Check total loss
            total_loss = account_info['balance'] - account_info['equity']
            if abs(total_loss) >= abs(self.rules['trading_rules']['max_total_loss']):
                compliance['compliant'] = False
                violation = "Total loss limit exceeded"
                compliance['violations'].append(violation)
                self.logger.error(f"FTMO Violation: {violation}")
            elif abs(total_loss) >= abs(self.rules['trading_rules']['max_total_loss'] * 0.8):
                warning = "Approaching total loss limit"
                compliance['warnings'].append(warning)
                self.logger.warning(f"FTMO Warning: {warning}")

            # Check position duration if position provided
            if position:
                duration_check = self.check_position_duration(position)
                compliance['duration_check'] = duration_check
                
                if duration_check['needs_closure']:
                    compliance['compliant'] = False
                    violation = f"Position {position['ticket']} exceeded maximum duration"
                    compliance['violations'].append(violation)
                    self.logger.error(f"FTMO Violation: {violation}")
                elif duration_check['warning']:
                    warning = f"Position {position['ticket']} approaching duration limit"
                    compliance['warnings'].append(warning)
                    self.logger.warning(f"FTMO Warning: {warning}")

            # Log compliance status
            self.logger.info(f"""
            FTMO Compliance Check Results:
            Compliant: {compliance['compliant']}
            Daily Loss: ${abs(account_info['profit'])} / ${abs(self.rules['trading_rules']['max_daily_loss'])}
            Total Loss: ${abs(total_loss)} / ${abs(self.rules['trading_rules']['max_total_loss'])}
            Trading Days: {compliance['trading_days']}
            Violations: {len(compliance['violations'])}
            Warnings: {len(compliance['warnings'])}
            """)

            return compliance

        except Exception as e:
            self.logger.error(f"Error in FTMO compliance check: {str(e)}", exc_info=True)
            return {
                'compliant': False,
                'violations': [f"Error checking compliance: {str(e)}"],
                'warnings': []
            }
        
    def _get_trading_days_count(self) -> int:
        """Calculate number of trading days in current period"""
        try:
            # Get trading activity from MT5
            from datetime import datetime, timedelta
            
            start_date = datetime.now() - timedelta(days=30)  # Look back 30 days
            trading_days = set()  # Use set to count unique days
            
            # Get all positions (both open and closed)
            positions = self.mt5_trader.get_positions_history(start_date)
            
            for position in positions:
                trade_date = datetime.fromtimestamp(position['time']).date()
                trading_days.add(trade_date)
                
            count = len(trading_days)
            self.logger.info(f"Trading days count: {count} in last 30 days")
            return count
            
        except Exception as e:
            self.logger.error(f"Error counting trading days: {str(e)}")
            return 0