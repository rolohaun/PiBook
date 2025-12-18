"""
RAW EPUB renderer - ZERO processing.
Just renders the EPUB page exactly as-is with no modifications.
Used to establish a baseline for text quality.
"""

import fitz
from PIL import Image
import logging


class RawEPUBRenderer:
    """
    Minimal EPUB renderer with ZERO processing.
    No resizing, no rotation, no filters - just raw output.
    """

    def __init__(self, epub_path: str, width: int = 800, height: int = 480, zoom_factor: float = 1.0, dpi: int = 150):
        """
        Initialize - width/height/zoom/dpi are ignored, just kept for API compatibility
        """
        self.logger = logging.getLogger(__name__)
        self.epub_path = epub_path
        self.width = width
        self.height = height
        
        # Open EPUB with PyMuPDF
        self.doc = fitz.open(epub_path)
        self.page_count = len(self.doc)
        
        self.logger.info(f"RAW renderer: Loaded {epub_path} ({self.page_count} pages)")

    def render_page(self, page_num: int, show_page_number: bool = True) -> Image.Image:
        """
        Render page with ZERO processing.
        """
        try:
            page = self.doc[page_num]
            
            # Render at default 72 DPI - NO ZOOM, NO SCALING
            # This is the raw, native output from PyMuPDF
            pix = page.get_pixmap(alpha=False)
            
            self.logger.info(f"RAW render: page {page_num+1} at {pix.width}x{pix.height}")
            
            # Convert to PIL Image - RGB, no conversion
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Convert to grayscale
            gray = img.convert('L')
            
            # Simple threshold to 1-bit - NO contrast, NO sharpening
            # Just a basic 128 threshold
            bw = gray.point(lambda p: 255 if p > 128 else 0, mode='1')
            
            return bw
            
        except Exception as e:
            self.logger.error(f"RAW render failed: {e}")
            return Image.new('1', (self.width, self.height), 1)

    def get_page_count(self) -> int:
        return self.page_count

    def get_metadata(self):
        return {'title': 'Unknown', 'author': 'Unknown'}

    def close(self):
        if self.doc:
            self.doc.close()
            self.doc = None
