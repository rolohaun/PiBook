"""
UI screen implementations for Library and Reader.
Uses Pillow for library menu, PyMuPDF for reader pages.
PORTABILITY: 100% portable between Pi 3B+ and Pi Zero 2 W
"""

from PIL import Image, ImageDraw, ImageFont
from typing import List, Optional, Dict
import os
import logging
import socket
import subprocess


def get_ip_address():
    """Get the Pi's local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "No Network"


def get_wifi_status():
    """Check if WiFi is enabled and connected"""
    try:
        # Check if wlan0 interface exists and is up
        result = subprocess.run(['ip', 'link', 'show', 'wlan0'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            # Check if interface is UP
            if 'state UP' in result.stdout or 'UP' in result.stdout:
                return True
        return False
    except Exception:
        return False


def get_bluetooth_status():
    """Check if Bluetooth is enabled"""
    try:
        # Check if bluetooth service is active
        result = subprocess.run(['systemctl', 'is-active', 'bluetooth'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip() == 'active':
            # Also check if hci0 is up
            hci_result = subprocess.run(['hciconfig', 'hci0'],
                                      capture_output=True, text=True, timeout=2)
            if hci_result.returncode == 0 and 'UP RUNNING' in hci_result.stdout:
                return True
        return False
    except Exception:
        return False


class LibraryScreen:
    """
    Book library/selection screen
    Renders a list of available EPUB files using Pillow
    """

    def __init__(self, width: int = 800, height: int = 480, items_per_page: int = 8, font_size: int = 20, web_port: int = 5000, battery_monitor=None):
        """
        Initialize library screen

        Args:
            width: Screen width
            height: Screen height
            items_per_page: Number of books to show per page
            font_size: Font size for menu text
            web_port: Web server port number
            battery_monitor: Optional BatteryMonitor instance
        """
        self.logger = logging.getLogger(__name__)
        self.width = width
        self.height = height
        self.items_per_page = items_per_page
        self.font_size = font_size
        self.web_port = web_port

        self.current_index = 0
        self.current_page = 0
        self.books: List[Dict[str, str]] = []
        self.battery_monitor = battery_monitor

        # Try to load fonts
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            self.title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except Exception:
            self.logger.warning("TrueType fonts not found, using default")
            self.font = ImageFont.load_default()
            self.title_font = ImageFont.load_default()

    def load_books(self, books_dir: str):
        """
        Load list of EPUB files from directory

        Args:
            books_dir: Path to books directory
        """
        self.books = []

        if not os.path.exists(books_dir):
            self.logger.warning(f"Books directory not found: {books_dir}")
            return

        for filename in os.listdir(books_dir):
            if filename.lower().endswith('.epub'):
                self.books.append({
                    'filename': filename,
                    'path': os.path.join(books_dir, filename),
                    'title': filename[:-5]  # Remove .epub extension
                })

        self.books.sort(key=lambda x: x['title'].lower())
        self.logger.info(f"Loaded {len(self.books)} books")

    def next_item(self):
        """Move selection to next book"""
        if self.current_index < len(self.books) - 1:
            self.current_index += 1

            # Page down if needed
            if self.current_index >= (self.current_page + 1) * self.items_per_page:
                self.current_page += 1

            self.logger.debug(f"Selected book {self.current_index}")

    def prev_item(self):
        """Move selection to previous book"""
        if self.current_index > 0:
            self.current_index -= 1

            # Page up if needed
            if self.current_index < self.current_page * self.items_per_page:
                self.current_page -= 1

            self.logger.debug(f"Selected book {self.current_index}")

    def get_selected_book(self) -> Optional[Dict[str, str]]:
        """
        Get currently selected book

        Returns:
            Book dictionary or None if no books
        """
        if 0 <= self.current_index < len(self.books):
            return self.books[self.current_index]
        return None

    def _draw_battery_icon(self, draw: ImageDraw.Draw, x: int, y: int, percentage: int):
        """
        Draw battery icon with percentage

        Args:
            draw: ImageDraw object
            x: X position (top-right corner)
            y: Y position
            percentage: Battery percentage (0-100)
        """
        # Battery dimensions
        battery_width = 30
        battery_height = 14
        terminal_width = 2
        terminal_height = 6

        # Draw battery outline
        battery_x = x - battery_width
        draw.rectangle(
            [(battery_x, y), (battery_x + battery_width, y + battery_height)],
            outline=0,
            width=1
        )

        # Draw battery terminal (positive end)
        terminal_x = battery_x + battery_width
        terminal_y = y + (battery_height - terminal_height) // 2
        draw.rectangle(
            [(terminal_x, terminal_y), (terminal_x + terminal_width, terminal_y + terminal_height)],
            fill=0
        )

        # Draw battery fill based on percentage
        fill_width = int((battery_width - 4) * (percentage / 100))
        if fill_width > 0:
            draw.rectangle(
                [(battery_x + 2, y + 2), (battery_x + 2 + fill_width, y + battery_height - 2)],
                fill=0
            )

        # Draw percentage text
        percentage_text = f"{percentage}%"
        try:
            bbox = draw.textbbox((0, 0), percentage_text, font=self.font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(percentage_text) * 8

        text_x = battery_x - text_width - 5
        draw.text((text_x, y), percentage_text, font=self.font, fill=0)

    def render(self) -> Image.Image:
        """
        Render library screen to PIL Image

        Returns:
            PIL Image (1-bit, for e-ink display)
        """
        # Create white background
        image = Image.new('1', (self.width, self.height), 1)
        draw = ImageDraw.Draw(image)

        # Draw WiFi status indicator (top left)
        wifi_on = get_wifi_status()
        wifi_icon_x = 10
        wifi_icon_y = 8
        if wifi_on:
            # Draw WiFi icon (three curved lines)
            draw.arc([wifi_icon_x, wifi_icon_y+8, wifi_icon_x+16, wifi_icon_y+16], 180, 360, fill=0, width=2)
            draw.arc([wifi_icon_x+3, wifi_icon_y+11, wifi_icon_x+13, wifi_icon_y+16], 180, 360, fill=0, width=2)
            draw.arc([wifi_icon_x+6, wifi_icon_y+14, wifi_icon_x+10, wifi_icon_y+16], 180, 360, fill=0, width=2)
            draw.text((wifi_icon_x + 20, wifi_icon_y), "WiFi", font=self.font, fill=0)
        else:
            # Draw WiFi off icon (X through WiFi)
            draw.text((wifi_icon_x, wifi_icon_y), "WiFi OFF", font=self.font, fill=0)

        # Draw Bluetooth status indicator (top right)
        bt_on = get_bluetooth_status()
        bt_text = "BT" if bt_on else "BT OFF"
        try:
            bbox = draw.textbbox((0, 0), bt_text, font=self.font)
            bt_width = bbox[2] - bbox[0]
        except:
            bt_width = len(bt_text) * 10
        bt_x = self.width - bt_width - 10
        bt_y = 8

        if bt_on:
            # Draw simple Bluetooth icon (B symbol)
            draw.text((bt_x, bt_y), "BT", font=self.font, fill=0)
        else:
            draw.text((bt_x, bt_y), "BT OFF", font=self.font, fill=0)

        # Draw IP address and port at top center
        ip_address = get_ip_address()
        ip_text = f"{ip_address}:{self.web_port}"
        try:
            # Get text bounding box for centering
            bbox = draw.textbbox((0, 0), ip_text, font=self.font)
            ip_width = bbox[2] - bbox[0]
            ip_x = (self.width - ip_width) // 2
        except:
            ip_x = self.width // 2 - 80
        draw.text((ip_x, 5), ip_text, font=self.font, fill=0)

        # Draw battery status in top-right corner
        if self.battery_monitor:
            battery_percentage = self.battery_monitor.get_percentage()
            self._draw_battery_icon(draw, self.width - 10, 5, battery_percentage)

        # Draw title
        draw.text((40, 30), "Library", font=self.title_font, fill=0)
        draw.line([(40, 65), (self.width - 40, 65)], fill=0, width=2)

        if not self.books:
            # No books available
            draw.text((40, 100), "No EPUB files found in books directory", font=self.font, fill=0)
            draw.text((40, 140), "Add .epub files to:", font=self.font, fill=0)
            draw.text((40, 170), "/home/pi/PiBook/books/", font=self.font, fill=0)
            return image

        # Calculate visible range
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.books))

        # Draw book list
        y = 85
        line_height = 38

        for i in range(start_idx, end_idx):
            book = self.books[i]
            is_selected = (i == self.current_index)

            if is_selected:
                # Draw selection box
                draw.rectangle(
                    [(30, y - 5), (self.width - 30, y + line_height - 10)],
                    outline=0,
                    width=2
                )

            # Draw book title (truncate if too long)
            title = book['title']
            if len(title) > 50:
                title = title[:47] + "..."

            draw.text((40, y), title, font=self.font, fill=0)
            y += line_height

        # Draw footer with page info
        if len(self.books) > 0:
            footer_text = f"Book {self.current_index + 1} of {len(self.books)}"
            draw.text((40, self.height - 40), footer_text, font=self.font, fill=0)

        return image


class ReaderScreen:
    """
    Book reading screen
    Uses EPUBRenderer (PyMuPDF) to display pages
    """

    def __init__(self, width: int = 800, height: int = 480, zoom_factor: float = 1.0, dpi: int = 150, cache_size: int = 5, show_page_numbers: bool = True, battery_monitor=None):
        """
        Initialize reader screen

        Args:
            width: Screen width
            height: Screen height
            zoom_factor: Zoom multiplier for content
            dpi: Rendering DPI for quality
            cache_size: Number of pages to cache
            show_page_numbers: Whether to show page numbers
            battery_monitor: Optional BatteryMonitor instance
        """
        self.logger = logging.getLogger(__name__)
        self.width = width
        self.height = height
        self.zoom_factor = zoom_factor
        self.dpi = dpi
        self.show_page_numbers = show_page_numbers

        self.current_page = 0
        self.renderer = None
        self.page_cache = None
        self.epub_path = None
        self.renderer_type = None
        self.battery_monitor = battery_monitor

        # Helper for page caching
        from src.reader.page_cache import PageCache
        self.PageCache = PageCache
        self.cache_size = cache_size

    def load_epub(self, epub_path: str, zoom_factor: float = None, dpi: int = None):
        """
        Load an EPUB file

        Args:
            epub_path: Path to EPUB file
            zoom_factor: Optional zoom override (uses self.zoom_factor if not provided)
            dpi: Optional DPI override (uses self.dpi if not provided)
        """
        try:
            # Close previous book if open
            if self.renderer:
                self.renderer.close()

            # Use provided settings or defaults
            if zoom_factor is not None:
                self.zoom_factor = zoom_factor
            if dpi is not None:
                self.dpi = dpi

            # Initialize PillowTextRenderer
            from src.reader.pillow_text_renderer import PillowTextRenderer
            self.renderer = PillowTextRenderer(
                epub_path, 
                width=self.width, 
                height=self.height, 
                zoom_factor=self.zoom_factor, 
                dpi=self.dpi
            )
            self.renderer_type = 'pillow'
            self.logger.info(f"Using PillowTextRenderer for: {epub_path}")

            self.epub_path = epub_path

            self.page_cache = self.PageCache(self.cache_size)
            self.current_page = 0
            
            # Pre-fill cache for first few pages
            if self.page_cache:
                self.page_cache.reset()
                self._update_cache(0) # Cache surrounding pages

        except Exception as e:
            self.epub_path = epub_path

            self.logger.info(f"Loaded EPUB: {epub_path} ({self.renderer.get_page_count()} pages, renderer={self.renderer_type}, zoom={self.zoom_factor}, dpi={self.dpi})")

        except Exception as e:
            self.logger.error(f"Failed to load EPUB: {e}")
            raise

    def next_page(self) -> bool:
        """
        Navigate to next page

        Returns:
            True if navigation occurred, False if on last page
        """
        if not self.renderer:
            return False

        if self.current_page < self.renderer.get_page_count() - 1:
            self.current_page += 1
            self.logger.debug(f"Next page: {self.current_page}")
            return True

        self.logger.debug("Already on last page")
        return False

    def prev_page(self) -> bool:
        """
        Navigate to previous page

        Returns:
            True if navigation occurred, False if on first page
        """
        if not self.renderer:
            return False

        if self.current_page > 0:
            self.current_page -= 1
            self.logger.debug(f"Previous page: {self.current_page}")
            return True

        self.logger.debug("Already on first page")
        return False

    def _draw_battery_icon(self, draw: ImageDraw.Draw, x: int, y: int, percentage: int):
        """
        Draw battery icon with percentage

        Args:
            draw: ImageDraw object
            x: X position (top-right corner)
            y: Y position
            percentage: Battery percentage (0-100)
        """
        # Battery dimensions
        battery_width = 30
        battery_height = 14
        terminal_width = 2
        terminal_height = 6

        # Draw battery outline
        battery_x = x - battery_width
        draw.rectangle(
            [(battery_x, y), (battery_x + battery_width, y + battery_height)],
            outline=0,
            width=1
        )

        # Draw battery terminal (positive end)
        terminal_x = battery_x + battery_width
        terminal_y = y + (battery_height - terminal_height) // 2
        draw.rectangle(
            [(terminal_x, terminal_y), (terminal_x + terminal_width, terminal_y + terminal_height)],
            fill=0
        )

        # Draw battery fill based on percentage
        fill_width = int((battery_width - 4) * (percentage / 100))
        if fill_width > 0:
            draw.rectangle(
                [(battery_x + 2, y + 2), (battery_x + 2 + fill_width, y + battery_height - 2)],
                fill=0
            )

        # Draw percentage text
        percentage_text = f"{percentage}%"
        # Use default font for battery percentage
        font = ImageFont.load_default()
        try:
            bbox = draw.textbbox((0, 0), percentage_text, font=font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(percentage_text) * 8

        text_x = battery_x - text_width - 5
        draw.text((text_x, y), percentage_text, font=font, fill=0)

    def get_current_image(self) -> Image.Image:
        """
        Get current page as PIL Image (with caching)

        Returns:
            PIL Image (1-bit, for e-ink display)
        """
        if not self.renderer:
            # Return blank page if no book loaded
            return Image.new('1', (self.width, self.height), 1)

        # Check cache first
        cached = self.page_cache.get(self.current_page)
        if cached:
            return cached

        # Render and cache
        img = self.renderer.render_page(self.current_page, show_page_number=self.show_page_numbers)
        self.page_cache.put(self.current_page, img)

        # Add battery overlay if monitor available
        if self.battery_monitor:
            # Create a copy to avoid modifying cached image
            img = img.copy()
            draw = ImageDraw.Draw(img)
            battery_percentage = self.battery_monitor.get_percentage()
            self._draw_battery_icon(draw, self.width - 10, 5, battery_percentage)

        return img

    def get_page_info(self) -> Dict[str, any]:
        """
        Get information about current page

        Returns:
            Dictionary with page number, total pages, etc.
        """
        if not self.renderer:
            return {'current': 0, 'total': 0}

        return {
            'current': self.current_page + 1,  # 1-indexed for display
            'total': self.renderer.get_page_count(),
            'cache_stats': self.page_cache.get_stats() if self.page_cache else {}
        }

    def close(self):
        """Close current book and clean up"""
        if self.renderer:
            self.renderer.close()
            self.renderer = None

        if self.page_cache:
            self.page_cache.clear()
            self.page_cache = None

        self.logger.info("Reader closed")
