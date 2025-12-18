"""
PiBook E-Reader - Main Application
Event-driven e-ink reader for Raspberry Pi
PORTABILITY: 100% portable between Pi 3B+ and Pi Zero 2 W
"""

import sys
import os
import logging
import signal
import gc
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.display.display_driver import DisplayDriver
from src.hardware.gpio_handler import GPIOHandler
from src.ui.navigation import NavigationManager, Screen
from src.ui.screens import LibraryScreen, ReaderScreen


class PiBookApp:
    """
    Main E-Reader application
    """

    def __init__(self, config_path: str):
        """
        Initialize application

        Args:
            config_path: Path to config.yaml
        """
        # Load configuration
        self.config = Config(config_path)

        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 50)
        self.logger.info("PiBook E-Reader starting...")
        self.logger.info("=" * 50)

        # Initialize components
        display_width = self.config.get('display.width', 800)
        display_height = self.config.get('display.height', 480)
        display_dpi = self.config.get('display.dpi', 150)

        self.display = DisplayDriver(display_width, display_height)
        self.gpio = GPIOHandler(self.config.get('gpio_config', 'config/gpio_mapping.yaml'))
        self.navigation = NavigationManager(Screen.LIBRARY)

        # Initialize screens
        self.library_screen = LibraryScreen(
            width=display_width,
            height=display_height,
            items_per_page=self.config.get('library.items_per_page', 8),
            font_size=self.config.get('library.font_size', 20)
        )

        self.reader_screen = ReaderScreen(
            width=display_width,
            height=display_height,
            dpi=display_dpi,
            cache_size=self.config.get('reader.page_cache_size', 5)
        )

        # State
        self.running = False
        self.page_turn_count = 0
        self.gc_threshold = self.config.get('performance.gc_threshold', 100)

    def _setup_logging(self):
        """Configure logging"""
        log_level = getattr(logging, self.config.get('logging.level', 'INFO'))
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        handlers = []

        # Console handler
        if self.config.get('logging.console', True):
            handlers.append(logging.StreamHandler())

        # File handler
        log_file = self.config.get('logging.file')
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            handlers.append(logging.FileHandler(log_file))

        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=handlers
        )

    def start(self):
        """Start the application"""
        try:
            # Initialize hardware
            self.logger.info("Initializing hardware...")
            self.display.initialize()
            self._register_gpio_callbacks()

            # Load library
            books_dir = self.config.get('library.books_directory', '/home/pi/PiBook/books')
            self.library_screen.load_books(books_dir)

            # Set running flag
            self.running = True

            # Render initial screen
            self._render_current_screen()

            self.logger.info("PiBook started successfully!")
            self.logger.info("Press Ctrl+C to exit")

            # Keep running (wake on button press)
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

            # Pause indefinitely - wake on GPIO interrupts
            signal.pause()

        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
            self.stop()
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            self.stop()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}")
        self.stop()
        sys.exit(0)

    def stop(self):
        """Clean shutdown"""
        self.logger.info("Shutting down...")
        self.running = False

        # Close reader
        if self.reader_screen:
            self.reader_screen.close()

        # Cleanup hardware
        if self.display:
            self.display.cleanup()

        if self.gpio:
            self.gpio.cleanup()

        self.logger.info("PiBook stopped")

    def _register_gpio_callbacks(self):
        """Register button callbacks"""
        self.gpio.register_callback('next_page', self._handle_next)
        self.gpio.register_callback('prev_page', self._handle_prev)
        self.gpio.register_callback('select', self._handle_select)
        self.gpio.register_callback('back', self._handle_back)
        self.gpio.register_callback('menu', self._handle_menu)

        self.logger.info("GPIO callbacks registered")

    def _handle_next(self):
        """Handle next button press"""
        if not self.running:
            return

        self.logger.info("Button: Next")

        if self.navigation.is_on_screen(Screen.LIBRARY):
            self.library_screen.next_item()
        elif self.navigation.is_on_screen(Screen.READER):
            self.reader_screen.next_page()

        self._render_current_screen()
        self._trigger_gc_if_needed()

    def _handle_prev(self):
        """Handle previous button press"""
        if not self.running:
            return

        self.logger.info("Button: Previous")

        if self.navigation.is_on_screen(Screen.LIBRARY):
            self.library_screen.prev_item()
        elif self.navigation.is_on_screen(Screen.READER):
            self.reader_screen.prev_page()

        self._render_current_screen()
        self._trigger_gc_if_needed()

    def _handle_select(self):
        """Handle select button press"""
        if not self.running:
            return

        self.logger.info("Button: Select")

        if self.navigation.is_on_screen(Screen.LIBRARY):
            # Open selected book
            book = self.library_screen.get_selected_book()
            if book:
                self._open_book(book)

    def _handle_back(self):
        """Handle back button press"""
        if not self.running:
            return

        self.logger.info("Button: Back")

        if self.navigation.is_on_screen(Screen.READER):
            # Return to library
            self.reader_screen.close()
            self.navigation.navigate_to(Screen.LIBRARY)
            self._render_current_screen()

    def _handle_menu(self):
        """Handle menu button press"""
        if not self.running:
            return

        self.logger.info("Button: Menu")

        # Always return to library
        if self.navigation.is_on_screen(Screen.READER):
            self.reader_screen.close()

        self.navigation.navigate_to(Screen.LIBRARY)
        self._render_current_screen()

    def _open_book(self, book: dict):
        """
        Open and display a book

        Args:
            book: Book dict from library
        """
        try:
            self.logger.info(f"Opening book: {book['title']}")

            # Load EPUB with PyMuPDF
            self.reader_screen.load_epub(book['path'])

            # Navigate to reader screen
            self.navigation.navigate_to(Screen.READER, {'book': book})
            self._render_current_screen()

            # Log page info
            info = self.reader_screen.get_page_info()
            self.logger.info(f"Book opened: {info['total']} pages")

        except Exception as e:
            self.logger.error(f"Failed to open book: {e}", exc_info=True)
            # Stay on library screen

    def _render_current_screen(self):
        """Render the current screen to display"""
        try:
            if self.navigation.is_on_screen(Screen.LIBRARY):
                image = self.library_screen.render()
            elif self.navigation.is_on_screen(Screen.READER):
                image = self.reader_screen.get_current_image()

                # Log page info
                info = self.reader_screen.get_page_info()
                self.logger.info(f"Page {info['current']} of {info['total']}")

                # Log cache stats periodically
                if 'cache_stats' in info:
                    stats = info['cache_stats']
                    self.logger.debug(f"Cache: {stats.get('hit_rate', 0):.1f}% hit rate")

            else:
                self.logger.warning(f"Unknown screen: {self.navigation.current_screen}")
                return

            # Display image
            self.display.display_image(image)

        except Exception as e:
            self.logger.error(f"Render error: {e}", exc_info=True)

    def _trigger_gc_if_needed(self):
        """Trigger garbage collection periodically (for Pi Zero 2 W)"""
        self.page_turn_count += 1

        if self.page_turn_count % self.gc_threshold == 0:
            gc.collect()
            self.logger.debug(f"Garbage collection triggered (count: {self.page_turn_count})")


def main():
    """Main entry point"""
    # Determine config path
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = os.environ.get(
            'PIBOOK_CONFIG',
            os.path.join(os.path.dirname(__file__), '../config/config.yaml')
        )

    # Ensure config exists
    if not os.path.exists(config_path):
        print(f"ERROR: Configuration file not found: {config_path}")
        print(f"Usage: python3 {sys.argv[0]} [config_path]")
        sys.exit(1)

    # Create and start application
    app = PiBookApp(config_path)
    app.start()


if __name__ == '__main__':
    main()
