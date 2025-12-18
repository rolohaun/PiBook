"""
EPUB renderer using direct Pillow text rendering with RICH TEXT support.
Extracts HTML and preserves basic formatting (Bold, Italic, Headers) 
while rendering directly with TTF fonts for maximum sharpness on e-ink.
"""

import ebooklib
from ebooklib import epub
from PIL import Image, ImageDraw, ImageFont
import logging
import os
import re
import textwrap
from typing import Dict, List, Optional, Tuple, NamedTuple
from bs4 import BeautifulSoup, NavigableString, Tag

# Define a token structure for rich text
class TextToken(NamedTuple):
    text: str
    style: str  # 'normal', 'bold', 'italic', 'bold_italic', 'h1', 'h2'
    new_paragraph: bool = False

class PillowTextRenderer:
    """
    EPUB renderer using direct Pillow text drawing with Rich Text support.
    """

    def __init__(self, epub_path: str, width: int = 800, height: int = 480, zoom_factor: float = 1.0, dpi: int = 150):
        self.logger = logging.getLogger(__name__)
        self.epub_path = epub_path
        self.width = width
        self.height = height
        self.zoom_factor = zoom_factor
        
        # Layout settings
        self.margin_left = 30
        self.margin_right = 30
        self.margin_top = 30
        self.margin_bottom = 40
        self.line_spacing = 1.3
        self.paragraph_spacing = 5    # Reduced for book-like look
        self.paragraph_indent = 40    # Indent for new paragraphs
        
        # Font sizes
        self.base_font_size = int(18 * zoom_factor)
        self.header_font_size = int(24 * zoom_factor)
        
        # Calculate text area
        self.text_width = width - self.margin_left - self.margin_right
        self.text_height = height - self.margin_top - self.margin_bottom
        
        # Load fonts map
        self.fonts = {}
        self._load_fonts()
        
        # Book content
        self.book = None
        self.pages = []  # List of pages, each page is a list of (x, y, text, font) tuples
        self.page_count = 0
        
        try:
            self._load_epub()
        except Exception as e:
            self.logger.error(f"Failed to load EPUB: {e}")
            raise

    # ... (keep font loading) ...

    # ... (keep cache methods) ...

    def _load_epub(self):
        # Try cache first
        if self._load_cache():
            return

        self.book = epub.read_epub(self.epub_path)
        all_tokens = []
        
        for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            try:
                content = item.get_content()
                try:
                    html = content.decode('utf-8')
                except UnicodeDecodeError:
                    html = content.decode('latin-1', errors='ignore')
                    
                tokens = self._parse_html(html)
                if tokens:
                    all_tokens.extend(tokens)
                    all_tokens.append(TextToken("", "normal", new_paragraph=True)) 
            except Exception as e:
                self.logger.warning(f"Chapter error: {e}")
                
        self._reflow_pages(all_tokens)
        self._save_cache()
        self.logger.info(f"Loaded EPUB: {self.page_count} pages")

    # ... (keep _parse_html) ...

    def _reflow_pages(self, tokens: List[TextToken]):
        """Reflow tokens into pages based on width/height"""
        self.logger.info(f"Reflowing {len(tokens)} tokens...")
        self.pages = []
        current_page = []
        current_y = self.margin_top
        current_x = self.margin_left + self.paragraph_indent # Start indented
        
        # Pre-calculate font heights to avoid per-word overhead
        font_metrics = {}
        for style, font in self.fonts.items():
            bbox = font.getbbox("Ay")
            font_metrics[style] = bbox[3] - bbox[1] if bbox else self.base_font_size

        # Helper to finish a line
        def finish_line(line_items, y, h):
            nonlocal current_y, current_page
            if y + h > self.height - self.margin_bottom:
                self.pages.append(current_page)
                current_page = []
                current_y = self.margin_top
                y = current_y
            
            for txt, style, x in line_items:
                current_page.append((x, y, txt, style))
            current_y += int(h * self.line_spacing)
            return current_y

        current_line = [] # (text, style, x)
        current_line_max_h = 0
        
        count = 0
        for token in tokens:
            count += 1
            if count % 10000 == 0:
                self.logger.debug(f"Reflow progress: {count}/{len(tokens)}")

            font = self.fonts.get(token.style, self.fonts['normal'])
            font_h = font_metrics.get(token.style, self.base_font_size)
            
            # Handle headers (no indent, extra space)
            if token.style in ['h1', 'h2']:
                if current_line:
                     current_y = finish_line(current_line, current_y, current_line_max_h or font_h)
                     current_line = []
                     current_line_max_h = 0
                current_x = self.margin_left # Headers not indented
                current_y += self.paragraph_spacing * 2
            
            # Measure token width only
            try:
                width = font.getlength(token.text)
            except:
                width = len(token.text) * self.base_font_size * 0.6

            # Check if fits on line
            if current_x + width > self.width - self.margin_right:
                # Wrap
                current_y = finish_line(current_line, current_y, current_line_max_h or font_h)
                current_line = []
                current_line_max_h = 0
                current_x = self.margin_left # Wrapped lines are NOT indented
                # If whitespace caused wrap, skip it at start of new line
                if token.text.isspace():
                    continue

            current_line.append((token.text, token.style, current_x))
            current_x += width
            current_line_max_h = max(current_line_max_h, font_h)
            
            if token.new_paragraph:
                # Force new line
                current_y = finish_line(current_line, current_y, current_line_max_h or font_h)
                current_line = []
                current_line_max_h = 0
                current_x = self.margin_left + self.paragraph_indent # New paragraph IS indented
                current_y += self.paragraph_spacing
                
        # Finish last page
        if current_line:
             finish_line(current_line, current_y, current_line_max_h)
        if current_page:
            self.pages.append(current_page)
        
        if not self.pages:
            self.pages.append([])
            self.page_count = 1
        else:
            self.page_count = len(self.pages)
        self.logger.info(f"Reflow complete: {self.page_count} pages")

    def render_page(self, page_num: int, show_page_number: bool = True) -> Image.Image:
        image = Image.new('1', (self.width, self.height), 1)
        draw = ImageDraw.Draw(image)
        
        if 0 <= page_num < len(self.pages):
            for x, y, text, style in self.pages[page_num]:
                font = self.fonts.get(style, self.fonts['normal'])
                draw.text((x, y), text, font=font, fill=0)
                
        if show_page_number:
            page_text = f"Page {page_num + 1} of {self.page_count}"
            font = self.fonts['normal']
            try:
                bbox = draw.textbbox((0, 0), page_text, font=font)
                w = bbox[2] - bbox[0]
                draw.text(((self.width - w)//2, self.height - 25), page_text, font=font, fill=0)
            except:
                pass
                
        return image

    def get_page_count(self): return self.page_count
    def get_metadata(self): return {'title': 'Rich Text', 'author': '?'}
    def close(self): pass
