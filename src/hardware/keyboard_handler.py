"""
Bluetooth Keyboard Handler for PiBook
Monitors evdev input devices for keyboard events
"""

import logging
import threading
import time
from typing import Callable, Dict, Optional

try:
    import evdev
    from evdev import InputDevice, categorize, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False


class KeyboardHandler:
    """
    Handles Bluetooth keyboard input via evdev

    Maps keyboard keys to navigation actions:
    - Arrow keys: Navigate menus
    - Enter: Select
    - Escape: Back
    - Page Up/Down: Page navigation in reader
    """

    # Key code to action mapping
    DEFAULT_KEY_MAP = {
        ecodes.KEY_UP: 'prev',
        ecodes.KEY_DOWN: 'next',
        ecodes.KEY_LEFT: 'prev',
        ecodes.KEY_RIGHT: 'next',
        ecodes.KEY_ENTER: 'select',
        ecodes.KEY_SPACE: 'next',
        ecodes.KEY_ESC: 'back',
        ecodes.KEY_BACKSPACE: 'back',
        ecodes.KEY_PAGEUP: 'prev',
        ecodes.KEY_PAGEDOWN: 'next',
        ecodes.KEY_HOME: 'home',
        ecodes.KEY_Q: 'back',
        ecodes.KEY_H: 'home',
    } if EVDEV_AVAILABLE else {}

    def __init__(self, device_pattern: str = None, logger=None):
        """
        Initialize keyboard handler

        Args:
            device_pattern: Pattern to match device name (e.g., "Apple" or "Keyboard")
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.device_pattern = device_pattern
        self.callbacks: Dict[str, Callable] = {}
        self.device: Optional[InputDevice] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._device_monitor_thread: Optional[threading.Thread] = None

        if not EVDEV_AVAILABLE:
            self.logger.warning("evdev not available - keyboard input disabled")
            return

        self.logger.info("KeyboardHandler initialized")

    def register_callback(self, action: str, callback: Callable):
        """
        Register a callback for an action

        Args:
            action: Action name ('next', 'prev', 'select', 'back', 'home')
            callback: Function to call when action triggered
        """
        self.callbacks[action] = callback
        self.logger.debug(f"Registered keyboard callback for '{action}'")

    def _find_keyboard_device(self) -> Optional[InputDevice]:
        """Find a keyboard input device"""
        if not EVDEV_AVAILABLE:
            return None

        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

            for device in devices:
                # Check device capabilities for keyboard keys
                caps = device.capabilities()
                if ecodes.EV_KEY not in caps:
                    continue

                key_caps = caps[ecodes.EV_KEY]
                # Must have arrow keys or enter to be considered a keyboard
                has_arrows = ecodes.KEY_UP in key_caps or ecodes.KEY_DOWN in key_caps
                has_enter = ecodes.KEY_ENTER in key_caps

                if has_arrows or has_enter:
                    device_name = device.name.lower()

                    # If pattern specified, match against it
                    if self.device_pattern:
                        if self.device_pattern.lower() in device_name:
                            self.logger.info(f"Found matching keyboard: {device.name} at {device.path}")
                            return device
                    else:
                        # Accept any keyboard-like device
                        # Skip internal Pi devices that aren't real keyboards
                        skip_patterns = ['gpio', 'ir-receiver', 'power button']
                        if not any(skip in device_name for skip in skip_patterns):
                            self.logger.info(f"Found keyboard: {device.name} at {device.path}")
                            return device

            return None
        except Exception as e:
            self.logger.warning(f"Error finding keyboard device: {e}")
            return None

    def _read_events(self):
        """Read keyboard events in a loop"""
        self.logger.info("Starting keyboard event reader")

        while self.running:
            if not self.device:
                time.sleep(1)
                continue

            try:
                # Use select with timeout to allow checking self.running
                import select
                r, _, _ = select.select([self.device.fd], [], [], 0.5)

                if not r:
                    continue

                for event in self.device.read():
                    if event.type == ecodes.EV_KEY:
                        key_event = categorize(event)

                        # Only trigger on key down (value=1), not key up or repeat
                        if key_event.keystate == 1:  # Key down
                            key_code = key_event.scancode

                            if key_code in self.DEFAULT_KEY_MAP:
                                action = self.DEFAULT_KEY_MAP[key_code]
                                self.logger.debug(f"Keyboard: {ecodes.KEY[key_code]} -> {action}")

                                if action in self.callbacks:
                                    try:
                                        self.callbacks[action]()
                                    except Exception as e:
                                        self.logger.error(f"Error in keyboard callback: {e}")

            except OSError as e:
                # Device disconnected
                self.logger.warning(f"Keyboard device disconnected: {e}")
                self.device = None
            except Exception as e:
                self.logger.error(f"Error reading keyboard events: {e}")
                time.sleep(0.5)

    def _monitor_devices(self):
        """Monitor for keyboard device connection/disconnection"""
        self.logger.info("Starting keyboard device monitor")

        while self.running:
            try:
                if self.device is None:
                    # Try to find a keyboard
                    new_device = self._find_keyboard_device()
                    if new_device:
                        self.device = new_device
                        self.logger.info(f"Keyboard connected: {new_device.name}")
                else:
                    # Check if device still exists
                    try:
                        # Just checking if we can access the device
                        _ = self.device.name
                    except OSError:
                        self.logger.info("Keyboard disconnected")
                        self.device = None

            except Exception as e:
                self.logger.warning(f"Error monitoring keyboard devices: {e}")

            time.sleep(2)  # Check every 2 seconds

    def start(self):
        """Start the keyboard handler"""
        if not EVDEV_AVAILABLE:
            self.logger.warning("Cannot start keyboard handler - evdev not available")
            return False

        if self.running:
            return True

        self.running = True

        # Try to find initial device
        self.device = self._find_keyboard_device()

        # Start event reader thread
        self._thread = threading.Thread(target=self._read_events, daemon=True)
        self._thread.start()

        # Start device monitor thread
        self._device_monitor_thread = threading.Thread(target=self._monitor_devices, daemon=True)
        self._device_monitor_thread.start()

        self.logger.info("Keyboard handler started")
        return True

    def stop(self):
        """Stop the keyboard handler"""
        self.running = False

        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

        if self._device_monitor_thread:
            self._device_monitor_thread.join(timeout=2)
            self._device_monitor_thread = None

        if self.device:
            try:
                self.device.close()
            except:
                pass
            self.device = None

        self.logger.info("Keyboard handler stopped")

    def is_connected(self) -> bool:
        """Check if a keyboard is connected"""
        return self.device is not None

    def get_device_name(self) -> Optional[str]:
        """Get the name of the connected keyboard"""
        if self.device:
            try:
                return self.device.name
            except:
                pass
        return None
