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


class LibraryScreen:
    """
    Book library/selection screen
    Renders a list of available EPUB files using Pillow
    """

    def __init__(self, width: int = 800, height: int = 480, items_per_page: int = 8, font_size: int = 20, web_port: int = 5000):
        """
        Initialize library screen

        Args:
            width: Screen width
            height: Screen height
            items_per_page: Number of books to show per page
            font_size: Font size for menu text
            web_port: Web server port number
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

    def render(self) -> Image.Image:
        """
        Render library screen to PIL Image

        Returns:
            PIL Image (1-bit, for e-ink display)
        """
        # Create white background
        image = Image.new('1', (self.width, self.height), 1)
        draw = ImageDraw.Draw(image)

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

    def __init__(self, width: int = 800, height: int = 480, zoom_factor: float = 1.0, dpi: int = 150, cache_size: int = 5, show_page_numbers: bool = True):
        """
        Initialize reader screen

        Args:
            width: Screen width
            height: Screen height
            zoom_factor: Zoom multiplier for content
            dpi: Rendering DPI for quality
            cache_size: Number of pages to cache
            show_page_numbers: Whether to show page numbers
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
        self.renderer_type = None  # Track which renderer is in use

        # RAW renderer - ZERO processing (User requested baseline)
        try:
            from src.reader.raw_renderer import RawEPUBRenderer
            self.RawRenderer = RawEPUBRenderer
            self.logger.info("RAW renderer enabled (zero processing)")
        except ImportError as e:
            self.RawRenderer = None
            self.logger.info(f"RAW renderer not available: {e}")

        # Pillow text renderer - DISABLED
        self.PillowTextRenderer = None

        # WeasyPrint renderer - DISABLED
        self.WeasyPrintRenderer = None

        # Import PyMuPDF renderer as fallback
        from src.reader.epub_renderer import EPUBRenderer
        from src.reader.page_cache import PageCache

        self.EPUBRenderer = EPUBRenderer
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

            # Try RAW renderer first (zero processing - for baseline testing)
            if self.RawRenderer:
                try:
                    self.renderer = self.RawRenderer(epub_path, self.width, self.height, self.zoom_factor, self.dpi)
                    self.renderer_type = 'raw'
                    self.logger.info(f"Using RAW renderer (zero processing) for: {epub_path}")
                except Exception as e:
                    self.logger.warning(f"RAW renderer failed: {e}")
                    self.renderer = None

            # Try Pillow text renderer
            if self.renderer is None and self.PillowTextRenderer:
                try:
                    self.renderer = self.PillowTextRenderer(epub_path, self.width, self.height, self.zoom_factor, self.dpi)
                    self.renderer_type = 'pillow'
                    self.logger.info(f"Using Pillow text renderer for: {epub_path}")
                except Exception as e:
                    self.logger.warning(f"Pillow text renderer failed: {e}")
                    self.renderer = None

            # Try WeasyPrint renderer
            if self.renderer is None and self.WeasyPrintRenderer:
                try:
                    self.renderer = self.WeasyPrintRenderer(epub_path, self.width, self.height, self.zoom_factor, self.dpi)
                    self.renderer_type = 'weasyprint'
                    self.logger.info(f"Using WeasyPrint renderer for: {epub_path}")
                except Exception as e:
                    self.logger.warning(f"WeasyPrint renderer failed: {e}")
                    self.renderer = None

            # Fallback to PyMuPDF renderer
            if self.renderer is None:
                self.renderer = self.EPUBRenderer(epub_path, self.width, self.height, self.zoom_factor, self.dpi)
                self.renderer_type = 'pymupdf'
                self.logger.info(f"Using PyMuPDF renderer for: {epub_path}")

            self.page_cache = self.PageCache(self.cache_size)
            self.current_page = 0
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
