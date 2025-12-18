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

    def _load_epub(self):
        self.book = epub.read_epub(self.epub_path)
        all_tokens = []
        
        for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            try:
                html = item.get_content().decode('utf-8')
                tokens = self._parse_html(html)
                all_tokens.extend(tokens)
                # Add chapter break
                all_tokens.append(TextToken("", "normal", new_paragraph=True)) 
            except Exception as e:
                self.logger.warning(f"Chapter error: {e}")
                
        self._reflow_pages(all_tokens)
        self.logger.info(f"Loaded EPUB: {self.page_count} pages")

    def _parse_html(self, html: str) -> List[TextToken]:
        """Parse HTML into flat list of tokens with styles"""
        soup = BeautifulSoup(html, 'html.parser')
        tokens = []
        
        # Remove metadata
        for tag in soup(['head', 'script', 'style']):
            tag.decompose()
            
        def process_node(node, current_style='normal'):
            if isinstance(node, NavigableString):
                text = str(node).replace('\n', ' ').strip()
                if not text: return
                # Split into words to allow wrapping, but keep them as one token for now
                # We'll split tokens by spaces in reflow if needed, or here?
                # Better to split by words here
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
        self.pages = []
        current_page = []
        current_y = self.margin_top
        current_x = self.margin_left
        line_height = 0
        
        # Helper to finish a line
        def finish_line(line_items, y, h):
            # line_items is list of (text, font)
            # Add to current page
            # Check page height
            nonlocal current_y, current_page
            if y + h > self.height - self.margin_bottom:
                self.pages.append(current_page)
                current_page = []
                current_y = self.margin_top
                y = current_y
            
            for txt, fnt, x in line_items:
                current_page.append((x, y, txt, fnt))
            current_y += int(h * self.line_spacing)
            return current_y

        current_line = [] # (text, font, x)
        
        for token in tokens:
            font = self.fonts.get(token.style, self.fonts['normal'])
            
            # Handle headers with extra spacing
            if token.style in ['h1', 'h2'] and not current_line:
                current_y += self.paragraph_spacing
            
            # Measure token
            try:
                width = font.getlength(token.text)
                bbox = font.getbbox(token.text)
                height = bbox[3] - bbox[1] if bbox else self.base_font_size
            except:
                width = len(token.text) * self.base_font_size * 0.6
                height = self.base_font_size

            # Check if fits on line
            if current_x + width > self.width - self.margin_right:
                # Wrap
                # Calculate max height of current line
                max_h = max([i[3].getbbox("Ay")[3] for i in current_line]) if current_line else height
                current_y = finish_line(current_line, current_y, max_h)
                current_line = []
                current_x = self.margin_left
                # If whitespace caused wrap, skip it at start of new line
                if token.text.isspace():
                    continue

            current_line.append((token.text, font, current_x))
            current_x += width
            line_height = max(line_height, height)
            
            if token.new_paragraph:
                # Force new line
                max_h = max([i[3].getbbox("Ay")[3] for i in current_line]) if current_line else height
                current_y = finish_line(current_line, current_y, max_h)
                current_line = []
                current_x = self.margin_left
                current_y += self.paragraph_spacing
                line_height = 0
                
        # Finish last page
        if current_line:
             finish_line(current_line, current_y, line_height)
        if current_page:
            self.pages.append(current_page)
        
        if not self.pages:
            self.pages.append([])
            self.page_count = 1
        else:
            self.page_count = len(self.pages)

    def render_page(self, page_num: int, show_page_number: bool = True) -> Image.Image:
        image = Image.new('1', (self.width, self.height), 1)
        draw = ImageDraw.Draw(image)
        
        if 0 <= page_num < len(self.pages):
            for x, y, text, font in self.pages[page_num]:
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
