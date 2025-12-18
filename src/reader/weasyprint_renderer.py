"""
EPUB rendering engine using EbookLib + WeasyPrint.
Extracts HTML/CSS from EPUB and renders with WeasyPrint for crisp text.
PORTABILITY: Requires WeasyPrint dependencies (Pango, etc.)
"""

import ebooklib
from ebooklib import epub
from weasyprint import HTML, CSS
from PIL import Image
import io
import logging
import tempfile
import os
from typing import Dict, Optional, List
from bs4 import BeautifulSoup


class WeasyPrintRenderer:
    """
    EPUB renderer using EbookLib for parsing and WeasyPrint for rendering.
    Produces high-quality text rendering with proper font handling.
    """

    def __init__(self, epub_path: str, width: int = 800, height: int = 480, zoom_factor: float = 1.0, dpi: int = 150):
        """
        Initialize EPUB renderer

        Args:
            epub_path: Path to EPUB file
            width: Target screen width
            height: Target screen height
            zoom_factor: Zoom multiplier
            dpi: Rendering DPI for quality
        """
        self.logger = logging.getLogger(__name__)
        self.epub_path = epub_path
        self.width = width
        self.height = height
        self.zoom_factor = zoom_factor
        self.dpi = dpi
        self.book = None
        self.chapters = []  # List of (title, html_content, css_content)
        self.page_count = 0
        self.current_chapter = 0
        self.pages_per_chapter = []  # Number of pages in each chapter
        
        # Temporary directory for extracting EPUB assets
        self.temp_dir = tempfile.mkdtemp(prefix='pibook_epub_')
        
        try:
            self._load_epub()
        except Exception as e:
            self.logger.error(f"Failed to load EPUB: {e}")
            raise

    def _load_epub(self):
        """Load and parse the EPUB file"""
        self.book = epub.read_epub(self.epub_path)
        
        # Extract all CSS stylesheets
        css_content = ""
        for item in self.book.get_items_of_type(ebooklib.ITEM_STYLE):
            try:
                css_content += item.get_content().decode('utf-8') + "\n"
            except Exception as e:
                self.logger.warning(f"Failed to decode CSS: {e}")
        
        # Extract all images and save to temp dir
        for item in self.book.get_items_of_type(ebooklib.ITEM_IMAGE):
            try:
                img_path = os.path.join(self.temp_dir, item.get_name())
                os.makedirs(os.path.dirname(img_path), exist_ok=True)
                with open(img_path, 'wb') as f:
                    f.write(item.get_content())
            except Exception as e:
                self.logger.warning(f"Failed to extract image {item.get_name()}: {e}")
        
        # Extract chapters (HTML documents)
        self.chapters = []
        for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            try:
                html_content = item.get_content().decode('utf-8')
                title = item.get_name()
                self.chapters.append({
                    'title': title,
                    'html': html_content,
                    'css': css_content,
                    'name': item.get_name()
                })
            except Exception as e:
                self.logger.warning(f"Failed to process chapter: {e}")
        
        # Pre-render to count pages
        self._calculate_page_count()
        
        self.logger.info(f"Loaded EPUB: {self.epub_path} ({len(self.chapters)} chapters, ~{self.page_count} pages)")

    def _calculate_page_count(self):
        """Estimate total page count by rendering each chapter"""
        # For now, assume 1 page per chapter (we'll paginate within chapters later)
        self.page_count = len(self.chapters)
        self.pages_per_chapter = [1] * len(self.chapters)

    def _prepare_html_for_render(self, chapter: dict) -> str:
        """
        Prepare HTML for rendering with WeasyPrint.
        Fixes relative paths, adds CSS, etc.
        """
        html = chapter['html']
        css = chapter['css']
        
        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Fix image paths to point to temp directory
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src and not src.startswith(('http://', 'https://', 'data:')):
                # Convert relative path to absolute path in temp dir
                img['src'] = os.path.join(self.temp_dir, src).replace('\\', '/')
        
        # Add custom CSS for e-ink optimization
        eink_css = f"""
        @page {{
            size: {self.width}px {self.height}px;
            margin: 20px;
        }}
        body {{
            font-family: 'DejaVu Serif', 'Liberation Serif', 'Times New Roman', serif;
            font-size: 14pt;
            line-height: 1.4;
            color: black;
            background: white;
            margin: 0;
            padding: 10px;
        }}
        p {{
            text-align: justify;
            margin-bottom: 0.5em;
        }}
        h1, h2, h3 {{
            font-weight: bold;
            margin-top: 1em;
            margin-bottom: 0.5em;
        }}
        img {{
            max-width: 100%;
            height: auto;
        }}
        """
        
        # Inject CSS into head
        style_tag = soup.new_tag('style')
        style_tag.string = eink_css + "\n" + css
        
        if soup.head:
            soup.head.append(style_tag)
        else:
            head = soup.new_tag('head')
            head.append(style_tag)
            if soup.html:
                soup.html.insert(0, head)
        
        return str(soup)

    def render_page(self, page_num: int, show_page_number: bool = True) -> Image.Image:
        """
        Render an EPUB page to a PIL Image

        Args:
            page_num: Page number (0-indexed)
            show_page_number: Whether to show page number overlay

        Returns:
            PIL Image in 1-bit mode for e-ink display
        """
        try:
            # For now, page_num maps directly to chapter
            if page_num < 0 or page_num >= len(self.chapters):
                self.logger.error(f"Page {page_num} out of range (0-{len(self.chapters)-1})")
                return Image.new('1', (self.width, self.height), 1)
            
            chapter = self.chapters[page_num]
            html_content = self._prepare_html_for_render(chapter)
            
            # Render with WeasyPrint to PNG in memory
            html = HTML(string=html_content, base_url=self.temp_dir)
            
            # Render to PNG bytes
            png_bytes = io.BytesIO()
            html.write_png(png_bytes, resolution=self.dpi)
            png_bytes.seek(0)
            
            # Load as PIL Image
            img = Image.open(png_bytes)
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize to fit screen while maintaining aspect ratio
            margin_v = 25 if show_page_number else 0
            usable_width = self.width
            usable_height = self.height - margin_v
            
            # Calculate scale to fit
            scale_x = usable_width / img.width
            scale_y = usable_height / img.height
            scale = min(scale_x, scale_y) * self.zoom_factor
            
            target_width = int(img.width * scale)
            target_height = int(img.height * scale)
            
            # Only resize if needed
            if target_width != img.width or target_height != img.height:
                img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Convert to grayscale
            gray = img.convert('L')
            
            # Detect if this is mostly text or image
            small = gray.resize((50, 50), Image.Resampling.NEAREST)
            pixels = list(small.getdata())
            unique_values = len(set(pixels))
            is_image_page = unique_values > 40
            
            if is_image_page:
                # Use dithering for images
                bw = gray.convert('1')
            else:
                # Use threshold for text
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Contrast(gray)
                gray = enhancer.enhance(1.3)
                bw = gray.convert('1', dither=Image.Dither.NONE)
            
            # Create white background
            background = Image.new('1', (self.width, self.height), 1)
            
            # Center content
            x_offset = (self.width - bw.width) // 2
            y_offset = (usable_height - bw.height) // 2
            background.paste(bw, (x_offset, y_offset))
            
            # Add page number
            if show_page_number:
                from PIL import ImageDraw, ImageFont
                draw = ImageDraw.Draw(background)
                
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
                except:
                    font = ImageFont.load_default()
                
                page_text = f"Page {page_num + 1} of {self.page_count}"
                try:
                    bbox = draw.textbbox((0, 0), page_text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_x = (self.width - text_width) // 2
                except:
                    text_x = self.width // 2 - 50
                
                draw.text((text_x, self.height - 22), page_text, fill=0, font=font)
            
            self.logger.debug(f"Rendered page {page_num + 1}/{self.page_count}")
            return background
            
        except Exception as e:
            self.logger.error(f"Failed to render page {page_num}: {e}")
            import traceback
            traceback.print_exc()
            return Image.new('1', (self.width, self.height), 1)

    def get_page_count(self) -> int:
        """Get total number of pages"""
        return self.page_count

    def get_metadata(self) -> Dict[str, str]:
        """Extract metadata from EPUB"""
        if not self.book:
            return {}

        metadata = {
            'title': 'Unknown',
            'author': 'Unknown'
        }
        
        try:
            title = self.book.get_metadata('DC', 'title')
            if title:
                metadata['title'] = title[0][0]
            
            creator = self.book.get_metadata('DC', 'creator')
            if creator:
                metadata['author'] = creator[0][0]
        except Exception as e:
            self.logger.warning(f"Failed to extract metadata: {e}")
        
        return metadata

    def close(self):
        """Clean up resources"""
        # Clean up temp directory
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            self.logger.warning(f"Failed to cleanup temp dir: {e}")
        
        self.book = None
        self.chapters = []

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.close()
