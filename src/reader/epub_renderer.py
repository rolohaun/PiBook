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

            # Disable anti-aliasing for crisp text rendering on e-ink
            # Level 0 = no anti-aliasing (sharp pixel edges)
            # This is crucial for 1-bit e-ink displays
            fitz.TOOLS.set_aa_level(0)

            # Render at high DPI for quality - higher = sharper source
            render_dpi = max(self.dpi, 300)
            pix = page.get_pixmap(dpi=render_dpi)

            # Convert PyMuPDF pixmap to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Import PIL filters
            from PIL import ImageOps, ImageFilter, ImageEnhance
            
            # AUTO-CROP: Remove whitespace margins from the EPUB's internal styling
            gray_for_crop = img.convert('L')
            inverted = ImageOps.invert(gray_for_crop)
            bbox = inverted.getbbox()
            if bbox:
                padding = 10
                left = max(0, bbox[0] - padding)
                top = max(0, bbox[1] - padding)
                right = min(img.width, bbox[2] + padding)
                bottom = min(img.height, bbox[3] + padding)
                img = img.crop((left, top, right, bottom))
                self.logger.debug(f"Auto-cropped from {pix.width}x{pix.height} to {img.width}x{img.height}")

            # Convert to grayscale
            gray = img.convert('L')
            
            # Detect if this is an image-heavy page (like a cover) or text page
            # Image pages have many unique gray values, text pages are mostly black/white
            # Sample the image to check variance
            small = gray.resize((100, 100), Image.Resampling.NEAREST)
            pixels = list(small.getdata())
            unique_values = len(set(pixels))
            
            # If many unique gray values (>50), this is likely an image - use dithering
            # If few unique values, this is text - use threshold
            is_image_page = unique_values > 50
            self.logger.debug(f"Page {page_num}: unique gray values={unique_values}, is_image={is_image_page}")
            
            # Calculate target size
            margin_v = 25 if show_page_number else 0
            usable_width = self.width
            usable_height = self.height - margin_v

            zoom_x = usable_width / gray.width
            zoom_y = usable_height / gray.height
            zoom = min(zoom_x, zoom_y) * self.zoom_factor

            target_width = int(gray.width * zoom)
            target_height = int(gray.height * zoom)
            
            # Resize FIRST in grayscale (high quality), THEN convert to 1-bit
            gray = gray.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            if is_image_page:
                # For images/covers: use Floyd-Steinberg dithering to preserve shading
                # Re-enable anti-aliasing for smooth gradients in images
                fitz.TOOLS.set_aa_level(8)
                self.logger.debug("Using dithering for image page")
                bw = gray.convert('1')  # Default dithering preserves gradients
            else:
                # For text: use threshold conversion WITHOUT dithering
                # The dither=False parameter is crucial - it prevents Pillow from
                # creating gray dithering patterns that look fuzzy on e-ink
                enhancer = ImageEnhance.Contrast(gray)
                gray = enhancer.enhance(1.3)  # Slight contrast boost
                
                # Apply sharpening for crisper text edges
                gray = gray.filter(ImageFilter.SHARPEN)
                
                # Convert to 1-bit with dither=False for crisp threshold
                # This uses simple threshold at 128 (midpoint) without dithering
                bw = gray.convert('1', dither=Image.Dither.NONE)
                self.logger.debug("Using threshold (no dither) for text page")

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
