"""
Settings Management Module
Handles user settings persistence and access
"""

import json
import os
import logging


class SettingsManager:
    """Manages user settings persistence"""
    
    DEFAULT_SETTINGS = {
        'zoom': 1.0,
        'dpi': 150,
        'full_refresh_interval': 5,
        'show_page_numbers': True,
        'sleep_enabled': True,
        'sleep_message': "Shh I'm sleeping",
        'sleep_timeout': 120,
        'shutdown_message': 'OFF',
        'wifi_while_reading': False,
        'items_per_page': 4,
        'undervolt': -2
    }
    
    def __init__(self, settings_file='settings.json', logger=None):
        """
        Initialize settings manager
        
        Args:
            settings_file: Path to settings JSON file
            logger: Logger instance (optional)
        """
        self.settings_file = settings_file
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.load()
    
    def load(self):
        """Load settings from file"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    settings = self.DEFAULT_SETTINGS.copy()
                    settings.update(loaded_settings)
                    return settings
            except Exception as e:
                self.logger.warning(f"Failed to load settings: {e}. Using defaults.")
                return self.DEFAULT_SETTINGS.copy()
        else:
            # Create default settings file
            self.save(self.DEFAULT_SETTINGS)
            return self.DEFAULT_SETTINGS.copy()
    
    def save(self, settings=None):
        """
        Save settings to file
        
        Args:
            settings: Settings dict to save (uses self.settings if None)
        """
        if settings is not None:
            self.settings = settings
        
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            self.logger.info("Settings saved successfully")
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
    
    def get(self, key, default=None):
        """
        Get a setting value
        
        Args:
            key: Setting key
            default: Default value if key doesn't exist
            
        Returns:
            Setting value or default
        """
        return self.settings.get(key, default)
    
    def set(self, key, value):
        """
        Set a setting value
        
        Args:
            key: Setting key
            value: Setting value
        """
        self.settings[key] = value
    
    def update(self, updates):
        """
        Update multiple settings
        
        Args:
            updates: Dict of settings to update
        """
        self.settings.update(updates)
    
    def get_all(self):
        """Get all settings"""
        return self.settings.copy()
