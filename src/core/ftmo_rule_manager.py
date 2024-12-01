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

        # Initialize FTMO Logger
        from src.utils.ftmo_logger import FTMOLogger
        self.ftmo_logger = FTMOLogger()
        self.logger.info("FTMO Logger initialized")
        
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
    
    def initialize_monitoring(self):
        """Initialize FTMO monitoring on startup"""
        try:
            self.logger.info("Initializing FTMO monitoring...")
            
            # Log initial account state
            account_info = self.mt5_trader.get_account_info()
            self.ftmo_logger.log_daily_loss(
                account_info['profit'],
                self.rules['trading_rules']['max_daily_loss']
            )
            
            # Log initial profit target
            self.ftmo_logger.log_profit_update(
                account_info['profit'],
                self.rules['trading_rules']['profit_target']
            )
            
            # Log initial status
            self.ftmo_logger.log_warning(
                "Startup",
                f"""FTMO Monitoring Started
                Balance: ${account_info['balance']:.2f}
                Equity: ${account_info['equity']:.2f}
                Profit Target: ${self.rules['trading_rules']['profit_target']:.2f}
                Daily Loss Limit: ${abs(self.rules['trading_rules']['max_daily_loss']):.2f}
                Total Loss Limit: ${abs(self.rules['trading_rules']['max_total_loss']):.2f}
                """
            )
            
            self.logger.info("FTMO monitoring initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing FTMO monitoring: {str(e)}")
            return False
    
    def track_trading_days_requirement(self) -> Dict:
        """
        Track and validate minimum trading days requirement
        Returns: Dict with trading days status and validation
        """
        try:
            self.logger.info("Checking trading days requirement...")
            
            # Get trading activity from last 30 days
            from datetime import datetime, timedelta
            start_date = datetime.now() - timedelta(days=30)
            
            # Get all positions (both open and closed)
            positions = self.mt5_trader.get_positions_history(start_date)
            
            # Track unique trading days and volume
            trading_days = {}
            for position in positions:
                trade_date = datetime.fromtimestamp(position['time']).date()
                if trade_date not in trading_days:
                    trading_days[trade_date] = {
                        'positions': 0,
                        'volume': 0.0,
                        'profit': 0.0
                    }
                trading_days[trade_date]['positions'] += 1
                trading_days[trade_date]['volume'] += position['volume']
                trading_days[trade_date]['profit'] += position['profit']

            # Calculate trading days metrics
            min_required = self.rules['trading_rules'].get('min_trading_days', 4)
            days_completed = len(trading_days)
            days_remaining = max(0, min_required - days_completed)
            
            # Validate daily activity
            valid_trading_days = 0
            for date, stats in trading_days.items():
                if stats['positions'] >= 1:  # At least one trade
                    valid_trading_days += 1

            result = {
                'status': 'COMPLIANT' if valid_trading_days >= min_required else 'PENDING',
                'days_completed': valid_trading_days,
                'days_required': min_required,
                'days_remaining': days_remaining,
                'trading_activity': trading_days,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # Log detailed trading days status
            self.ftmo_logger.log_trading_days_status(
                valid_trading_days,
                min_required,
                trading_days
            )

            # Log to main logger
            self.logger.info(f"""
            Trading Days Requirement Check:
            Status: {result['status']}
            Completed Days: {valid_trading_days}
            Required Days: {min_required}
            Remaining Days: {days_remaining}
            
            Trading Activity Summary:
            Total Trading Days: {len(trading_days)}
            Valid Trading Days: {valid_trading_days}
            Last Update: {result['last_update']}
            """)

            return result

        except Exception as e:
            self.logger.error(f"Error tracking trading days requirement: {str(e)}")
            return {
                'status': 'ERROR',
                'error': str(e),
                'days_completed': 0,
                'days_required': self.rules['trading_rules'].get('min_trading_days', 4),
                'days_remaining': self.rules['trading_rules'].get('min_trading_days', 4)
            }

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
        """
        Enhanced daily performance monitoring with proper logging
        
        Args:
            account_info: Current account information dictionary
        """
        try:
            current_time = datetime.now()
            
            # Reset daily stats if new day
            if current_time.date() > self.last_reset.date():
                self.logger.info("New trading day detected - Resetting daily statistics")
                self.daily_stats = {
                    'total_profit': 0,
                    'positions_opened': 0,
                    'max_drawdown': 0,
                    'trading_day_logged': False
                }
                self.last_reset = current_time

            # Update daily statistics
            current_profit = account_info['profit']
            previous_profit = self.daily_stats.get('total_profit', 0)
            
            self.daily_stats.update({
                'total_profit': current_profit,
                'previous_profit': previous_profit,
                'profit_change': current_profit - previous_profit
            })

            # Update max drawdown if needed
            if current_profit < self.daily_stats['max_drawdown']:
                self.daily_stats['max_drawdown'] = current_profit
                self.logger.warning(f"New maximum drawdown reached: ${current_profit:.2f}")

            # Calculate warning thresholds
            daily_limit = abs(self.rules['trading_rules']['max_daily_loss'])
            total_limit = abs(self.rules['trading_rules']['max_total_loss'])
            daily_warning = daily_limit * 0.8  # 80% of daily limit
            total_warning = total_limit * 0.8  # 80% of total limit

            # Log detailed status
            self.logger.info(f"""
            Daily Performance Update:
            Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
            Current Profit: ${current_profit:.2f}
            Max Drawdown: ${self.daily_stats['max_drawdown']:.2f}
            Daily Limit: ${daily_limit:.2f}
            Remaining: ${(daily_limit + current_profit):.2f}
            """)

            # Check and log warnings
            if abs(current_profit) >= daily_warning:
                warning_msg = f"WARNING: Approaching daily loss limit - Current: ${abs(current_profit):.2f} / Limit: ${daily_limit:.2f}"
                self.logger.warning(warning_msg)
                if hasattr(self, 'status_manager'):
                    self.status_manager.log_action(warning_msg)

            if account_info['balance'] <= self.rules['monitoring']['warning_threshold_total']:
                warning_msg = f"WARNING: Approaching total loss limit - Current: ${abs(account_info['balance']):.2f} / Limit: ${total_limit:.2f}"
                self.logger.warning(warning_msg)
                if hasattr(self, 'status_manager'):
                    self.status_manager.log_action(warning_msg)

            # Log daily summary if positions closed
            if not self.daily_stats.get('trading_day_logged') and len(self.position_manager.get_open_positions()) > 0:
                self.daily_stats['trading_day_logged'] = True
                self.logger.info("New trading day recorded in statistics")

        except Exception as e:
            self.logger.error(f"Error monitoring daily performance: {str(e)}")
            if hasattr(self, 'status_manager'):
                self.status_manager.log_action(f"Error in daily monitoring: {str(e)}")

    def track_daily_compliance(self, account_info: Dict):
        """
        Enhanced FTMO compliance tracking with detailed logging
        
        Args:
            account_info: Current account information dictionary
        """
        try:
            current_time = datetime.now()
            
            # Calculate current metrics
            daily_loss = abs(account_info['profit'])
            total_loss = abs(account_info['balance'] - account_info['equity'])
            daily_limit = abs(self.rules['trading_rules']['max_daily_loss'])
            total_limit = abs(self.rules['trading_rules']['max_total_loss'])
            
            # Get open positions
            positions = self.position_manager.get_open_positions() if hasattr(self, 'position_manager') else []
            active_positions = len(positions)
            
            # Calculate warning thresholds (80% of limits)
            daily_warning = daily_limit * 0.8
            total_warning = total_limit * 0.8
            
            # Get current session info if available
            market_session = "Unknown"
            if hasattr(self.mt5_trader, '_get_current_session'):
                market_session = self.mt5_trader._get_current_session()

            # Log comprehensive status
            self.logger.info(f"""
            ========== FTMO COMPLIANCE STATUS ==========
            Timestamp: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
            Market Session: {market_session}
            
            Daily P/L Status:
            - Current Loss: ${daily_loss:.2f}
            - Daily Limit: ${daily_limit:.2f}
            - Remaining: ${(daily_limit - daily_loss):.2f}
            - Warning Level: {daily_warning:.2f}
            
            Total Account Status:
            - Current Loss: ${total_loss:.2f}
            - Total Limit: ${total_limit:.2f}
            - Remaining: ${(total_limit - total_loss):.2f}
            - Warning Level: {total_warning:.2f}
            
            Position Status:
            - Active Positions: {active_positions}
            - Max Allowed: {self.rules['trading_rules']['max_positions']}
            
            Trading Day Status:
            - Trading Day Count: {self._get_trading_days_count()}
            - Min Required: {self.rules.get('trading_rules', {}).get('min_trading_days', 4)}
            ============================================
            """)

            # Log warnings if approaching limits
            if daily_loss >= daily_warning:
                self.logger.warning(f"ALERT: Approaching daily loss limit - Current: ${daily_loss:.2f} / Limit: ${daily_limit:.2f}")
            
            if total_loss >= total_warning:
                self.logger.warning(f"ALERT: Approaching total loss limit - Current: ${total_loss:.2f} / Limit: ${total_limit:.2f}")

            # Check each open position for duration
            for position in positions:
                duration_check = self.check_position_duration(position)
                if duration_check.get('warning', False):
                    self.logger.warning(f"""
                    Position Duration Warning:
                    Ticket: {position['ticket']}
                    Symbol: {position['symbol']}
                    Duration: {duration_check['duration']}
                    Max Allowed: {self.rules['time_rules']['max_position_duration']}min
                    """)

        except Exception as e:
            self.logger.error(f"Error tracking FTMO compliance: {str(e)}", exc_info=True)

    def track_trading_days(self) -> Dict:
        """
        Track and validate trading days requirement
        Returns: Dict with trading days status
        """
        try:
            self.logger.info("Starting trading days tracking...")
            
            # Get trading activity from last 30 days
            from datetime import datetime, timedelta
            start_date = datetime.now() - timedelta(days=30)
            
            # Get all positions (both open and closed)
            positions = self.mt5_trader.get_positions_history(start_date)
            
            # Track unique trading days
            trading_days = set()
            daily_volumes = {}
            
            for position in positions:
                trade_date = datetime.fromtimestamp(position['time']).date()
                trading_days.add(trade_date)
                
                # Track volume per day
                if trade_date not in daily_volumes:
                    daily_volumes[trade_date] = 0
                daily_volumes[trade_date] += position['volume']

            # Calculate required days
            required_days = self.rules['trading_rules'].get('min_trading_days', 4)
            days_completed = len(trading_days)
            days_remaining = max(0, required_days - days_completed)

            result = {
                'days_completed': days_completed,
                'days_required': required_days,
                'days_remaining': days_remaining,
                'daily_volumes': daily_volumes,
                'status': 'COMPLIANT' if days_completed >= required_days else 'PENDING',
                'trading_dates': sorted(list(trading_days))
            }

            # Log detailed tracking information
            self.logger.info(f"""
            Trading Days Status:
            Completed Days: {days_completed}
            Required Days: {required_days}
            Remaining Days: {days_remaining}
            Status: {result['status']}
            
            Trading Dates:
            {chr(10).join(d.strftime('%Y-%m-%d') for d in result['trading_dates'])}
            
            Daily Volumes:
            {chr(10).join(f"{date}: {volume} lots" for date, volume in daily_volumes.items())}
            """)

            return result

        except Exception as e:
            self.logger.error(f"Error tracking trading days: {str(e)}", exc_info=True)
            return {
                'days_completed': 0,
                'days_required': self.rules['trading_rules'].get('min_trading_days', 4),
                'days_remaining': self.rules['trading_rules'].get('min_trading_days', 4),
                'status': 'ERROR',
                'error': str(e)
            }

    def monitor_drawdown(self) -> Dict:
        """
        Enhanced drawdown monitoring with detailed tracking
        Returns: Dict with drawdown metrics
        """
        try:
            self.logger.info("Starting drawdown monitoring...")
            
            account_info = self.mt5_trader.get_account_info()
            
            # Calculate drawdown metrics
            current_balance = account_info['balance']
            current_equity = account_info['equity']
            
            # Update peak balance if needed
            if not hasattr(self, 'peak_balance') or current_balance > self.peak_balance:
                self.peak_balance = current_balance
                self.logger.info(f"New peak balance recorded: ${self.peak_balance:.2f}")

            # Calculate drawdown amounts
            absolute_drawdown = self.peak_balance - current_equity
            percentage_drawdown = (absolute_drawdown / self.peak_balance * 100) if self.peak_balance else 0
            
            # Calculate daily drawdown
            daily_high = getattr(self, 'daily_equity_high', current_equity)
            if current_equity > daily_high:
                self.daily_equity_high = current_equity
            daily_drawdown = self.daily_equity_high - current_equity
            daily_drawdown_percent = (daily_drawdown / self.daily_equity_high * 100) if self.daily_equity_high else 0

            result = {
                'current_drawdown': absolute_drawdown,
                'drawdown_percent': percentage_drawdown,
                'peak_balance': self.peak_balance,
                'current_equity': current_equity,
                'daily_drawdown': daily_drawdown,
                'daily_drawdown_percent': daily_drawdown_percent,
                'status': self._get_drawdown_status(percentage_drawdown)
            }

            # Log drawdown metrics
            self.logger.info(f"""
            Drawdown Monitoring Update:
            Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Overall Drawdown:
            - Peak Balance: ${self.peak_balance:.2f}
            - Current Equity: ${current_equity:.2f}
            - Absolute Drawdown: ${absolute_drawdown:.2f}
            - Drawdown Percentage: {percentage_drawdown:.2f}%
            
            Daily Metrics:
            - Daily High: ${self.daily_equity_high:.2f}
            - Daily Drawdown: ${daily_drawdown:.2f}
            - Daily Drawdown Percentage: {daily_drawdown_percent:.2f}%
            
            Status: {result['status']}
            """)

            # Add warning logs for significant drawdown
            if percentage_drawdown >= 8:  # 80% of 10% max drawdown
                self.logger.warning(f"CRITICAL: Approaching maximum drawdown limit ({percentage_drawdown:.2f}%)")
            elif percentage_drawdown >= 5:
                self.logger.warning(f"WARNING: Significant drawdown detected ({percentage_drawdown:.2f}%)")

            return result

        except Exception as e:
            self.logger.error(f"Error monitoring drawdown: {str(e)}", exc_info=True)
            return {
                'error': str(e),
                'status': 'ERROR'
            }

    def _get_drawdown_status(self, drawdown_percent: float) -> str:
        """Helper method to determine drawdown status"""
        if drawdown_percent >= 9:  # 90% of max drawdown
            return 'CRITICAL'
        elif drawdown_percent >= 7:  # 70% of max drawdown
            return 'WARNING'
        elif drawdown_percent >= 5:  # 50% of max drawdown
            return 'CAUTION'
        return 'NORMAL'

    def track_profit_target(self) -> Dict:
        """
        Track progress towards profit target
        Returns: Dict with profit metrics
        """
        try:
            self.logger.info("Starting profit target tracking...")
            
            account_info = self.mt5_trader.get_account_info()
            profit_target = self.rules['trading_rules'].get('profit_target', 1000)
            
            # Calculate current profit
            current_profit = account_info['profit']
            progress_percent = (current_profit / profit_target * 100) if profit_target else 0
            
            result = {
                'current_profit': current_profit,
                'target': profit_target,
                'remaining': profit_target - current_profit,
                'progress_percent': progress_percent,
                'status': self._get_profit_status(progress_percent)
            }

            # Log profit tracking
            self.logger.info(f"""
            Profit Target Tracking:
            Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Progress:
            - Current Profit: ${current_profit:.2f}
            - Target: ${profit_target:.2f}
            - Remaining: ${result['remaining']:.2f}
            - Progress: {progress_percent:.2f}%
            
            Status: {result['status']}
            """)

            return result

        except Exception as e:
            self.logger.error(f"Error tracking profit target: {str(e)}", exc_info=True)
            return {
                'error': str(e),
                'status': 'ERROR'
            }

    def _get_profit_status(self, progress_percent: float) -> str:
        """Helper method to determine profit status"""
        if progress_percent >= 100:
            return 'TARGET_REACHED'
        elif progress_percent >= 75:
            return 'NEAR_TARGET'
        elif progress_percent >= 50:
            return 'ON_TRACK'
        return 'IN_PROGRESS'

    def monitor_ftmo_status(self) -> Dict:
        """
        Monitor FTMO compliance status even during closed markets
        Returns: Dict with full status details
        """
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            account_info = self.mt5_trader.get_account_info()

            # Get market status
            is_weekend = datetime.now().weekday() >= 5
            market_message = "CLOSED - Weekend" if is_weekend else "CLOSED - After Hours"

            # Calculate trading day status
            trading_days = self._get_trading_days_count()
            days_remaining = max(0, self.rules.get('trading_rules', {}).get('min_trading_days', 4) - trading_days)

            # Calculate account metrics
            current_balance = account_info['balance']
            current_equity = account_info['equity']
            daily_loss_limit = abs(self.rules['trading_rules']['max_daily_loss'])
            total_loss_limit = abs(self.rules['trading_rules']['max_total_loss'])

            # Update peak balance if needed
            if not hasattr(self, 'peak_balance') or current_balance > self.peak_balance:
                self.peak_balance = current_balance
            
            drawdown = self.peak_balance - current_equity if hasattr(self, 'peak_balance') else 0
            drawdown_percent = (drawdown / self.peak_balance * 100) if self.peak_balance else 0

            status = {
                'market_status': market_message,
                'timestamp': timestamp,
                'account_status': {
                    'balance': current_balance,
                    'equity': current_equity,
                    'daily_loss_used': abs(account_info['profit']),
                    'daily_loss_limit': daily_loss_limit,
                    'total_loss_limit': total_loss_limit,
                    'drawdown': drawdown,
                    'drawdown_percent': drawdown_percent
                },
                'trading_progress': {
                    'days_completed': trading_days,
                    'days_remaining': days_remaining,
                    'min_required': self.rules.get('trading_rules', {}).get('min_trading_days', 4)
                },
                'rules_status': {
                    'position_duration_limit': f"{self.rules['time_rules']['max_position_duration']} minutes",
                    'max_positions': self.rules['trading_rules']['max_positions']
                },
                'warnings': []
            }

            # Add relevant warnings
            if drawdown_percent >= 8:  # 80% of 10% max drawdown
                status['warnings'].append(f"High Drawdown Level: {drawdown_percent:.2f}%")

            if abs(account_info['profit']) >= daily_loss_limit * 0.8:
                status['warnings'].append(f"Approaching Daily Loss Limit: {abs(account_info['profit']):.2f}/{daily_loss_limit:.2f}")

            # Log detailed status
            self.logger.info(f"""
            ========== FTMO STATUS MONITORING ==========
            Timestamp: {timestamp}
            Market Status: {market_message}

            Account Status:
            - Balance: ${current_balance:.2f}
            - Equity: ${current_equity:.2f}
            - Daily Loss Used: ${abs(account_info['profit']):.2f} / ${daily_loss_limit:.2f}
            - Current Drawdown: ${drawdown:.2f} ({drawdown_percent:.2f}%)
            
            Trading Progress:
            - Days Completed: {trading_days}
            - Days Remaining: {days_remaining}
            - Minimum Required: {status['trading_progress']['min_required']}

            FTMO Rules:
            - Position Duration Limit: {status['rules_status']['position_duration_limit']}
            - Maximum Positions: {status['rules_status']['max_positions']}

            Warnings:
            {chr(10).join(status['warnings']) if status['warnings'] else 'None'}
            =============================================
            """)

            return status

        except Exception as e:
            self.logger.error(f"Error monitoring FTMO status: {str(e)}", exc_info=True)
            return {
                'error': str(e),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def log_trading_activity(self, activity_type: str, data: Dict):
        """
        Log detailed trading activity with FTMO compliance checks
        
        Args:
            activity_type: Type of activity ('POSITION_OPEN', 'POSITION_CLOSE', 'DURATION_CHECK', 'LOSS_CHECK')
            data: Dictionary containing activity details
        """
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Basic activity logging
            self.logger.info(f"""
            ========== FTMO TRADING ACTIVITY ==========
            Time: {timestamp}
            Type: {activity_type}
            """)

            # Log specific activity details based on type
            if activity_type == 'POSITION_OPEN':
                self.logger.info(f"""
                New Position:
                Symbol: {data.get('symbol')}
                Type: {data.get('type')}
                Volume: {data.get('volume')}
                Entry Price: {data.get('entry_price')}
                SL: {data.get('stop_loss')}
                TP: {data.get('take_profit')}
                """)
                
                # Check position count
                positions = self.mt5_trader.get_positions() if hasattr(self, 'mt5_trader') else []
                self.logger.info(f"Total Positions: {len(positions)}/{self.rules['trading_rules']['max_positions']}")

            elif activity_type == 'POSITION_CLOSE':
                self.logger.info(f"""
                Closed Position:
                Ticket: {data.get('ticket')}
                Symbol: {data.get('symbol')}
                Profit/Loss: ${data.get('profit', 0):.2f}
                Duration: {data.get('duration')}
                """)
                
                # Check daily loss limit
                account_info = self.mt5_trader.get_account_info() if hasattr(self, 'mt5_trader') else {'profit': 0}
                daily_loss = abs(account_info['profit'])
                self.logger.info(f"Daily P/L: ${-daily_loss:.2f}/{self.rules['trading_rules']['max_daily_loss']}")

            elif activity_type == 'DURATION_CHECK':
                self.logger.info(f"""
                Duration Check:
                Ticket: {data.get('ticket')}
                Symbol: {data.get('symbol')}
                Current Duration: {data.get('duration')}
                Max Allowed: {self.rules['time_rules']['max_position_duration']}min
                Status: {data.get('status', 'OK')}
                """)

            elif activity_type == 'LOSS_CHECK':
                self.logger.info(f"""
                Loss Check:
                Daily Loss: ${abs(data.get('daily_loss', 0)):.2f}/{abs(self.rules['trading_rules']['max_daily_loss'])}
                Total Loss: ${abs(data.get('total_loss', 0)):.2f}/{abs(self.rules['trading_rules']['max_total_loss'])}
                Status: {data.get('status', 'OK')}
                """)

            self.logger.info("==========================================")

        except Exception as e:
            self.logger.error(f"Error logging trading activity: {str(e)}", exc_info=True)

    def monitor_trading_status(self) -> Dict:
        """
        Real-time monitoring of FTMO rule compliance
        Returns Dict with current status and any violations
        """
        try:
            if not hasattr(self, 'mt5_trader') or not self.mt5_trader:
                self.logger.error("MT5 trader not initialized")
                return {'error': 'MT5 trader not initialized'}

            # Get current account info
            account_info = self.mt5_trader.get_account_info()
            
            # Calculate daily stats
            current_profit = account_info['profit']
            daily_loss_limit = abs(self.rules['trading_rules']['max_daily_loss'])
            daily_loss_used = (abs(current_profit) / daily_loss_limit) * 100 if current_profit < 0 else 0
            
            # Calculate drawdown
            if not hasattr(self, 'peak_balance'):
                self.peak_balance = account_info['balance']
            elif account_info['balance'] > self.peak_balance:
                self.peak_balance = account_info['balance']
            
            current_drawdown = self.peak_balance - account_info['balance']
            drawdown_percentage = (current_drawdown / self.peak_balance) * 100 if self.peak_balance else 0
            
            # Get active positions with durations
            positions = self.mt5_trader.get_positions() if hasattr(self.mt5_trader, 'get_positions') else []
            position_details = []
            duration_warnings = []
            
            for position in positions:
                duration_check = self.check_position_duration(position)
                position_details.append({
                    'ticket': position['ticket'],
                    'symbol': position['symbol'],
                    'duration': duration_check['duration'],
                    'warning': duration_check['warning']
                })
                if duration_check['warning']:
                    duration_warnings.append(f"Position {position['ticket']} duration: {duration_check['duration']}")

            # Get trading days count
            trading_days = self._get_trading_days_count()
            
            # Compile status report
            status = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'daily_performance': {
                    'current_profit': current_profit,
                    'loss_limit_used': f"{daily_loss_used:.2f}%",
                    'remaining_loss_allowed': daily_loss_limit - abs(current_profit)
                },
                'drawdown': {
                    'current_drawdown': current_drawdown,
                    'percentage': f"{drawdown_percentage:.2f}%",
                    'peak_balance': self.peak_balance
                },
                'positions': {
                    'active_count': len(positions),
                    'max_allowed': self.rules['trading_rules']['max_positions'],
                    'details': position_details
                },
                'trading_days': {
                    'count': trading_days,
                    'required': self.rules.get('trading_rules', {}).get('min_trading_days', 4)
                },
                'warnings': []
            }

            # Check for warnings/violations
            if daily_loss_used >= 80:
                status['warnings'].append(f"CRITICAL: Approaching daily loss limit ({daily_loss_used:.2f}%)")
            if drawdown_percentage >= 8:  # 80% of 10% max drawdown
                status['warnings'].append(f"WARNING: High drawdown level ({drawdown_percentage:.2f}%)")
            if duration_warnings:
                status['warnings'].extend(duration_warnings)

            # Log comprehensive status
            self.logger.info(f"""
            ========== FTMO STATUS UPDATE ==========
            Time: {status['timestamp']}
            
            Daily Performance:
            - Current P/L: ${current_profit:.2f}
            - Loss Limit Used: {status['daily_performance']['loss_limit_used']}
            - Remaining Allowance: ${status['daily_performance']['remaining_loss_allowed']:.2f}
            
            Drawdown Status:
            - Current Drawdown: ${current_drawdown:.2f}
            - Drawdown %: {status['drawdown']['percentage']}
            - Peak Balance: ${self.peak_balance:.2f}
            
            Position Status:
            - Active Positions: {status['positions']['active_count']}/{status['positions']['max_allowed']}
            - Positions with Warnings: {len(duration_warnings)}
            
            Trading Progress:
            - Trading Days: {status['trading_days']['count']}/{status['trading_days']['required']}
            
            Warnings/Violations:
            {chr(10).join(status['warnings']) if status['warnings'] else 'None'}
            =======================================
            """)

            return status

        except Exception as e:
            self.logger.error(f"Error monitoring FTMO status: {str(e)}", exc_info=True)
            return {'error': str(e)}

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