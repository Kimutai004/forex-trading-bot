import logging
from datetime import datetime
import os
from typing import Dict

class FTMOLogger:
    def __init__(self, log_dir: str = "trading_logs"):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Setup specific FTMO log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.ftmo_log_file = os.path.join(log_dir, f"ftmo_activity_{timestamp}.log")
        
        # Configure logger
        self.logger = logging.getLogger('FTMOLogger')
        self.logger.setLevel(logging.INFO)
        
        # File handler for FTMO specific logs
        fh = logging.FileHandler(self.ftmo_log_file)
        formatter = logging.Formatter(
            '%(asctime)s - FTMO - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def log_daily_loss(self, current_loss: float, max_loss: float):
        """Log daily loss status"""
        percentage = (abs(current_loss) / abs(max_loss)) * 100
        message = f"""
        Daily Loss Update:
        Current Loss: ${abs(current_loss):.2f}
        Maximum Allowed: ${abs(max_loss):.2f}
        Percentage Used: {percentage:.2f}%
        """
        if percentage >= 80:
            self.logger.critical(message)
        elif percentage >= 60:
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def log_profit_update(self, current_profit: float, target: float):
        """Log profit tracking status"""
        percentage = (current_profit / target) * 100 if target != 0 else 0
        self.logger.info(f"""
        Profit Tracking Update:
        Current Profit: ${current_profit:.2f}
        Target: ${target:.2f}
        Progress: {percentage:.2f}%
        """)

    def log_violation(self, rule_type: str, details: str):
        """Log rule violations"""
        self.logger.error(f"""
        FTMO RULE VIOLATION:
        Type: {rule_type}
        Details: {details}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """)

    def log_trading_days_status(self, completed_days: int, required_days: int, trading_activity: Dict):
        """Log trading days requirement status"""
        message = f"""
        Trading Days Status Update:
        Completed Valid Days: {completed_days}
        Required Days: {required_days}
        Remaining Days: {max(0, required_days - completed_days)}
        
        Trading Activity Details:
        """
        
        for date, stats in trading_activity.items():
            message += f"""
        {date}:
            Positions: {stats['positions']}
            Volume: {stats['volume']:.2f}
            Profit: ${stats['profit']:.2f}
        """
        
        if completed_days >= required_days:
            self.logger.info(message)
        elif completed_days >= required_days * 0.75:  # 75% complete
            self.logger.warning(message + "\nApproaching trading days requirement deadline")
        else:
            self.logger.info(message)

    def log_warning(self, rule_type: str, details: str):
        """Log rule warnings"""
        self.logger.warning(f"""
        FTMO RULE WARNING:
        Type: {rule_type}
        Details: {details}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """)