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
from src.hardware.battery_monitor import BatteryMonitor
from src.ui.navigation import NavigationManager, Screen
from src.ui.screens import MainMenuScreen, LibraryScreen, ReaderScreen, IPScannerScreen
from src.web.webserver import PiBookWebServer
from src.utils.progress_manager import ProgressManager


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
        self.navigation = NavigationManager()  # Defaults to Screen.MAIN_MENU

        # Initialize battery monitor (if enabled)
        self.battery_monitor = None
        if self.config.get('battery.enabled', False):
            try:
                self.battery_monitor = BatteryMonitor(
                    adc_channel=self.config.get('battery.adc_channel', 0),
                    voltage_divider_ratio=self.config.get('battery.voltage_divider_ratio', 2.0),
                    min_voltage=self.config.get('battery.min_voltage', 3.0),
                    max_voltage=self.config.get('battery.max_voltage', 4.2),
                    update_interval=self.config.get('battery.update_interval', 30),
                    pisugar_socket=self.config.get('pisugar.socket_path', '/tmp/pisugar-server.sock')
                )
                self.logger.info("Battery monitor initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize battery monitor: {e}")
                self.battery_monitor = None

        # Initialize PiSugar button handler (if enabled)
        self.pisugar_button = None
        if self.config.get('pisugar.button_enabled', False):
            try:
                from src.hardware.pisugar_button_handler import PiSugarButtonHandler
                self.pisugar_button = PiSugarButtonHandler(
                    socket_path=self.config.get('pisugar.button_socket_path', '/tmp/pibook-button.sock')
                )
                # Register callbacks (will be set up after GPIO callbacks)
                self.logger.info("PiSugar button handler initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize PiSugar button handler: {e}")
                self.pisugar_button = None

        # Initialize reading progress manager
        progress_file = self.config.get('reading_progress.progress_file', 'data/reading_progress.json')
        self.progress_manager = ProgressManager(progress_file)
        self.logger.info("Reading progress manager initialized")
        
        # Disable HDMI for battery savings (never needed for e-ink display)


        # HDMI is disabled via /boot/config.txt (dtoverlay=vc4-kms-v3d,nohdmi)

        self.logger.info("HDMI disabled via boot config")



        # Initialize screens

        web_port = self.config.get('web.port', 5000)

        self.main_menu_screen = MainMenuScreen(
            width=display_width,
            height=display_height,
            font_size=self.config.get('main_menu.font_size', 24),
            battery_monitor=self.battery_monitor
        )

        self.library_screen = LibraryScreen(
            width=display_width,
            height=display_height,
            items_per_page=self.config.get('library.items_per_page', 8),
            font_size=self.config.get('library.font_size', 20),
            web_port=web_port,
            battery_monitor=self.battery_monitor
        )

        self.reader_screen = ReaderScreen(
            width=display_width,
            height=display_height,
            zoom_factor=zoom_factor,
            dpi=dpi,
            cache_size=self.config.get('reader.page_cache_size', 5),
            show_page_numbers=self.settings.get('show_page_numbers', True),
            battery_monitor=self.battery_monitor
        )

        self.ip_scanner_screen = IPScannerScreen(
            width=display_width,
            height=display_height,
            font_size=self.config.get('ip_scanner.font_size', 18),
            battery_monitor=self.battery_monitor
        )

        # State
        self.running = False
        self.page_turn_count = 0
        self.gc_threshold = self.config.get('performance.gc_threshold', 100)
        # Inactivity tracking for sleep mode (battery optimization)
        self.sleep_enabled = self.settings.get('sleep_enabled', True)  # Load from settings
        self.sleep_timeout = self.config.get('power.sleep_timeout', 120)  # 2 minutes default
        self.last_activity_time = time.time()
        self.is_sleeping = False
        sleep_status = "enabled" if self.sleep_enabled else "disabled"
        self.logger.info(f"Sleep mode {sleep_status}, timeout set to {self.sleep_timeout}s for battery optimization")

        # Sync sleep status to library screen now that it's defined
        self.library_screen.sleep_enabled = self.sleep_enabled

        # Web server
        self.web_server = None

    def _load_settings(self):
        """Load user settings from settings.json"""
        import json
        settings_file = 'settings.json'
        default_settings = {
            'zoom': 1.0,
            'dpi': 150,
            'full_refresh_interval': 5,
            'show_page_numbers': True
        }

        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                if hasattr(self, 'logger'):
                    self.logger.warning(f"Failed to load settings: {e}. Using defaults.")
                return default_settings
        else:
            # Create default settings file
            try:
                with open(settings_file, 'w') as f:
                    json.dump(default_settings, f, indent=2)
            except Exception as e:
                if hasattr(self, 'logger'):
                    self.logger.warning(f"Failed to create settings file: {e}")
            return default_settings

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

    def _log_cpu_voltage(self):
        """Log CPU core voltage for undervolt diagnostics"""
        try:
            import subprocess
            result = subprocess.run(
                ['vcgencmd', 'measure_volts', 'core'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                voltage = result.stdout.strip()
                undervolt_setting = self.config.get('power.undervolt', 0)
                self.logger.info(f"CPU Core Voltage: {voltage} (undervolt setting: {undervolt_setting})")

                # Log undervolt status
                if undervolt_setting < 0:
                    voltage_reduction = abs(undervolt_setting) * 25
                    self.logger.info(f"Undervolting ACTIVE: -{voltage_reduction}mV reduction for power savings")
                else:
                    self.logger.info("Undervolting DISABLED (set power.undervolt in config.yaml)")
            else:
                self.logger.warning(f"Could not read CPU voltage: {result.stderr}")
        except FileNotFoundError:
            self.logger.warning("vcgencmd not found - cannot monitor CPU voltage")
        except Exception as e:
            self.logger.warning(f"Failed to read CPU voltage: {e}")

    def start(self):
        """Start the application"""
        try:
            # Initialize hardware
            self.logger.info("Initializing hardware...")
            self.display.initialize()
            self._register_gpio_callbacks()

            # Log CPU voltage for undervolt diagnostics
            self._log_cpu_voltage()

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

        if self.pisugar_button:
            self.pisugar_button.stop()

        self.logger.info("PiBook stopped")

    def _register_gpio_callbacks(self):
        """Register button callbacks"""
        # Single GPIO button with short and long press functionality
        # Short press: Next page (in reader) or move down (in library)
        # Long press: Toggle between library and reader
        self.gpio.register_callback('toggle', self._handle_next, long_press=False)
        self.gpio.register_callback('toggle', self._handle_toggle, long_press=True)

        self.logger.info("GPIO callbacks registered (short press: next, long press: toggle)")

        # Register PiSugar button callbacks (if available)
        if self.pisugar_button:
            self.pisugar_button.register_callback('next_page', self._handle_next)
            self.pisugar_button.register_callback('prev_page', self._handle_prev)
            self.pisugar_button.register_callback('select', self._handle_select)
            self.pisugar_button.register_callback('back', self._handle_back)
            self.pisugar_button.register_callback('toggle', self._handle_toggle)  # Long press toggles
            self.pisugar_button.start()
            self.logger.info("PiSugar button callbacks registered")

    def _monitor_inactivity(self):
        """Background thread to check for inactivity and battery status"""
        last_battery_check = 0
        last_battery_percentage = None
        last_battery_charging = None
        # Debouncing for charging status to filter PiSugar glitches
        charging_debounce_count = 0
        pending_charging_state = None

        while self.running:
            try:
                # Only enter sleep if sleep mode is enabled
                if self.sleep_enabled and not self.is_sleeping and (time.time() - self.last_activity_time > self.sleep_timeout):
                    self._enter_sleep()

                # Check battery status every 60 seconds on library screen
                current_time = time.time()
                if (self.battery_monitor and
                    self.navigation.is_on_screen(Screen.LIBRARY) and
                    not self.is_sleeping and
                    current_time - last_battery_check >= 60):

                    # Force a fresh battery reading
                    self.battery_monitor.force_update()

                    battery_percentage = self.battery_monitor.get_percentage()
                    battery_charging = self.battery_monitor.is_charging()

                    # Debounce charging status changes (PiSugar can glitch)
                    # Only update if charging state is stable for 2 consecutive checks
                    if battery_charging != last_battery_charging:
                        if pending_charging_state == battery_charging:
                            # Second consecutive reading confirms the change
                            charging_debounce_count += 1
                            if charging_debounce_count >= 1:  # Need 2 total readings (1 previous + 1 now)
                                self.logger.info(f"Battery charging changed (debounced): {last_battery_charging} -> {battery_charging}")
                                last_battery_charging = battery_charging
                                self._update_battery_display()
                                charging_debounce_count = 0
                                pending_charging_state = None
                        else:
                            # First reading of potential change
                            self.logger.debug(f"Battery charging change pending: {last_battery_charging} -> {battery_charging}")
                            pending_charging_state = battery_charging
                            charging_debounce_count = 0
                    else:
                        # Charging state stable, reset debounce
                        charging_debounce_count = 0
                        pending_charging_state = None

                    # Update display if battery percentage changed
                    # Filter out unrealistic jumps (PiSugar glitches during charging transitions)
                    if last_battery_percentage is not None and battery_percentage != last_battery_percentage:
                        percentage_change = abs(battery_percentage - last_battery_percentage)

                        # Allow changes if:
                        # 1. Small gradual change (<=5% in 1 minute)
                        # 2. OR charging state is changing (can cause legitimate jumps)
                        if percentage_change <= 5 or battery_charging != last_battery_charging:
                            self.logger.info(f"Battery percentage changed: {last_battery_percentage}% -> {battery_percentage}%")
                            last_battery_percentage = battery_percentage
                            self._update_battery_display()
                        else:
                            # Ignore unrealistic jump (likely PiSugar glitch)
                            self.logger.warning(f"Ignoring unrealistic battery jump: {last_battery_percentage}% -> {battery_percentage}% (change: {percentage_change}%)")
                    elif last_battery_percentage is None:
                        # First reading
                        last_battery_percentage = battery_percentage

                    last_battery_check = current_time

                time.sleep(10)
            except Exception as e:
                self.logger.error(f"Error in monitor thread: {e}")

    def _enter_sleep(self):
        """Enter sleep mode"""
        self.logger.info("Entering sleep mode (inactive)")
        
        # Save reading progress before sleeping
        if self.navigation.is_on_screen(Screen.READER) and self.reader_screen.current_book_path:
            self.progress_manager.save_progress(
                self.reader_screen.current_book_path,
                self.reader_screen.current_page,
                self.reader_screen.renderer.get_page_count()
            )
            self.logger.info("💾 Saved reading progress before sleep")
        
        self.is_sleeping = True
        
        # Stop web server during sleep (battery optimization)
        if self.web_server and not self.config.get('web.always_on', False):
            try:
                self.web_server.stop()
                self.logger.info("🔌 Web server stopped for battery savings")
            except:
                pass
        
        # Disable WiFi during sleep (battery optimization)
        if not self.config.get('web.always_on', False):
            try:
                os.system("sudo ifconfig wlan0 down")
                self.logger.info("📶 WiFi disabled for battery savings")
            except Exception as e:
                self.logger.warning(f"Failed to disable WiFi: {e}")
        
        # Create sleep image
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new('1', (self.display.width, self.display.height), 1)
        draw = ImageDraw.Draw(image)
        
        # Try to load a font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 48)
        except:
            font = ImageFont.load_default()
        
        # Load sleep message from settings or use default
        try:
            import json
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                text = settings.get('sleep_message', 'Shh I\'m sleeping')
        except:
            text = 'Shh I\'m sleeping'
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
        """Wake from sleep mode"""
        self.logger.info("Waking from sleep")
        self.is_sleeping = False
        
        # Re-enable WiFi (battery optimization)
        if not self.config.get('web.always_on', False):
            try:
                os.system("sudo ifconfig wlan0 up")
                self.logger.info("📶 WiFi re-enabled")
                # Wait a moment for WiFi to come up
                time.sleep(2)
            except Exception as e:
                self.logger.warning(f"Failed to enable WiFi: {e}")
        
        # Restart web server if it was stopped (battery optimization)
        if not self.web_server and self.config.get('web.enabled', True):
            try:
                web_port = self.config.get('web.port', 5000)
                self.web_server = PiBookWebServer(
                    self.library_screen,
                    port=web_port,
                    books_dir=self.config.get('library.books_directory')
                )
                self.web_server.start()
                self.logger.info("🔌 Web server restarted")
            except:
                pass
        
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

        if self.navigation.is_on_screen(Screen.MAIN_MENU):
            self.logger.info("🏠 Action: NEXT APP (Main Menu)")
            self.main_menu_screen.next_app()
        elif self.navigation.is_on_screen(Screen.LIBRARY):
            self.logger.info("📖 Action: NEXT (Library - Move down)")
            self.library_screen.next_item()
        elif self.navigation.is_on_screen(Screen.READER):
            self.logger.info("📄 Action: NEXT PAGE (Reader)")
            self.reader_screen.next_page()
            # Save progress after page turn
            if self.reader_screen.current_book_path:
                self.progress_manager.save_progress(
                    self.reader_screen.current_book_path,
                    self.reader_screen.current_page,
                    self.reader_screen.renderer.get_page_count()
                )

        self._render_current_screen()
        
        # Force garbage collection on page turn (battery optimization)
        if self.config.get('performance.gc_on_page_turn', True):
            gc.collect()
        
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
            self.logger.info("📖 Action: PREVIOUS (Library - Move up)")
            self.library_screen.prev_item()
        elif self.navigation.is_on_screen(Screen.READER):
            self.logger.info("📄 Action: PREVIOUS PAGE (Reader)")
            self.reader_screen.prev_page()
            # Save progress after page turn
            if self.reader_screen.current_book_path:
                self.progress_manager.save_progress(
                    self.reader_screen.current_book_path,
                    self.reader_screen.current_page,
                    self.reader_screen.renderer.get_total_pages()
                )

        self._render_current_screen()
        self._trigger_gc_if_needed()

    def _handle_select(self):
        """Handle select button press"""
        if not self.running: return
        
        self._reset_activity()
        if self.is_sleeping:
            self._wake_from_sleep()
            return

        if self.navigation.is_on_screen(Screen.LIBRARY):
            book = self.library_screen.get_selected_book()
            if book:
                # Check if Home icon is selected
                if book['path'] == '__home__':
                    self.logger.info("🏠 Action: SELECT - Returning to main menu")
                    self.navigation.navigate_to(Screen.MAIN_MENU)
                    self._render_current_screen()
                else:
                    self.logger.info(f"📚 Action: SELECT - Opening book '{book['title']}'")
                    self._open_book(book)
            else:
                self.logger.warning("No book selected")

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
        elif self.navigation.is_on_screen(Screen.LIBRARY):
            # Return to main menu
            self.logger.info("🏠 Action: BACK - Returning to main menu")
            self.navigation.navigate_to(Screen.MAIN_MENU)
            self._render_current_screen()

    def _handle_menu(self):
        """Handle menu button press"""
        if not self.running: return

        self._reset_activity()
        if self.is_sleeping:
            self._wake_from_sleep()
            return

        self.logger.info("Button: Menu")

        # Always return to main menu
        if self.navigation.is_on_screen(Screen.READER):
            self.reader_screen.close()

        self.navigation.navigate_to(Screen.MAIN_MENU)
        self._render_current_screen()

    def _handle_toggle(self):
        """Handle toggle button press (PiSugar long press)"""
        if not self.running: return

        self._reset_activity()
        if self.is_sleeping:
            self._wake_from_sleep()
            return

        if self.navigation.is_on_screen(Screen.MAIN_MENU):
            # On main menu - select and launch app
            app = self.main_menu_screen.get_selected_app()
            self.logger.info(f"🚀 Action: TOGGLE - Launching app '{app['name']}'")

            if app['screen'] == 'library':
                self.navigation.navigate_to(Screen.LIBRARY)
                self._render_current_screen()
            elif app['screen'] == 'ip_scanner':
                self.navigation.navigate_to(Screen.IP_SCANNER)
                self._render_current_screen()
            elif app['screen'] is None:
                self.logger.info(f"App '{app['name']}' not yet implemented")
        elif self.navigation.is_on_screen(Screen.LIBRARY):
            # On library - open selected book (same as select)
            book = self.library_screen.get_selected_book()
            if book:
                # Check if Home icon is selected
                if book['path'] == '__home__':
                    self.logger.info("🏠 Action: TOGGLE - Returning to main menu")
                    self.navigation.navigate_to(Screen.MAIN_MENU)
                    self._render_current_screen()
                else:
                    self.logger.info(f"🔄 Action: TOGGLE - Opening book '{book['title']}' from library")
                    self._open_book(book)
            else:
                self.logger.warning("No book selected to open")
        elif self.navigation.is_on_screen(Screen.READER):
            # On reader - return to library
            self.logger.info("🔄 Action: TOGGLE - Returning to library from reader")
            
            # Save progress before leaving reader
            if self.reader_screen.current_book_path:
                self.progress_manager.save_progress(
                    self.reader_screen.current_book_path,
                    self.reader_screen.current_page,
                    self.reader_screen.renderer.get_page_count()
                )
            
            self.reader_screen.close()
            self.navigation.navigate_to(Screen.LIBRARY)
            
            # Re-enable WiFi when returning to library (battery optimization)
            if not self.config.get('web.always_on', False):
                try:
                    os.system("sudo ifconfig wlan0 up")
                    self.logger.info("📶 WiFi re-enabled (returning to library)")
                    # Wait a moment for WiFi to come up
                    time.sleep(2)
                except Exception as e:
                    self.logger.warning(f"Failed to enable WiFi: {e}")
            
            # Restart web server when returning to library (battery optimization)
            if not self.web_server and self.config.get('web.enabled', True):
                try:
                    web_port = self.config.get('web.port', 5000)
                    self.web_server = PiBookWebServer(
                        self.library_screen,
                        port=web_port,
                        books_dir=self.config.get('library.books_directory')
                    )
                    self.web_server.start()
                    self.logger.info("🔌 Web server restarted (returning to library)")
                except:
                    pass

            self._render_current_screen()
        elif self.navigation.is_on_screen(Screen.IP_SCANNER):
            # On IP scanner - start scan
            self.logger.info("🔍 Action: TOGGLE - Starting network scan")
            self.ip_scanner_screen.start_scan()
            self._render_current_screen()

    def _open_book(self, book: dict):
        """
        Open and display a book

        Args:
            book: Book dict from library
        """
        try:
            self.logger.info(f"Opening book: {book['title']}")

            # Show initial loading screen (0%)
            loading_img = self.reader_screen.show_loading_progress(0, "Loading book...")
            self.display.display_image(loading_img)

            # Load EPUB
            self.reader_screen.load_epub(book['path'])

            # Check for saved progress and restore position
            saved_page = self.progress_manager.load_progress(book['path'])
            if saved_page is not None and saved_page > 0:
                self.reader_screen.go_to_page(saved_page)
                self.logger.info(f"📖 Restored to page {saved_page + 1}")

            # Stop web server when entering reader (battery optimization)
            if self.web_server and not self.config.get('web.always_on', False):
                try:
                    self.web_server.stop()
                    self.logger.info("🔌 Web server stopped (entering reader)")
                except:
                    pass
            
            # Disable WiFi when entering reader (battery optimization)
            if not self.config.get('web.always_on', False):
                try:
                    os.system("sudo ifconfig wlan0 down")
                    self.logger.info("📶 WiFi disabled (entering reader)")
                except Exception as e:
                    self.logger.warning(f"Failed to disable WiFi: {e}")

            # Navigate to reader screen
            self.navigation.navigate_to(Screen.READER, {'book': book})
            
            # Show final loading (100%)
            loading_img = self.reader_screen.show_loading_progress(100, "Ready!")
            self.display.display_image(loading_img)
            
            # Small delay to show completion
            time.sleep(0.3)
            
            # Render first page
            self._render_current_screen()

            # Log page info
            info = self.reader_screen.get_page_info()
            self.logger.info(f"Book opened: {info['total']} pages")

        except Exception as e:
            self.logger.error(f"Failed to open book: {e}", exc_info=True)
            # Stay on library screen

    def _update_battery_display(self):
        """Update just the battery icon area with a partial refresh"""
        try:
            if not self.navigation.is_on_screen(Screen.LIBRARY):
                return

            # Re-render the library screen to get updated battery icon
            image = self.library_screen.render()

            # Display with partial refresh (only updates changed pixels)
            self.display.display_image(image, use_partial=True)

        except Exception as e:
            self.logger.error(f"Battery display update error: {e}", exc_info=True)

    def _render_current_screen(self):
        """Render the current screen to display"""
        try:
            use_partial = False  # Default to full refresh

            if self.navigation.is_on_screen(Screen.MAIN_MENU):
                image = self.main_menu_screen.render()
                use_partial = True  # Use partial refresh for main menu
            elif self.navigation.is_on_screen(Screen.LIBRARY):
                image = self.library_screen.render()
                use_partial = True  # Use partial refresh for library navigation too (faster)
            elif self.navigation.is_on_screen(Screen.IP_SCANNER):
                image = self.ip_scanner_screen.render()
                use_partial = True  # Use partial refresh for IP scanner
            elif self.navigation.is_on_screen(Screen.READER):
                image = self.reader_screen.get_current_image()
                use_partial = True  # Use partial refresh for page turns

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

            # Display image with appropriate refresh mode
            self.display.display_image(image, use_partial=use_partial)

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
