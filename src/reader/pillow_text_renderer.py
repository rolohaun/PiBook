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

    def _load_fonts(self):
        """Load specific TrueType fonts for styles"""
        # Font search paths with proper file names
        font_candidates = [
            # DejaVu Serif (common on Raspberry Pi)
            {
                'normal': '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
                'bold': '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
                'italic': '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf',
                'bold_italic': '/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf',
            },
            # Liberation Serif
            {
                'normal': '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
                'bold': '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf',
                'italic': '/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf',
                'bold_italic': '/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf',
            },
            # Windows fonts
            {
                'normal': 'C:/Windows/Fonts/times.ttf',
                'bold': 'C:/Windows/Fonts/timesbd.ttf',
                'italic': 'C:/Windows/Fonts/timesi.ttf',
                'bold_italic': 'C:/Windows/Fonts/timesbi.ttf',
            },
        ]

        # Find first available font family
        font_paths = None
        for candidate in font_candidates:
            if os.path.exists(candidate['normal']):
                font_paths = candidate
                self.logger.info(f"Using font: {candidate['normal']}")
                break

        if not font_paths:
            self.logger.warning("No TrueType fonts found, using default bitmap font")
            default = ImageFont.load_default()
            self.fonts = {k: default for k in ['normal', 'bold', 'italic', 'bold_italic', 'h1', 'h2']}
            return

        # Load fonts with fallback to normal if variants don't exist
        def load_font(style, size):
            path = font_paths.get(style, font_paths['normal'])
            if not os.path.exists(path):
                path = font_paths['normal']  # Fallback to normal
            try:
                return ImageFont.truetype(path, size)
            except Exception as e:
                self.logger.warning(f"Failed to load {path}: {e}")
                return ImageFont.load_default()

        self.fonts['normal'] = load_font('normal', self.base_font_size)
        self.fonts['bold'] = load_font('bold', self.base_font_size)
        self.fonts['italic'] = load_font('italic', self.base_font_size)
        self.fonts['bold_italic'] = load_font('bold_italic', self.base_font_size)
        self.fonts['h1'] = load_font('bold', self.header_font_size)
        self.fonts['h2'] = load_font('bold', int(self.header_font_size * 0.9))

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

    def _parse_html(self, html: str) -> List[TextToken]:
        """Parse HTML into flat list of tokens with styles"""
        soup = BeautifulSoup(html, 'html.parser')
        tokens = []

        # Remove metadata
        for tag in soup(['head', 'script', 'style', 'title', 'meta']):
            tag.decompose()

        def process_node(node, current_style='normal'):
            if isinstance(node, NavigableString):
                text = str(node).replace('\n', ' ').strip()
                if not text: return

                words = re.split(r'(\s+)', str(node).replace('\n', ' '))
                for w in words:
                    if w:
                        tokens.append(TextToken(w, current_style))
                return

            if isinstance(node, Tag):
                style = current_style
                is_block = node.name in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'br', 'li']

                # Determine style
                if node.name in ['b', 'strong']:
                    style = 'bold_italic' if 'italic' in style else 'bold'
                elif node.name in ['i', 'em']:
                    style = 'bold_italic' if 'bold' in style else 'italic'
                elif node.name == 'h1':
                    style = 'h1'
                elif node.name == 'h2':
                    style = 'h2'
                elif node.name in ['h3', 'h4']:
                    style = 'bold'

                if is_block and tokens and not tokens[-1].new_paragraph:
                    # Mark last token to end paragraph
                    tokens[-1] = tokens[-1]._replace(new_paragraph=True)

                for child in node.children:
                    process_node(child, style)

                if is_block and tokens and not tokens[-1].new_paragraph:
                    tokens[-1] = tokens[-1]._replace(new_paragraph=True)

        process_node(soup.body if soup.body else soup)
        return tokens

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
