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
import threading
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.display.display_driver import DisplayDriver
from src.hardware.gpio_handler import GPIOHandler
from src.ui.navigation import NavigationManager, Screen
from src.ui.screens import LibraryScreen, ReaderScreen
from src.web.webserver import PiBookWebServer


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

        # Load user settings
        self.settings = self._load_settings()
        self.logger.info(f"User settings loaded: {self.settings}")

        # Initialize components
        display_width = self.config.get('display.width', 800)
        display_height = self.config.get('display.height', 480)
        display_rotation = self.config.get('display.rotation', 0)
        zoom_factor = self.settings.get('zoom', 1.0)
        dpi = self.settings.get('dpi', 150)

        self.display = DisplayDriver(display_width, display_height, display_rotation)
        # Set full refresh interval from settings
        self.display.set_full_refresh_interval(self.settings.get('full_refresh_interval', 5))

        self.gpio = GPIOHandler(self.config.get('gpio_config', 'config/gpio_mapping.yaml'))
        self.navigation = NavigationManager(Screen.LIBRARY)

        # Initialize screens
        web_port = self.config.get('web.port', 5000)
        self.library_screen = LibraryScreen(
            width=display_width,
            height=display_height,
            items_per_page=self.config.get('library.items_per_page', 8),
            font_size=self.config.get('library.font_size', 20),
            web_port=web_port
        )

        self.reader_screen = ReaderScreen(
            width=display_width,
            height=display_height,
            zoom_factor=zoom_factor,
            dpi=dpi,
            cache_size=self.config.get('reader.page_cache_size', 5),
            show_page_numbers=self.settings.get('show_page_numbers', True)
        )

        # State
        self.running = False
        self.page_turn_count = 0
        self.gc_threshold = self.config.get('performance.gc_threshold', 100)
        
        # Sleep Mode
        self.last_activity_time = time.time()
        self.is_sleeping = False
        self.sleep_timeout = 300 # 5 minutes

        # Web server
        self.web_server = None

    def _setup_logging(self):
        """Configure logging"""
        # ... (keep existing logging setup) ...
        # Since replace_file_content requires context matching, I will supply the full surrounding context
        # But this method is very long. I will edit the file in chunks or carefully match context.
        # Let's try to match the State section and imports first.
        pass

    # ... (skipping to implemented methods) ...

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

            # Start web server
            web_port = self.config.get('web.port', 5000)
            self.web_server = PiBookWebServer(books_dir, self, web_port)
            self.web_server.run()
            self.logger.info(f"Web interface available at http://<pi-ip>:{web_port}")

            # Start inactivity monitor
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_inactivity, daemon=True)
            self.monitor_thread.start()

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

    # ... (keep stop/signal handlers) ...

    def _monitor_inactivity(self):
        """Background thread to check for inactivity"""
        while self.running:
            try:
                if not self.is_sleeping and (time.time() - self.last_activity_time > self.sleep_timeout):
                    self._enter_sleep()
                time.sleep(10)
            except Exception as e:
                self.logger.error(f"Error in monitor thread: {e}")

    def _enter_sleep(self):
        """Enter sleep mode"""
        self.logger.info("Entering sleep mode (inactive)")
        self.is_sleeping = True
        
        # Create sleep image
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new('1', (self.display.width, self.display.height), 1)
        draw = ImageDraw.Draw(image)
        
        # Try to load a font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 48)
        except:
            font = ImageFont.load_default()
            
        text = "Shh I'm sleeping"
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text(((self.display.width - w)//2, (self.display.height - h)//2), text, font=font, fill=0)
        except:
            draw.text((100, 100), text, fill=0) # Fallback
            
        # Full refresh for sleep screen
        self.display.display_image(image, use_partial=False)

    def _wake_from_sleep(self):
        """Wake from sleep"""
        self.logger.info("Waking up!")
        self.is_sleeping = False
        self._reset_activity()
        self._render_current_screen()

    def _reset_activity(self):
        self.last_activity_time = time.time()

    def _handle_next(self):
        """Handle next button press"""
        if not self.running: return
        
        # Reset activity timer
        self._reset_activity()
        
        # If sleeping, just wake up and consume event
        if self.is_sleeping:
            self._wake_from_sleep()
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
        if not self.running: return
        
        self._reset_activity()
        if self.is_sleeping:
            self._wake_from_sleep()
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
        if not self.running: return
        
        self._reset_activity()
        if self.is_sleeping:
            self._wake_from_sleep()
            return

        self.logger.info("Button: Select")

        if self.navigation.is_on_screen(Screen.LIBRARY):
            # Open selected book
            book = self.library_screen.get_selected_book()
            if book:
                self._open_book(book)

    def _handle_back(self):
        """Handle back button press"""
        if not self.running: return
        
        self._reset_activity()
        if self.is_sleeping:
            self._wake_from_sleep()
            return

        self.logger.info("Button: Back")

        if self.navigation.is_on_screen(Screen.READER):
            # Return to library
            self.reader_screen.close()
            self.navigation.navigate_to(Screen.LIBRARY)
            self._render_current_screen()

    def _handle_menu(self):
        """Handle menu button press"""
        if not self.running: return
        
        self._reset_activity()
        if self.is_sleeping:
            self._wake_from_sleep()
            return

        self.logger.info("Button: Menu")

        # Always return to library
        if self.navigation.is_on_screen(Screen.READER):
            self.reader_screen.close()

        self.navigation.navigate_to(Screen.LIBRARY)
        self._render_current_screen()


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
