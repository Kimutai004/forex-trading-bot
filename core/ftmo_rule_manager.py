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
    
    def check_position_duration(self, position: Dict) -> Dict:
        """
        Check if position has exceeded maximum duration
        
        Args:
            position: Position dictionary from PositionManager
            
        Returns:
            Dict with status and duration information
        """
        try:
            self.logger.info(f"Checking duration for position {position['ticket']}")
            current_time = datetime.now()
            max_duration = self.rules['time_rules']['max_position_duration']  # in minutes

            # Convert timestamp to datetime, handling both string and numeric formats
            if isinstance(position['time'], str):
                try:
                    open_time = datetime.strptime(position['time'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # If string parsing fails, try to convert from timestamp string
                    open_time = datetime.fromtimestamp(float(position['time']))
            else:
                # If it's already a number (int or float)
                open_time = datetime.fromtimestamp(position['time'])

            duration = current_time - open_time
            duration_minutes = duration.total_seconds() / 60
            
            # Format duration string
            hours = int(duration_minutes // 60)
            minutes = int(duration_minutes % 60)
            duration_str = f"{hours}h {minutes}m"
            
            result = {
                'needs_closure': duration_minutes >= max_duration,
                'duration': duration_str,
                'duration_minutes': duration_minutes,
                'max_duration': max_duration,
                'open_time': open_time.strftime('%Y-%m-%d %H:%M:%S'),
                'warning': duration_minutes >= (max_duration * 0.75)  # Warning at 75% of max duration
            }

            self.logger.info(f"Duration check result for position {position['ticket']}: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error checking position duration for ticket {position.get('ticket', 'unknown')}: {str(e)}")
            return {
                'needs_closure': False,
                'duration': "0h 0m",
                'duration_minutes': 0,
                'max_duration': self.rules['time_rules']['max_position_duration'],
                'open_time': "Unknown",
                'warning': False
            }

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
        
    def check_position_duration(self, position: Dict) -> Dict:
        """
        Check if position has exceeded maximum duration
        """
        try:
            self.logger.info(f"Checking duration for position {position['ticket']}")
            current_time = datetime.now()
            max_duration = self.rules['time_rules']['max_position_duration']  # in minutes
            
            # Calculate position duration
            open_time = datetime.fromtimestamp(position['time'])
            duration = current_time - open_time
            duration_minutes = duration.total_seconds() / 60
            
            # Format duration string
            duration_str = f"{int(duration_minutes // 60)}h {int(duration_minutes % 60)}m"
            
            result = {
                'needs_closure': duration_minutes >= max_duration,
                'duration': duration_str,
                'duration_minutes': duration_minutes,
                'max_duration': max_duration,
                'open_time': open_time.strftime('%Y-%m-%d %H:%M:%S'),
                'warning': duration_minutes >= (max_duration * 0.75)
            }

            if result['warning']:
                self.logger.warning(f"Position {position['ticket']} approaching time limit. Duration: {duration_str}")
            if result['needs_closure']:
                self.logger.warning(f"Position {position['ticket']} exceeded time limit. Duration: {duration_str}")

            return result
            
        except Exception as e:
            self.logger.error(f"Error checking position duration for ticket {position.get('ticket', 'unknown')}: {str(e)}")
            return {
                'needs_closure': False,
                'duration': "0h 0m",
                'duration_minutes': 0,
                'max_duration': self.rules['time_rules']['max_position_duration'],
                'open_time': "Unknown",
                'warning': False
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