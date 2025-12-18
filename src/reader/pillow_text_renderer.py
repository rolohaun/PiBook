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
        self.margin_bottom = 50
        self.line_spacing = 1.4
        self.paragraph_spacing = 15
        
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

    def _load_fonts(self):
        """Load specific TrueType fonts for styles"""
        font_families = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif",
            "/usr/share/fonts/truetype/liberation/LiberationSerif",
            "C:/Windows/Fonts/times"
        ]
        
        base_path = None
        for path in font_families:
            # Check if Regular exists (handling extensions)
            for ext in ['.ttf', '-Regular.ttf']:
                if os.path.exists(path + ext) or os.path.exists(path + '.ttf'):
                    base_path = path
                    break
            if base_path: break
            
        if not base_path:
            self.logger.warning("No fonts found, using default")
            default = ImageFont.load_default()
            self.fonts = {k: default for k in ['normal', 'bold', 'italic', 'bold_italic', 'h1', 'h2']}
            return

        def load(suffix, size):
            try:
                # Try common naming patterns
                p = f"{base_path}{suffix}.ttf"
                if not os.path.exists(p):
                    p = f"{base_path}{suffix.replace('-','')}.ttf"
                return ImageFont.truetype(p, size)
            except:
                return ImageFont.truetype(f"{base_path}.ttf", size)

        self.fonts['normal'] = load("", self.base_font_size)
        self.fonts['bold'] = load("-Bold", self.base_font_size)
        self.fonts['italic'] = load("-Italic", self.base_font_size)
        self.fonts['bold_italic'] = load("-BoldItalic", self.base_font_size)
        self.fonts['h1'] = load("-Bold", self.header_font_size)
        self.fonts['h2'] = load("-Bold", int(self.header_font_size * 0.9))

    def _get_cache_path(self) -> str:
        """Get path to cache file"""
        return self.epub_path + f".{self.width}x{self.height}.{self.zoom_factor}.cache"

    def _load_cache(self) -> bool:
        """Try to load layout from cache"""
        import pickle
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            try:
                # Check timestamp
                if os.path.getmtime(cache_path) < os.path.getmtime(self.epub_path):
                    return False
                
                with open(cache_path, 'rb') as f:
                    data = pickle.load(f)
                    self.pages = data['pages']
                    self.page_count = data['page_count']
                self.logger.info(f"Loaded layout from cache: {cache_path}")
                return True
            except Exception as e:
                self.logger.warning(f"Failed to load cache: {e}")
        return False

    def _save_cache(self):
        """Save layout to cache"""
        import pickle
        try:
            cache_path = self._get_cache_path()
            with open(cache_path, 'wb') as f:
                pickle.dump({
                    'pages': self.pages,
                    'page_count': self.page_count
                }, f)
            self.logger.info(f"Saved layout to cache: {cache_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save cache: {e}")

    def _load_epub(self):
        self.logger.info(f"Loading EPUB: {self.epub_path}")
        
        # DEBUG: Parsing issue - disable cache
        # if self._load_cache():
        #    return

        self.book = epub.read_epub(self.epub_path)
        all_tokens = []
        
        items = list(self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        self.logger.info(f"Found {len(items)} items in EPUB")

        for i, item in enumerate(items):
            try:
                content = item.get_content()
                self.logger.debug(f"Item {i} raw size: {len(content)}")
                
                try:
                    html = content.decode('utf-8')
                except UnicodeDecodeError:
                    html = content.decode('latin-1', errors='ignore')
                    
                self.logger.debug(f"Item {i} HTML size: {len(html)}")
                
                tokens = self._parse_html(html)
                self.logger.debug(f"Item {i} tokens: {len(tokens)}")
                
                if tokens:
                    all_tokens.extend(tokens)
                    all_tokens.append(TextToken("", "normal", new_paragraph=True)) 
            except Exception as e:
                self.logger.warning(f"Chapter error: {e}")
                
        self.logger.info(f"Total tokens parsed: {len(all_tokens)}")
        self._reflow_pages(all_tokens)
        
        # Only save cache if we have content
        if len(all_tokens) > 100:
            self._save_cache()
            
        self.logger.info(f"Loaded EPUB: {self.page_count} pages")

    # ... (keep _parse_html as is) ...

    def _reflow_pages(self, tokens: List[TextToken]):
        """Reflow tokens into pages based on width/height"""
        self.logger.info(f"Reflowing {len(tokens)} tokens...")
        self.pages = []
        current_page = []
        current_y = self.margin_top
        current_x = self.margin_left
        line_height = 0
        
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
            
            # Handle headers with extra spacing
            if token.style in ['h1', 'h2'] and not current_line:
                current_y += self.paragraph_spacing
            
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
                current_x = self.margin_left
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
                current_x = self.margin_left
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
