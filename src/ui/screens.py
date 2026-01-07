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
        
        # Initialize cover extractor
        from src.utils.cover_extractor import CoverExtractor
        self.cover_extractor = CoverExtractor()
        self.cover_size = (100, 150)  # Larger for better detail on e-ink

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
                # Remove .epub extension and replace underscores with spaces
                title = filename[:-5].replace('_', ' ')
                self.books.append({
                    'filename': filename,
                    'path': os.path.join(books_dir, filename),
                    'title': title
                })

        self.books.sort(key=lambda x: x['title'].lower())
        self.logger.info(f"Loaded {len(self.books)} books")
    
    def _wrap_text(self, text: str, max_width: int, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> list:
        """
        Wrap text to fit within max_width pixels
        
        Args:
            text: Text to wrap
            max_width: Maximum width in pixels
            draw: ImageDraw object for measuring
            font: Font to use for measuring
            
        Returns:
            List of text lines
        """
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            try:
                # Use draw.textbbox for accurate measurement
                bbox = draw.textbbox((0, 0), test_line, font=font)
                width = bbox[2] - bbox[0]
            except:
                # Fallback
                width = len(test_line) * 10
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Single word too long, add anyway
                    lines.append(word)
                    current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines if lines else [text]

    def next_item(self):
        """Move selection to next book (with wrap-around)"""
        if len(self.books) == 0:
            return
        
        self.current_index = (self.current_index + 1) % len(self.books)
        self.current_page = self.current_index // self.items_per_page

    def prev_item(self):
        """Move selection to previous book (with wrap-around)"""
        if len(self.books) == 0:
            return
        
        self.current_index = (self.current_index - 1 + len(self.books)) % len(self.books)
        self.current_page = self.current_index // self.items_per_page

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

        # Draw WiFi status indicator (top left) - only show when ON
        wifi_on = get_wifi_status()
        if wifi_on:
            wifi_icon_x = 10
            wifi_icon_y = 8
            # Draw simple WiFi icon (arcs)
            draw.arc([wifi_icon_x, wifi_icon_y, wifi_icon_x+16, wifi_icon_y+16], 180, 360, fill=0, width=2)
            draw.arc([wifi_icon_x+3, wifi_icon_y+8, wifi_icon_x+13, wifi_icon_y+16], 180, 360, fill=0, width=2)
            draw.arc([wifi_icon_x+6, wifi_icon_y+14, wifi_icon_x+10, wifi_icon_y+16], 180, 360, fill=0, width=2)
            draw.text((wifi_icon_x + 20, wifi_icon_y), "WiFi", font=self.font, fill=0)

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

        # Draw book list with covers
        y = 85
        line_height = 160  # Increased for larger covers (100x150) + 4 lines of text

        for i in range(start_idx, end_idx):
            book = self.books[i]
            is_selected = (i == self.current_index)

            # Get or create cover
            cover = self.cover_extractor.get_cover(book['path'], self.cover_size)
            if not cover:
                cover = self.cover_extractor.create_fallback_cover(self.cover_size)
            
            # Draw cover
            cover_x = 40
            cover_y = y
            image.paste(cover, (cover_x, cover_y))
            
            # Draw border around cover
            draw.rectangle(
                [(cover_x, cover_y), (cover_x + self.cover_size[0], cover_y + self.cover_size[1])],
                outline=0,
                width=1
            )

            # Draw selection box around entire item
            if is_selected:
                draw.rectangle(
                    [(30, y - 5), (self.width - 30, y + line_height - 10)],
                    outline=0,
                    width=2
                )

            # Draw book title with wrapping
            title = book['title']
            text_x = cover_x + self.cover_size[0] + 15
            text_y = y + 5
            max_text_width = self.width - text_x - 40
            
            # Wrap text to max 4 lines using draw object
            lines = self._wrap_text(title, max_text_width, draw, self.font)
            if len(lines) > 4:
                # Truncate to 4 lines with ellipsis
                lines = lines[:4]
                if len(lines[3]) > 3:
                    lines[3] = lines[3][:-3] + "..."
            
            # Draw wrapped lines
            for line in lines:
                draw.text((text_x, text_y), line, font=self.font, fill=0)
                text_y += 22  # Line spacing
            
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
        self.current_book_path = None  # Track current book for progress saving
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
            self.current_book_path = os.path.abspath(epub_path)  # Store absolute path for progress tracking

            self.page_cache = self.PageCache(self.cache_size)
            self.current_page = 0

            # Pre-fill cache for first few pages
            if self.page_cache:
                self.page_cache.reset()
                self._update_cache(0)  # Cache surrounding pages

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
            self.logger.debug(f"Previous page: {self.current_page + 1}/{self.renderer.get_total_pages()}")
            return True
        return False

    def go_to_page(self, page_number: int):
        """
        Jump to specific page number

        Args:
            page_number: Page number to jump to (0-indexed)
        """
        if not self.renderer:
            return

        total_pages = self.renderer.get_page_count()
        if 0 <= page_number < total_pages:
            self.current_page = page_number
            self.logger.info(f"Jumped to page {page_number + 1}/{total_pages}")

    def cache_page(self, page_number: int):
        """
        Pre-cache a specific page

        Args:
            page_number: Page number to cache (0-indexed)
        """
        if not self.renderer:
            return

        total_pages = self.renderer.get_page_count()
        if 0 <= page_number < total_pages:
            # Render and cache the page
            img = self.renderer.render_page(page_number, show_page_number=self.show_page_numbers)
            self.page_cache.put(page_number, img)
            self.logger.debug(f"Cached page {page_number + 1}/{total_pages}")

    def show_loading_progress(self, percentage: int, message: str = "Loading..."):
        """
        Display loading progress bar on screen

        Args:
            percentage: Progress percentage (0-100)
            message: Loading message to display

        Returns:
            PIL Image with progress bar
        """
        image = Image.new('1', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # Load font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Draw title
        try:
            bbox = draw.textbbox((0, 0), message, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (self.width - text_width) // 2
        except:
            text_x = self.width // 2 - 50

        draw.text((text_x, self.height // 2 - 60), message, font=font, fill=0)

        # Draw progress bar
        bar_width = 400
        bar_height = 30
        bar_x = (self.width - bar_width) // 2
        bar_y = self.height // 2

        # Outline
        draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
                       outline=0, width=2)

        # Fill based on percentage
        fill_width = int((bar_width - 4) * (percentage / 100))
        if fill_width > 0:
            draw.rectangle([bar_x + 2, bar_y + 2,
                           bar_x + 2 + fill_width, bar_y + bar_height - 2],
                           fill=0)

        # Percentage text
        pct_text = f"{percentage}%"
        try:
            bbox = draw.textbbox((0, 0), pct_text, font=small_font)
            pct_width = bbox[2] - bbox[0]
            pct_x = (self.width - pct_width) // 2
        except:
            pct_x = self.width // 2 - 20

        draw.text((pct_x, bar_y + bar_height + 20), pct_text, font=small_font, fill=0)

        return image
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
