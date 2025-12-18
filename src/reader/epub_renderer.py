"""
EPUB rendering engine using PyMuPDF (fitz).
Renders EPUB pages directly to images with formatting preserved.
PORTABILITY: 100% portable between Pi 3B+ and Pi Zero 2 W
"""

import fitz  # PyMuPDF
from PIL import Image
import logging
from typing import Dict, Optional


class EPUBRenderer:
    """
    EPUB renderer using PyMuPDF
    """

    def __init__(self, epub_path: str, width: int = 800, height: int = 480, dpi: int = 150):
        """
        Initialize EPUB renderer

        Args:
            epub_path: Path to EPUB file
            width: Target screen width
            height: Target screen height
            dpi: DPI for rendering
        """
        self.logger = logging.getLogger(__name__)
        self.epub_path = epub_path
        self.width = width
        self.height = height
        self.dpi = dpi
        self.doc = None
        self.page_count = 0

        try:
            self.doc = fitz.open(epub_path)
            self.page_count = len(self.doc)
            self.logger.info(f"Opened EPUB: {epub_path} ({self.page_count} pages)")
        except Exception as e:
            self.logger.error(f"Failed to open EPUB: {e}")
            raise

    def render_page(self, page_num: int) -> Image.Image:
        """
        Render an EPUB page to a PIL Image

        Args:
            page_num: Page number (0-indexed)

        Returns:
            PIL Image (1-bit black/white, sized for e-ink display)
        """
        if page_num < 0 or page_num >= self.page_count:
            raise ValueError(f"Page number {page_num} out of range (0-{self.page_count-1})")

        try:
            # Get page from PyMuPDF
            page = self.doc[page_num]

            # Calculate zoom to fit screen while maintaining aspect ratio
            zoom_x = self.width / page.rect.width
            zoom_y = self.height / page.rect.height
            zoom = min(zoom_x, zoom_y)

            # Create transformation matrix
            mat = fitz.Matrix(zoom, zoom)

            # Render page to pixmap (RGB image)
            pix = page.get_pixmap(matrix=mat, dpi=self.dpi)

            # Convert PyMuPDF pixmap to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Resize to exact screen dimensions (adding borders if needed)
            if img.size != (self.width, self.height):
                # Create white background
                background = Image.new('RGB', (self.width, self.height), 'white')

                # Center the rendered page
                x_offset = (self.width - img.width) // 2
                y_offset = (self.height - img.height) // 2
                background.paste(img, (x_offset, y_offset))
                img = background

            # Convert to 1-bit (black and white) for e-ink display
            img = img.convert('1')

            self.logger.debug(f"Rendered page {page_num}")
            return img

        except Exception as e:
            self.logger.error(f"Failed to render page {page_num}: {e}")
            # Return blank page on error
            return Image.new('1', (self.width, self.height), 1)

    def get_page_count(self) -> int:
        """Get total number of pages"""
        return self.page_count

    def get_metadata(self) -> Dict[str, str]:
        """
        Extract metadata from EPUB

        Returns:
            Dictionary with title, author, etc.
        """
        if not self.doc:
            return {}

        metadata = {
            'title': self.doc.metadata.get('title', 'Unknown'),
            'author': self.doc.metadata.get('author', 'Unknown'),
            'subject': self.doc.metadata.get('subject', ''),
            'keywords': self.doc.metadata.get('keywords', ''),
        }

        self.logger.debug(f"Metadata: {metadata}")
        return metadata

    def get_page_text(self, page_num: int) -> str:
        """
        Extract text from a page (for search/indexing)

        Args:
            page_num: Page number (0-indexed)

        Returns:
            Plain text content of page
        """
        if page_num < 0 or page_num >= self.page_count:
            return ""

        try:
            page = self.doc[page_num]
            return page.get_text()
        except Exception as e:
            self.logger.error(f"Failed to extract text from page {page_num}: {e}")
            return ""

    def close(self):
        """Close the EPUB document"""
        if self.doc:
            self.doc.close()
            self.logger.info("EPUB closed")
