"""
GPIO button handling with gpiozero.
PORTABILITY: 100% portable - GPIO layout identical on Pi 3B+ and Pi Zero 2 W
"""

import yaml
import logging
from typing import Callable, Dict, Optional


class GPIOHandler:
    """
    Handle GPIO button inputs using gpiozero
    """

    def __init__(self, config_path: str):
        """
        Initialize GPIO handler

        Args:
            config_path: Path to GPIO configuration YAML
        """
        self.logger = logging.getLogger(__name__)
        self.callbacks: Dict[str, Callable] = {}
        self.buttons: Dict[str, Optional[object]] = {}

        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Try to import gpiozero
        try:
            from gpiozero import Button
            self.Button = Button
            self.hardware_available = True
            self.logger.info("GPIO hardware available")
        except ImportError:
            self.logger.warning("gpiozero not available. Running in mock mode.")
            self.hardware_available = False
            self.Button = None

        # Setup buttons
        self._setup_buttons()

    def _setup_buttons(self):
        """Configure all buttons from config"""
        if not self.hardware_available:
            # Mock mode - create dummy button objects
            for button_name in self.config['buttons'].keys():
                self.buttons[button_name] = None
            self.logger.info("Mock GPIO buttons configured")
            return

        for button_name, button_config in self.config['buttons'].items():
            pin = button_config['pin']
            pull_up = (button_config['pull'] == 'up')
            bounce_time = button_config.get('bounce_time', 0.2)

            try:
                self.buttons[button_name] = self.Button(
                    pin,
                    pull_up=pull_up,
                    bounce_time=bounce_time
                )
                self.logger.info(f"Configured button '{button_name}' on GPIO {pin}")
            except Exception as e:
                self.logger.error(f"Failed to setup button '{button_name}': {e}")

    def register_callback(self, button_name: str, callback: Callable):
        """
        Register a callback function for a button

        Args:
            button_name: Name of button (from config)
            callback: Function to call when button is pressed
        """
        if button_name not in self.buttons:
            raise ValueError(f"Unknown button: {button_name}")

        self.callbacks[button_name] = callback

        if not self.hardware_available:
            self.logger.debug(f"Mock callback registered for '{button_name}'")
            return

        button = self.buttons[button_name]
        if button:
            button.when_pressed = callback
            self.logger.info(f"Registered callback for button '{button_name}'")

    def cleanup(self):
        """Clean up GPIO resources"""
        if not self.hardware_available:
            self.logger.debug("Mock GPIO cleanup")
            return

        for button_name, button in self.buttons.items():
            if button:
                try:
                    button.close()
                except Exception as e:
                    self.logger.error(f"Error cleaning up button '{button_name}': {e}")

        self.logger.info("GPIO cleaned up")

    def trigger_button(self, button_name: str):
        """
        Manually trigger a button callback (for testing/mock mode)

        Args:
            button_name: Name of button to trigger
        """
        if button_name in self.callbacks:
            self.logger.info(f"Manually triggering button '{button_name}'")
            self.callbacks[button_name]()
        else:
            self.logger.warning(f"No callback registered for '{button_name}'")
