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