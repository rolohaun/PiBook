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
from io import BytesIO
from typing import List, NamedTuple, Union
from bs4 import BeautifulSoup, NavigableString, Tag

# Optional: SVG support (requires cairosvg)
try:
    import cairosvg
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False

# Define a token structure for rich text
class TextToken(NamedTuple):
    text: str
    style: str  # 'normal', 'bold', 'italic', 'bold_italic', 'h1', 'h2', 'center'
    new_paragraph: bool = False
    align: str = 'left'  # 'left', 'center', 'right'

# Define an image token for embedded images
class ImageToken(NamedTuple):
    image: Image.Image
    max_width: int  # Maximum width in pixels
    max_height: int  # Maximum height in pixels
    new_paragraph: bool = True

# Define a table token for HTML tables
class TableToken(NamedTuple):
    rows: List[List[str]]  # 2D array of cell contents
    max_width: int  # Maximum width for table
    new_paragraph: bool = True

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
        self.pages = []  # List of pages, each page is a list of render items (text or image)
        self.page_count = 0
        self.images = {}  # Cache for EPUB images: {src_path: PIL.Image}
        self.custom_fonts = {}  # Cache for EPUB embedded fonts: {font_name: font_path}
        
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
            # Still need to load the book for images and fonts
            self.book = epub.read_epub(self.epub_path)
            self._extract_images()
            self._extract_fonts()
            return

        self.book = epub.read_epub(self.epub_path)

        # First pass: Extract and cache all images and fonts from EPUB
        self._extract_images()
        self._extract_fonts()

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

    def _extract_images(self):
        """Extract all images from EPUB and cache them (including SVG conversion)"""
        for item in self.book.get_items_of_type(ebooklib.ITEM_IMAGE):
            try:
                img_name = item.get_name()
                img_data = item.get_content()

                # Check if this is an SVG file
                if img_name.lower().endswith('.svg'):
                    if SVG_SUPPORT:
                        try:
                            # Convert SVG to PNG using cairosvg
                            png_data = cairosvg.svg2png(bytestring=img_data, output_width=800)
                            img = Image.open(BytesIO(png_data))
                            self.logger.debug(f"Converted SVG to raster: {img_name}")
                        except Exception as e:
                            self.logger.warning(f"Failed to convert SVG {img_name}: {e}")
                            continue
                    else:
                        self.logger.warning(f"SVG support not available (install cairosvg): {img_name}")
                        continue
                else:
                    # Regular raster image (PNG, JPG, GIF, etc.)
                    img = Image.open(BytesIO(img_data))

                # Convert to appropriate mode for e-ink
                if img.mode == 'RGBA':
                    # Create white background for transparency
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                    img = background
                elif img.mode not in ['RGB', 'L', '1']:
                    img = img.convert('RGB')

                # Store with filename as key
                self.images[img_name] = img
                self.logger.debug(f"Extracted image: {img_name} ({img.size[0]}x{img.size[1]})")
            except Exception as e:
                self.logger.warning(f"Failed to extract image {item.get_name()}: {e}")

        self.logger.info(f"Extracted {len(self.images)} images from EPUB")

    def _extract_fonts(self):
        """Extract embedded fonts from EPUB"""
        import tempfile

        for item in self.book.get_items():
            # Check if this is a font file (TTF, OTF, WOFF, etc.)
            item_name = item.get_name().lower()
            if any(item_name.endswith(ext) for ext in ['.ttf', '.otf', '.woff', '.woff2']):
                try:
                    font_data = item.get_content()

                    # WOFF/WOFF2 fonts need conversion (skip for now - complex)
                    if item_name.endswith(('.woff', '.woff2')):
                        self.logger.debug(f"Skipping WOFF font (conversion not supported): {item.get_name()}")
                        continue

                    # Save TTF/OTF to temp file (PIL needs file path, not bytes)
                    temp_font = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(item_name)[1])
                    temp_font.write(font_data)
                    temp_font.close()

                    # Extract font family name from filename
                    font_name = os.path.splitext(os.path.basename(item_name))[0]
                    self.custom_fonts[font_name] = temp_font.name

                    self.logger.debug(f"Extracted font: {font_name} from {item.get_name()}")
                except Exception as e:
                    self.logger.warning(f"Failed to extract font {item.get_name()}: {e}")

        if self.custom_fonts:
            self.logger.info(f"Extracted {len(self.custom_fonts)} custom fonts from EPUB")
            # Try to use custom fonts if available
            self._try_load_custom_fonts()

    def _try_load_custom_fonts(self):
        """Try to load custom EPUB fonts for rendering"""
        # Look for fonts that might replace our default fonts
        for font_name, font_path in self.custom_fonts.items():
            font_name_lower = font_name.lower()

            # Try to match to our font styles
            try:
                if 'bolditalic' in font_name_lower or 'bold-italic' in font_name_lower:
                    self.fonts['bold_italic'] = ImageFont.truetype(font_path, self.base_font_size)
                    self.logger.info(f"Using custom bold-italic font: {font_name}")
                elif 'bold' in font_name_lower:
                    self.fonts['bold'] = ImageFont.truetype(font_path, self.base_font_size)
                    self.fonts['h1'] = ImageFont.truetype(font_path, self.header_font_size)
                    self.fonts['h2'] = ImageFont.truetype(font_path, int(self.header_font_size * 0.9))
                    self.logger.info(f"Using custom bold font: {font_name}")
                elif 'italic' in font_name_lower:
                    self.fonts['italic'] = ImageFont.truetype(font_path, self.base_font_size)
                    self.logger.info(f"Using custom italic font: {font_name}")
                elif 'regular' in font_name_lower or 'normal' in font_name_lower or len(self.custom_fonts) == 1:
                    # Use as default font if it's marked as regular/normal or it's the only font
                    self.fonts['normal'] = ImageFont.truetype(font_path, self.base_font_size)
                    self.logger.info(f"Using custom normal font: {font_name}")
            except Exception as e:
                self.logger.warning(f"Failed to load custom font {font_name}: {e}")

    def _parse_html(self, html: str) -> List[Union[TextToken, ImageToken, TableToken]]:
        """Parse HTML into flat list of tokens with styles"""
        soup = BeautifulSoup(html, 'html.parser')
        tokens = []

        # Remove metadata
        for tag in soup(['head', 'script', 'style', 'title', 'meta']):
            tag.decompose()

        def process_node(node, current_style='normal', current_align='left'):
            if isinstance(node, NavigableString):
                text = str(node).replace('\n', ' ').strip()
                if not text: return

                words = re.split(r'(\s+)', str(node).replace('\n', ' '))
                for w in words:
                    if w:
                        tokens.append(TextToken(w, current_style, False, current_align))
                return

            if isinstance(node, Tag):
                # Handle table tags
                if node.name == 'table':
                    rows = []
                    for tr in node.find_all('tr'):
                        cells = []
                        for cell in tr.find_all(['td', 'th']):
                            # Extract text from cell, preserving basic formatting
                            cell_text = cell.get_text(separator=' ', strip=True)
                            cells.append(cell_text)
                        if cells:
                            rows.append(cells)

                    if rows:
                        tokens.append(TableToken(rows, self.text_width))
                        self.logger.debug(f"Added table token: {len(rows)} rows")
                    return  # Don't process children of table tag

                # Handle image tags
                if node.name == 'img':
                    src = node.get('src', '')
                    if src:
                        # Normalize path (remove ../ and leading /)
                        img_path = src.split('/')[-1]  # Get just the filename

                        # Try to find image in cache
                        img = None
                        for key in self.images.keys():
                            if key.endswith(img_path) or img_path in key:
                                img = self.images[key]
                                break

                        if img:
                            # Add image token with max dimensions
                            max_img_width = self.text_width
                            max_img_height = int(self.text_height * 0.6)  # Max 60% of page height
                            tokens.append(ImageToken(img, max_img_width, max_img_height))
                            self.logger.debug(f"Added image token: {img_path}")
                        else:
                            self.logger.warning(f"Image not found in EPUB: {src}")
                    return  # Don't process children of img tag

                style = current_style
                align = current_align
                is_block = node.name in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'br', 'li']

                # Check for CSS text-align in style attribute
                node_style = node.get('style', '')
                if 'text-align' in node_style:
                    if 'center' in node_style:
                        align = 'center'
                    elif 'right' in node_style:
                        align = 'right'
                    elif 'left' in node_style:
                        align = 'left'

                # Check for center tag
                if node.name == 'center':
                    align = 'center'

                # Determine style
                if node.name in ['b', 'strong']:
                    style = 'bold_italic' if 'italic' in style else 'bold'
                elif node.name in ['i', 'em']:
                    style = 'bold_italic' if 'bold' in style else 'italic'
                elif node.name == 'h1':
                    style = 'h1'
                    align = 'center'  # Headers are typically centered
                elif node.name == 'h2':
                    style = 'h2'
                    align = 'center'  # Headers are typically centered
                elif node.name in ['h3', 'h4']:
                    style = 'bold'

                if is_block and tokens and not tokens[-1].new_paragraph:
                    # Mark last token to end paragraph
                    if isinstance(tokens[-1], TextToken):
                        tokens[-1] = tokens[-1]._replace(new_paragraph=True)

                for child in node.children:
                    process_node(child, style, align)

                if is_block and tokens and not tokens[-1].new_paragraph:
                    # Mark last token to end paragraph
                    if isinstance(tokens[-1], TextToken):
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

            # Handle table tokens
            if isinstance(token, TableToken):
                # Finish current line first
                if current_line:
                    current_y = finish_line(current_line, current_y, current_line_max_h or self.base_font_size)
                    current_line = []
                    current_line_max_h = 0

                # Calculate table dimensions
                rows = token.rows
                if rows:
                    # Calculate column widths (equal distribution for simplicity)
                    num_cols = max(len(row) for row in rows)
                    col_width = token.max_width // num_cols
                    row_height = int(self.base_font_size * 1.5)
                    table_height = len(rows) * row_height

                    # Check if table fits on current page
                    if current_y + table_height > self.height - self.margin_bottom:
                        # Start new page
                        self.pages.append(current_page)
                        current_page = []
                        current_y = self.margin_top

                    # Add table to page (special marker: 'TABLE' with table data)
                    current_page.append((self.margin_left, current_y, rows, 'TABLE', col_width, row_height))
                    current_y += table_height + self.paragraph_spacing * 2

                # Reset text position
                current_x = self.margin_left + self.paragraph_indent
                continue

            # Handle image tokens
            if isinstance(token, ImageToken):
                # Finish current line first
                if current_line:
                    current_y = finish_line(current_line, current_y, current_line_max_h or self.base_font_size)
                    current_line = []
                    current_line_max_h = 0

                # Scale image to fit
                img = token.image
                img_w, img_h = img.size

                # Calculate scaled dimensions
                scale = min(token.max_width / img_w, token.max_height / img_h, 1.0)
                new_w = int(img_w * scale)
                new_h = int(img_h * scale)

                # Check if image fits on current page
                if current_y + new_h > self.height - self.margin_bottom:
                    # Start new page
                    self.pages.append(current_page)
                    current_page = []
                    current_y = self.margin_top

                # Add image to page (special marker: 'IMAGE' style with image object)
                img_x = self.margin_left + (self.text_width - new_w) // 2  # Center image
                current_page.append((img_x, current_y, img, 'IMAGE', new_w, new_h))
                current_y += new_h + self.paragraph_spacing * 2

                # Reset text position
                current_x = self.margin_left + self.paragraph_indent
                continue

            # Handle text tokens
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
            for item in self.pages[page_num]:
                # Check if this is an image item (has 6 elements)
                if len(item) == 6:
                    x, y, data, style_marker, w, h = item

                    if style_marker == 'IMAGE':
                        # Resize and convert image to 1-bit for e-ink
                        resized_img = data.resize((w, h), Image.Resampling.LANCZOS)

                        # Convert to grayscale first, then to 1-bit with dithering for better quality
                        if resized_img.mode != 'L':
                            resized_img = resized_img.convert('L')

                        # Convert to 1-bit with Floyd-Steinberg dithering for better image quality
                        bw_img = resized_img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)

                        # Paste the image onto the page
                        image.paste(bw_img, (x, y))

                    elif style_marker == 'TABLE':
                        # Render table with borders
                        rows = data  # data contains the table rows
                        col_width = w  # w contains column width
                        row_height = h  # h contains row height

                        font = self.fonts['normal']
                        num_cols = max(len(row) for row in rows) if rows else 0
                        table_width = col_width * num_cols
                        table_height = row_height * len(rows)

                        # Draw table border
                        draw.rectangle([x, y, x + table_width, y + table_height], outline=0, width=2)

                        # Draw rows and cells
                        for row_idx, row in enumerate(rows):
                            row_y = y + (row_idx * row_height)

                            # Draw horizontal line
                            if row_idx > 0:
                                draw.line([(x, row_y), (x + table_width, row_y)], fill=0, width=1)

                            for col_idx, cell in enumerate(row):
                                col_x = x + (col_idx * col_width)

                                # Draw vertical line
                                if col_idx > 0:
                                    draw.line([(col_x, y), (col_x, y + table_height)], fill=0, width=1)

                                # Draw cell text (truncate if too long)
                                cell_text = str(cell)
                                max_chars = int(col_width / (self.base_font_size * 0.6))
                                if len(cell_text) > max_chars:
                                    cell_text = cell_text[:max_chars-3] + '...'

                                # Center text in cell
                                text_x = col_x + 5  # Small padding
                                text_y = row_y + (row_height - self.base_font_size) // 2
                                draw.text((text_x, text_y), cell_text, font=font, fill=0)
                else:
                    # Text item (4 elements)
                    x, y, text, style = item
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
