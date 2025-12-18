"""
Configuration management for PiBook.
Loads and manages YAML configuration files.
PORTABILITY: 100% portable between Pi 3B+ and Pi Zero 2 W
"""

import yaml
import os
from typing import Any, Dict
import logging


class Config:
    """
    Application configuration manager
    """

    def __init__(self, config_path: str):
        """
        Load configuration from YAML file

        Args:
            config_path: Path to config.yaml
        """
        self.logger = logging.getLogger(__name__)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r') as f:
            self._config = yaml.safe_load(f)

        # Expand environment variables in paths
        self._expand_paths(self._config)

        self.logger.info(f"Configuration loaded from {config_path}")

    def _expand_paths(self, config: Dict):
        """Recursively expand environment variables in path strings"""
        for key, value in config.items():
            if isinstance(value, dict):
                self._expand_paths(value)
            elif isinstance(value, str) and ('$' in value or '~' in value):
                config[key] = os.path.expandvars(os.path.expanduser(value))

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation

        Args:
            path: Configuration path (e.g., 'display.width')
            default: Default value if path doesn't exist

        Returns:
            Configuration value
        """
        keys = path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, path: str, value: Any):
        """
        Set configuration value using dot notation

        Args:
            path: Configuration path (e.g., 'display.width')
            value: Value to set
        """
        keys = path.split('.')
        config = self._config

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        config[keys[-1]] = value
        self.logger.debug(f"Config set: {path} = {value}")

    def save(self, config_path: str):
        """
        Save configuration to YAML file

        Args:
            config_path: Path to save config file
        """
        with open(config_path, 'w') as f:
            yaml.safe_dump(self._config, f, default_flow_style=False)

        self.logger.info(f"Configuration saved to {config_path}")

    def get_all(self) -> Dict:
        """Get entire configuration dictionary"""
        return self._config.copy()
