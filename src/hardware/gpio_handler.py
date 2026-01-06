"""
GPIO button handling with gpiozero.
Supports short press and long press detection.
PORTABILITY: 100% portable - GPIO layout identical on Pi 3B+ and Pi Zero 2 W
"""

import yaml
import logging
import time
import threading
from typing import Callable, Dict, Optional


class GPIOHandler:
    """
    Handle GPIO button inputs using gpiozero with short/long press detection
    """

    def __init__(self, config_path: str, long_press_duration: float = 0.8):
        """
        Initialize GPIO handler

        Args:
            config_path: Path to GPIO configuration YAML
            long_press_duration: Seconds to hold for long press (default 0.8s)
        """
        self.logger = logging.getLogger(__name__)
        self.callbacks: Dict[str, Callable] = {}
        self.long_press_callbacks: Dict[str, Callable] = {}
        self.buttons: Dict[str, Optional[object]] = {}
        self.long_press_duration = long_press_duration
        
        # Track button press state
        self.press_start_time: Dict[str, Optional[float]] = {}
        self.long_press_triggered: Dict[str, bool] = {}

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
                self.press_start_time[button_name] = None
                self.long_press_triggered[button_name] = False
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
                self.press_start_time[button_name] = None
                self.long_press_triggered[button_name] = False
                self.logger.info(f"Configured button '{button_name}' on GPIO {pin}")
            except Exception as e:
                self.logger.error(f"Failed to setup button '{button_name}': {e}")

    def register_callback(self, button_name: str, callback: Callable, long_press: bool = False):
        """
        Register a callback function for a button

        Args:
            button_name: Name of button (from config)
            callback: Function to call when button is pressed
            long_press: If True, callback is for long press; if False, for short press
        """
        if button_name not in self.buttons:
            raise ValueError(f"Unknown button: {button_name}")

        if long_press:
            self.long_press_callbacks[button_name] = callback
            self.logger.info(f"Registered LONG PRESS callback for button '{button_name}'")
        else:
            self.callbacks[button_name] = callback
            self.logger.info(f"Registered SHORT PRESS callback for button '{button_name}'")

        if not self.hardware_available:
            return

        button = self.buttons[button_name]
        if button:
            # Set up press and release handlers
            button.when_pressed = lambda bn=button_name: self._on_button_press(bn)
            button.when_released = lambda bn=button_name: self._on_button_release(bn)

    def _on_button_press(self, button_name: str):
        """Handle button press event"""
        self.press_start_time[button_name] = time.time()
        self.long_press_triggered[button_name] = False
        self.logger.debug(f"Button '{button_name}' pressed")
        
        # Start a thread to check for long press
        threading.Thread(
            target=self._check_long_press,
            args=(button_name,),
            daemon=True
        ).start()

    def _check_long_press(self, button_name: str):
        """Check if button is held long enough for long press"""
        time.sleep(self.long_press_duration)
        
        # If button is still pressed after duration, trigger long press
        if self.press_start_time[button_name] is not None:
            button = self.buttons[button_name]
            if button and button.is_pressed:
                self.long_press_triggered[button_name] = True
                if button_name in self.long_press_callbacks:
                    self.logger.info(f"🔘 GPIO Button '{button_name}': LONG PRESS detected")
                    self.long_press_callbacks[button_name]()

    def _on_button_release(self, button_name: str):
        """Handle button release event"""
        if self.press_start_time[button_name] is None:
            return
        
        press_duration = time.time() - self.press_start_time[button_name]
        self.press_start_time[button_name] = None
        
        # If long press wasn't triggered, this is a short press
        if not self.long_press_triggered[button_name]:
            if button_name in self.callbacks:
                self.logger.info(f"🔘 GPIO Button '{button_name}': SHORT PRESS detected ({press_duration:.2f}s)")
                self.callbacks[button_name]()
        else:
            self.logger.debug(f"Button '{button_name}' released after long press")

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

    def trigger_button(self, button_name: str, long_press: bool = False):
        """
        Manually trigger a button callback (for testing/mock mode)

        Args:
            button_name: Name of button to trigger
            long_press: If True, trigger long press; if False, trigger short press
        """
        if long_press and button_name in self.long_press_callbacks:
            self.logger.info(f"Manually triggering LONG PRESS for '{button_name}'")
            self.long_press_callbacks[button_name]()
        elif not long_press and button_name in self.callbacks:
            self.logger.info(f"Manually triggering SHORT PRESS for '{button_name}'")
            self.callbacks[button_name]()
        else:
            self.logger.warning(f"No callback registered for '{button_name}' (long_press={long_press})")
