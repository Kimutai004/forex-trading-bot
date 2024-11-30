from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
from logger_config import setup_logger

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
            mode='AUTOMATED',
            started_at=datetime.now()
        )
        self.module_statuses: Dict[str, ModuleStatus] = {}
        self.activity_log: List[str] = []
        
    def _setup_logging(self):
        """Setup logging for status manager"""
        from logger_config import setup_logger, get_implementation_logger
        self.logger = setup_logger('BotStatusManager')
        impl_logger = get_implementation_logger()
        impl_logger.info("BotStatusManager initialized with centralized logging")

    def start_bot(self):
        """Mark bot as active"""
        self.bot_status.is_active = True
        self.bot_status.started_at = datetime.now()
        self._log_activity("Bot started")
        self.logger.error("Bot Started") # Show on dashboard
        self.logger.info("Bot startup sequence completed") # Log file only

    def stop_bot(self):
        """Mark bot as inactive"""
        self.bot_status.is_active = False
        self._log_activity("Bot stopped")
        self.logger.error("Bot Stopped") # Show on dashboard
        self.logger.info("Bot shutdown sequence completed") # Log file only

    def set_mode(self, mode: str):
        """Set bot operation mode"""
        if mode not in ['AUTOMATED', 'MANUAL']:
            raise ValueError("Invalid mode. Must be 'AUTOMATED' or 'MANUAL'")
        self.bot_status.mode = mode
        self._log_activity(f"Mode changed to {mode}")
        self.logger.error(f"Bot Mode: {mode}") # Show on dashboard
        self.logger.info(f"Operation mode updated to {mode}") # Log file onl

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
            self.logger.error(f"Module {module_name} Error: {message}")  # Show on dashboard
        elif status == 'WARNING':
            self.bot_status.warnings_count += 1
            self.logger.warning(f"Module {module_name}: {message}")  # Log file only
        else:
            self.logger.debug(f"Module {module_name} status updated: {status}")  # Log file only

    def log_action(self, action: str, operation: str = None):
        """Log bot action"""
        self.bot_status.last_action = action
        self.bot_status.last_action_time = datetime.now()
        if operation:
            self.bot_status.current_operation = operation
        self._log_activity(action)
        self.logger.info(f"Action: {action}")  # Log file only


    def _log_activity(self, activity: str):
        """Add activity to log with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"{timestamp} - {activity}"
        self.activity_log.append(log_entry)
        
        # Keep only last 1000 entries
        if len(self.activity_log) > 1000:
            self.activity_log = self.activity_log[-1000:]
        
        self.logger.debug(f"Activity logged: {activity}")  # Log file only

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