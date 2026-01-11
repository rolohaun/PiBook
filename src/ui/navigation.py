"""
Navigation state machine for UI screens.
PORTABILITY: 100% portable between Pi 3B+ and Pi Zero 2 W
"""

from enum import Enum
from typing import Optional, Dict, Any
import logging


class Screen(Enum):
    """Available screens in the application"""
    MAIN_MENU = "main_menu"
    LIBRARY = "library"
    READER = "reader"
    IP_SCANNER = "ip_scanner"


class NavigationManager:
    """
    Manage UI navigation and state transitions
    """

    def __init__(self, initial_screen: Screen = Screen.MAIN_MENU):
        """
        Initialize navigation manager

        Args:
            initial_screen: Starting screen
        """
        self.logger = logging.getLogger(__name__)
        self.current_screen = initial_screen
        self.previous_screen: Optional[Screen] = None
        self.state: Dict[str, Any] = {}

        self.logger.info(f"Navigation initialized at {self.current_screen}")

    def navigate_to(self, screen: Screen, state: Optional[Dict[str, Any]] = None):
        """
        Navigate to a new screen

        Args:
            screen: Target screen
            state: Optional state data to pass to screen
        """
        self.previous_screen = self.current_screen
        self.current_screen = screen

        if state:
            self.state.update(state)

        self.logger.info(f"Navigated from {self.previous_screen.value} to {self.current_screen.value}")

    def go_back(self) -> bool:
        """
        Navigate to previous screen

        Returns:
            True if navigation occurred, False if no previous screen
        """
        if self.previous_screen:
            temp = self.current_screen
            self.current_screen = self.previous_screen
            self.previous_screen = temp
            self.logger.info(f"Navigated back to {self.current_screen.value}")
            return True

        self.logger.debug("No previous screen to go back to")
        return False

    def get_state(self, key: str, default: Any = None) -> Any:
        """
        Get navigation state value

        Args:
            key: State key
            default: Default value if key doesn't exist

        Returns:
            State value or default
        """
        return self.state.get(key, default)

    def set_state(self, key: str, value: Any):
        """
        Set navigation state value

        Args:
            key: State key
            value: State value
        """
        self.state[key] = value
        self.logger.debug(f"State updated: {key} = {value}")

    def clear_state(self):
        """Clear all navigation state"""
        self.state.clear()
        self.logger.debug("Navigation state cleared")

    def is_on_screen(self, screen: Screen) -> bool:
        """
        Check if currently on a specific screen

        Args:
            screen: Screen to check

        Returns:
            True if on specified screen
        """
        return self.current_screen == screen
