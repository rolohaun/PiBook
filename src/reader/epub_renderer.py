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

    def __init__(self, epub_path: str, width: int = 800, height: int = 480, zoom_factor: float = 1.0, dpi: int = 150):
        """
        Initialize EPUB renderer

        Args:
            epub_path: Path to EPUB file
            width: Target screen width
            height: Target screen height
            zoom_factor: Zoom multiplier (1.0 = fit to screen, >1.0 = zoom in, <1.0 = zoom out)
            dpi: Rendering DPI for quality (higher = sharper)
        """
        self.logger = logging.getLogger(__name__)
        self.epub_path = epub_path
        self.width = width
        self.height = height
        self.zoom_factor = zoom_factor
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

    def render_page(self, page_num: int, show_page_number: bool = True) -> Image.Image:
        """
        Render an EPUB page to a PIL Image

        Args:
            page_num: Page number (0-indexed)
            show_page_number: Whether to show page number overlay

        Returns:
            PIL Image (1-bit black/white, sized for e-ink display)
        """
        if page_num < 0 or page_num >= self.page_count:
            raise ValueError(f"Page number {page_num} out of range (0-{self.page_count-1})")

        try:
            # Get page from PyMuPDF
            page = self.doc[page_num]
            
            # Import PIL filters
            from PIL import ImageOps, ImageFilter, ImageEnhance
            
            # Calculate target size
            margin_v = 25 if show_page_number else 0
            usable_width = self.width
            usable_height = self.height - margin_v
            
            # Get page dimensions
            page_rect = page.rect
            page_width = page_rect.width
            page_height = page_rect.height
            
            # Calculate zoom to fit screen - render DIRECTLY at target size
            # This eliminates any resize step which causes quality loss
            zoom_x = usable_width / page_width
            zoom_y = usable_height / page_height
            zoom = min(zoom_x, zoom_y) * self.zoom_factor
            
            # Create transformation matrix for direct rendering at target size
            mat = fitz.Matrix(zoom, zoom)
            
            # Disable anti-aliasing for crisp text rendering on e-ink
            # Level 0 = no anti-aliasing (sharp pixel edges)
            fitz.TOOLS.set_aa_level(0)
            
            # Render page directly at target size - NO RESIZE NEEDED
            pix = page.get_pixmap(matrix=mat, alpha=False)
            self.logger.debug(f"Rendered at {pix.width}x{pix.height} (zoom={zoom:.3f})")

            # Convert PyMuPDF pixmap to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Convert to grayscale
            gray = img.convert('L')
            
            # Detect if this is an image-heavy page (like a cover) or text page
            small = gray.resize((50, 50), Image.Resampling.NEAREST)
            pixels = list(small.getdata())
            unique_values = len(set(pixels))
            is_image_page = unique_values > 40
            self.logger.debug(f"Page {page_num}: unique_values={unique_values}, is_image={is_image_page}")
            
            if is_image_page:
                # For images/covers: use dithering to preserve gradients
                fitz.TOOLS.set_aa_level(8)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                gray = img.convert('L')
                self.logger.debug("Using dithering for image page")
                bw = gray.convert('1')  # Default Floyd-Steinberg dithering
            else:
                # For text: apply aggressive processing for crisp black text
                # 1. Boost contrast significantly
                enhancer = ImageEnhance.Contrast(gray)
                gray = enhancer.enhance(1.5)
                
                # 2. Apply sharpening to enhance text edges
                from PIL import ImageFilter
                gray = gray.filter(ImageFilter.SHARPEN)
                
                # 3. Use manual threshold for crisp black/white conversion
                # Higher threshold (200) = more aggressive black, crisper text
                # This is the key to matching Pillow's direct text rendering
                threshold = 200
                bw = gray.point(lambda x: 0 if x < threshold else 255, '1')
                self.logger.debug(f"Using manual threshold ({threshold}) for text page")

            # Create white 1-bit background
            background = Image.new('1', (self.width, self.height), 1)  # 1 = white

            # Center the content
            x_offset = (self.width - bw.width) // 2
            y_offset = (usable_height - bw.height) // 2
            background.paste(bw, (x_offset, y_offset))

            # Add page number overlay if requested
            if show_page_number:
                from PIL import ImageDraw, ImageFont
                draw = ImageDraw.Draw(background)

                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
                except:
                    font = ImageFont.load_default()

                page_text = f"Page {page_num + 1} of {self.page_count}"
                try:
                    bbox_text = draw.textbbox((0, 0), page_text, font=font)
                    text_width = bbox_text[2] - bbox_text[0]
                    text_x = (self.width - text_width) // 2
                except:
                    text_x = self.width // 2 - 50

                # For 1-bit images, fill=0 is black
                draw.text((text_x, self.height - 22), page_text, fill=0, font=font)

            self.logger.debug(f"Rendered page {page_num + 1}/{self.page_count}")
            return background

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
