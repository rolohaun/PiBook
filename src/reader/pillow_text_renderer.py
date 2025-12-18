"""
EPUB rendering engine using direct Pillow text rendering.
Extracts plain text from EPUB and renders with TTF fonts for crisp e-ink display.
This approach bypasses HTML rendering engines for maximum text clarity.
"""

import ebooklib
from ebooklib import epub
from PIL import Image, ImageDraw, ImageFont
import logging
import os
import re
import textwrap
from typing import Dict, List, Optional
from bs4 import BeautifulSoup


class PillowTextRenderer:
    """
    EPUB renderer using direct Pillow text drawing.
    Extracts plain text and renders with high-quality TTF fonts.
    """

    def __init__(self, epub_path: str, width: int = 800, height: int = 480, zoom_factor: float = 1.0, dpi: int = 150):
        """
        Initialize EPUB renderer

        Args:
            epub_path: Path to EPUB file
            width: Target screen width
            height: Target screen height
            zoom_factor: Zoom multiplier (affects font size)
            dpi: Not used directly, but kept for API compatibility
        """
        self.logger = logging.getLogger(__name__)
        self.epub_path = epub_path
        self.width = width
        self.height = height
        self.zoom_factor = zoom_factor
        self.dpi = dpi
        
        # Text rendering settings
        self.margin_left = 30
        self.margin_right = 30
        self.margin_top = 30
        self.margin_bottom = 50  # Room for page number
        self.line_spacing = 1.4  # Line height multiplier
        self.paragraph_spacing = 10  # Extra space between paragraphs
        
        # Font settings - scaled by zoom factor
        base_font_size = 18
        self.font_size = int(base_font_size * zoom_factor)
        self.title_font_size = int(24 * zoom_factor)
        
        # Calculate text area
        self.text_width = width - self.margin_left - self.margin_right
        self.text_height = height - self.margin_top - self.margin_bottom
        
        # Load fonts
        self._load_fonts()
        
        # Book content
        self.book = None
        self.chapters = []  # List of chapter text content
        self.pages = []  # List of (text, is_chapter_start) for each page
        self.page_count = 0
        
        try:
            self._load_epub()
        except Exception as e:
            self.logger.error(f"Failed to load EPUB: {e}")
            raise

    def _load_fonts(self):
        """Load TrueType fonts for crisp text rendering"""
        # Font paths to try (in order of preference)
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        
        bold_font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
            "C:/Windows/Fonts/timesbd.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
        
        # Load main font
        self.font = None
        for path in font_paths:
            try:
                self.font = ImageFont.truetype(path, self.font_size)
                self.logger.info(f"Loaded font: {path}")
                break
            except:
                continue
        
        if self.font is None:
            self.logger.warning("No TrueType fonts found, using default")
            self.font = ImageFont.load_default()
        
        # Load bold/title font
        self.title_font = None
        for path in bold_font_paths:
            try:
                self.title_font = ImageFont.truetype(path, self.title_font_size)
                break
            except:
                continue
        
        if self.title_font is None:
            self.title_font = self.font

    def _load_epub(self):
        """Load and parse the EPUB file"""
        self.book = epub.read_epub(self.epub_path)
        
        # Extract text from all chapters
        self.chapters = []
        
        for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            try:
                html_content = item.get_content().decode('utf-8')
                text = self._html_to_text(html_content)
                if text.strip():
                    self.chapters.append({
                        'name': item.get_name(),
                        'text': text
                    })
            except Exception as e:
                self.logger.warning(f"Failed to process chapter: {e}")
        
        # Paginate all content
        self._paginate()
        
        self.logger.info(f"Loaded EPUB: {self.epub_path} ({len(self.chapters)} chapters, {self.page_count} pages)")

    def _html_to_text(self, html: str) -> str:
        """
        Convert HTML to clean plain text.
        Preserves paragraph structure for proper formatting.
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'head', 'meta', 'link']):
            element.decompose()
        
        # Process text with paragraph awareness
        paragraphs = []
        
        # Handle headings
        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            text = tag.get_text(strip=True)
            if text:
                paragraphs.append(f"\n### {text} ###\n")
        
        # Handle paragraphs
        for p in soup.find_all(['p', 'div']):
            text = p.get_text(separator=' ', strip=True)
            if text:
                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text)
                paragraphs.append(text)
        
        # If no paragraphs found, just get all text
        if not paragraphs:
            text = soup.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)
            paragraphs = [text]
        
        return '\n\n'.join(paragraphs)

    def _paginate(self):
        """
        Split all chapter text into pages that fit on screen.
        """
        self.pages = []
        
        # Calculate how many lines fit on a page
        try:
            # Get font metrics
            bbox = self.font.getbbox("Ay")  # Use chars with ascenders/descenders
            line_height = int((bbox[3] - bbox[1]) * self.line_spacing)
        except:
            line_height = int(self.font_size * self.line_spacing)
        
        lines_per_page = self.text_height // line_height
        
        # Calculate characters per line (approximate)
        try:
            avg_char_width = self.font.getlength("x")
        except:
            avg_char_width = self.font_size * 0.5
        
        chars_per_line = int(self.text_width / avg_char_width)
        
        self.logger.debug(f"Pagination: {lines_per_page} lines/page, ~{chars_per_line} chars/line")
        
        for chapter in self.chapters:
            text = chapter['text']
            paragraphs = text.split('\n\n')
            
            current_page_lines = []
            is_chapter_start = True
            
            for para in paragraphs:
                if not para.strip():
                    continue
                
                # Check if this is a heading
                is_heading = para.strip().startswith('###') and para.strip().endswith('###')
                if is_heading:
                    para = para.strip()[3:-3].strip()  # Remove ### markers
                
                # Wrap paragraph to fit width
                wrapped_lines = textwrap.wrap(para, width=chars_per_line)
                
                for line in wrapped_lines:
                    current_page_lines.append((line, is_heading))
                    is_heading = False  # Only first line of heading is bold
                    
                    # Check if page is full
                    if len(current_page_lines) >= lines_per_page:
                        self.pages.append({
                            'lines': current_page_lines,
                            'is_chapter_start': is_chapter_start
                        })
                        current_page_lines = []
                        is_chapter_start = False
                
                # Add paragraph spacing (as empty line)
                if current_page_lines:
                    current_page_lines.append(('', False))
            
            # Add remaining lines as final page of chapter
            if current_page_lines:
                self.pages.append({
                    'lines': current_page_lines,
                    'is_chapter_start': is_chapter_start
                })
        
        self.page_count = len(self.pages)
        if self.page_count == 0:
            self.page_count = 1  # At least one blank page

    def render_page(self, page_num: int, show_page_number: bool = True) -> Image.Image:
        """
        Render a page to a PIL Image using direct text drawing.

        Args:
            page_num: Page number (0-indexed)
            show_page_number: Whether to show page number overlay

        Returns:
            PIL Image in 1-bit mode for e-ink display
        """
        # Create white background (1-bit for e-ink)
        image = Image.new('1', (self.width, self.height), 1)  # 1 = white
        draw = ImageDraw.Draw(image)
        
        try:
            if page_num < 0 or page_num >= len(self.pages):
                # Blank page for out of range
                self.logger.warning(f"Page {page_num} out of range")
                return image
            
            page_data = self.pages[page_num]
            lines = page_data['lines']
            
            # Calculate line height
            try:
                bbox = self.font.getbbox("Ay")
                line_height = int((bbox[3] - bbox[1]) * self.line_spacing)
            except:
                line_height = int(self.font_size * self.line_spacing)
            
            # Draw each line
            y = self.margin_top
            for line_text, is_heading in lines:
                if not line_text:
                    # Empty line for paragraph spacing
                    y += self.paragraph_spacing
                    continue
                
                # Choose font based on heading status
                font = self.title_font if is_heading else self.font
                
                # Draw text (fill=0 is black on 1-bit image)
                draw.text((self.margin_left, y), line_text, font=font, fill=0)
                
                y += line_height
                
                # Stop if we've exceeded the text area
                if y > self.height - self.margin_bottom:
                    break
            
            # Draw page number
            if show_page_number:
                page_text = f"Page {page_num + 1} of {self.page_count}"
                try:
                    bbox = draw.textbbox((0, 0), page_text, font=self.font)
                    text_width = bbox[2] - bbox[0]
                    text_x = (self.width - text_width) // 2
                except:
                    text_x = self.width // 2 - 50
                
                draw.text((text_x, self.height - 25), page_text, font=self.font, fill=0)
            
            self.logger.debug(f"Rendered page {page_num + 1}/{self.page_count}")
            
        except Exception as e:
            self.logger.error(f"Failed to render page {page_num}: {e}")
            import traceback
            traceback.print_exc()
        
        return image

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
        self.book = None
        self.chapters = []
        self.pages = []

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.close()
