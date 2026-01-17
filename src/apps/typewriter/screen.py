"""
Typewriter App - Terminal and Word Processor for PiBook

Features:
- Two tabs: Terminal and Word Processor
- Alt key switches between tabs
- Terminal executes shell commands on the Raspberry Pi
- Word Processor is a distraction-free writing environment
"""

import logging
import os
import subprocess
import json
from typing import Optional, List, Tuple
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime


class TypewriterScreen:
    """
    Typewriter app with terminal and word processor tabs
    """

    # Tab modes
    MODE_TERMINAL = 0
    MODE_WORDPROC = 1

    def __init__(self, width: int = 800, height: int = 480, font_size: int = 16, battery_monitor=None):
        """
        Initialize Typewriter screen

        Args:
            width: Screen width
            height: Screen height
            font_size: Base font size for text
            battery_monitor: Optional BatteryMonitor instance
        """
        self.width = width
        self.height = height
        self.font_size = font_size
        self.battery_monitor = battery_monitor
        self.logger = logging.getLogger(__name__)

        # Current mode (terminal or word processor)
        self.current_mode = self.MODE_TERMINAL

        # Load fonts - use monospace for terminal/typing
        try:
            self.mono_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
            self.mono_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", font_size)
            self.title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            self.small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            self.mono_font = ImageFont.load_default()
            self.mono_bold = ImageFont.load_default()
            self.title_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()

        # Calculate character dimensions for layout
        try:
            bbox = self.mono_font.getbbox("M")
            self.char_width = bbox[2] - bbox[0]
            self.char_height = bbox[3] - bbox[1] + 4  # Add line spacing
        except:
            self.char_width = 10
            self.char_height = 18

        # Terminal state
        self.terminal_input = ""
        self.terminal_history: List[Tuple[str, str]] = []  # List of (command, output) tuples
        self.terminal_scroll = 0
        self.current_dir = os.path.expanduser("~")

        # Word processor state
        self.document_lines: List[str] = [""]  # Start with one empty line
        self.cursor_line = 0
        self.cursor_col = 0
        self.wp_scroll = 0  # Scroll offset for word processor
        self.document_path = os.path.expanduser("~/PiBook/data/documents")
        self.current_document = None

        # Ensure documents directory exists
        os.makedirs(self.document_path, exist_ok=True)

        # Calculate visible lines for each mode
        self.header_height = 50
        self.footer_height = 30
        self.content_height = height - self.header_height - self.footer_height
        self.visible_lines = self.content_height // self.char_height

        # Character width for wrapping
        self.margin = 20
        self.content_width = width - (self.margin * 2)
        self.chars_per_line = self.content_width // self.char_width

        self.logger.info(f"TypewriterScreen initialized: {self.chars_per_line} chars/line, {self.visible_lines} lines visible")

    def toggle_mode(self):
        """Switch between terminal and word processor modes"""
        if self.current_mode == self.MODE_TERMINAL:
            self.current_mode = self.MODE_WORDPROC
            self.logger.info("Switched to Word Processor mode")
        else:
            self.current_mode = self.MODE_TERMINAL
            self.logger.info("Switched to Terminal mode")

    # ==================== Terminal Methods ====================

    def terminal_type_char(self, char: str):
        """Add a character to terminal input"""
        self.terminal_input += char

    def terminal_backspace(self):
        """Remove last character from terminal input"""
        if self.terminal_input:
            self.terminal_input = self.terminal_input[:-1]

    def terminal_execute(self):
        """Execute the current terminal command"""
        if not self.terminal_input.strip():
            return

        command = self.terminal_input.strip()
        self.terminal_input = ""

        # Handle built-in commands
        if command == "clear":
            self.terminal_history = []
            return

        if command.startswith("cd "):
            new_dir = command[3:].strip()
            if new_dir == "~":
                new_dir = os.path.expanduser("~")
            elif not new_dir.startswith("/"):
                new_dir = os.path.join(self.current_dir, new_dir)

            if os.path.isdir(new_dir):
                self.current_dir = os.path.abspath(new_dir)
                self.terminal_history.append((command, f"Changed to {self.current_dir}"))
            else:
                self.terminal_history.append((command, f"Directory not found: {new_dir}"))
            return

        # Execute shell command
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.current_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            if not output:
                output = "(no output)"
        except subprocess.TimeoutExpired:
            output = "Command timed out (30s limit)"
        except Exception as e:
            output = f"Error: {str(e)}"

        self.terminal_history.append((command, output.strip()))

        # Scroll to bottom
        self._terminal_scroll_to_bottom()

        self.logger.info(f"Terminal executed: {command}")

    def _terminal_scroll_to_bottom(self):
        """Scroll terminal to show latest output"""
        total_lines = self._count_terminal_lines()
        if total_lines > self.visible_lines:
            self.terminal_scroll = total_lines - self.visible_lines

    def _count_terminal_lines(self) -> int:
        """Count total lines in terminal history"""
        count = 0
        for cmd, output in self.terminal_history:
            count += 1  # Command prompt line
            output_lines = output.split('\n')
            for line in output_lines:
                count += (len(line) // self.chars_per_line) + 1
        count += 1  # Current input line
        return count

    def terminal_scroll_up(self):
        """Scroll terminal output up"""
        if self.terminal_scroll > 0:
            self.terminal_scroll -= 1

    def terminal_scroll_down(self):
        """Scroll terminal output down"""
        total_lines = self._count_terminal_lines()
        if self.terminal_scroll < total_lines - self.visible_lines:
            self.terminal_scroll += 1

    # ==================== Word Processor Methods ====================

    def wp_type_char(self, char: str):
        """Add a character at cursor position in word processor"""
        line = self.document_lines[self.cursor_line]
        new_line = line[:self.cursor_col] + char + line[self.cursor_col:]
        self.document_lines[self.cursor_line] = new_line
        self.cursor_col += 1

    def wp_backspace(self):
        """Handle backspace in word processor"""
        if self.cursor_col > 0:
            # Delete character before cursor
            line = self.document_lines[self.cursor_line]
            self.document_lines[self.cursor_line] = line[:self.cursor_col-1] + line[self.cursor_col:]
            self.cursor_col -= 1
        elif self.cursor_line > 0:
            # Join with previous line
            prev_line = self.document_lines[self.cursor_line - 1]
            curr_line = self.document_lines[self.cursor_line]
            self.cursor_col = len(prev_line)
            self.document_lines[self.cursor_line - 1] = prev_line + curr_line
            del self.document_lines[self.cursor_line]
            self.cursor_line -= 1
            self._ensure_cursor_visible()

    def wp_enter(self):
        """Handle enter key in word processor"""
        line = self.document_lines[self.cursor_line]
        # Split line at cursor
        self.document_lines[self.cursor_line] = line[:self.cursor_col]
        self.document_lines.insert(self.cursor_line + 1, line[self.cursor_col:])
        self.cursor_line += 1
        self.cursor_col = 0
        self._ensure_cursor_visible()

    def wp_move_up(self):
        """Move cursor up one line"""
        if self.cursor_line > 0:
            self.cursor_line -= 1
            self.cursor_col = min(self.cursor_col, len(self.document_lines[self.cursor_line]))
            self._ensure_cursor_visible()

    def wp_move_down(self):
        """Move cursor down one line"""
        if self.cursor_line < len(self.document_lines) - 1:
            self.cursor_line += 1
            self.cursor_col = min(self.cursor_col, len(self.document_lines[self.cursor_line]))
            self._ensure_cursor_visible()

    def wp_move_left(self):
        """Move cursor left"""
        if self.cursor_col > 0:
            self.cursor_col -= 1
        elif self.cursor_line > 0:
            self.cursor_line -= 1
            self.cursor_col = len(self.document_lines[self.cursor_line])
            self._ensure_cursor_visible()

    def wp_move_right(self):
        """Move cursor right"""
        line = self.document_lines[self.cursor_line]
        if self.cursor_col < len(line):
            self.cursor_col += 1
        elif self.cursor_line < len(self.document_lines) - 1:
            self.cursor_line += 1
            self.cursor_col = 0
            self._ensure_cursor_visible()

    def _ensure_cursor_visible(self):
        """Ensure cursor line is visible on screen"""
        if self.cursor_line < self.wp_scroll:
            self.wp_scroll = self.cursor_line
        elif self.cursor_line >= self.wp_scroll + self.visible_lines:
            self.wp_scroll = self.cursor_line - self.visible_lines + 1

    def wp_save(self):
        """Save current document"""
        if not self.current_document:
            # Generate filename from timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_document = f"document_{timestamp}.txt"

        filepath = os.path.join(self.document_path, self.current_document)
        try:
            with open(filepath, 'w') as f:
                f.write('\n'.join(self.document_lines))
            self.logger.info(f"Document saved: {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save document: {e}")
            return False

    def wp_new(self):
        """Create new document"""
        self.document_lines = [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self.wp_scroll = 0
        self.current_document = None
        self.logger.info("New document created")

    def wp_get_word_count(self) -> int:
        """Get word count of current document"""
        text = '\n'.join(self.document_lines)
        words = text.split()
        return len(words)

    # ==================== Unified Input Handling ====================

    def handle_key(self, key_code: int, char: Optional[str] = None, modifiers: dict = None):
        """
        Handle keyboard input

        Args:
            key_code: evdev key code
            char: Character if printable
            modifiers: Dict with 'shift', 'ctrl', 'alt' boolean flags
        """
        modifiers = modifiers or {}

        # Alt key switches modes
        if modifiers.get('alt'):
            self.toggle_mode()
            return

        if self.current_mode == self.MODE_TERMINAL:
            self._handle_terminal_key(key_code, char, modifiers)
        else:
            self._handle_wp_key(key_code, char, modifiers)

    def _handle_terminal_key(self, key_code: int, char: Optional[str], modifiers: dict):
        """Handle key press in terminal mode"""
        # Import evdev codes if available
        try:
            from evdev import ecodes

            if key_code == ecodes.KEY_ENTER:
                self.terminal_execute()
            elif key_code == ecodes.KEY_BACKSPACE:
                self.terminal_backspace()
            elif key_code == ecodes.KEY_UP:
                self.terminal_scroll_up()
            elif key_code == ecodes.KEY_DOWN:
                self.terminal_scroll_down()
            elif char and char.isprintable():
                self.terminal_type_char(char)
        except ImportError:
            # Fallback for when evdev isn't available (testing)
            if char and char.isprintable():
                self.terminal_type_char(char)

    def _handle_wp_key(self, key_code: int, char: Optional[str], modifiers: dict):
        """Handle key press in word processor mode"""
        try:
            from evdev import ecodes

            # Ctrl+S to save
            if modifiers.get('ctrl') and key_code == ecodes.KEY_S:
                self.wp_save()
                return

            # Ctrl+N for new document
            if modifiers.get('ctrl') and key_code == ecodes.KEY_N:
                self.wp_new()
                return

            if key_code == ecodes.KEY_ENTER:
                self.wp_enter()
            elif key_code == ecodes.KEY_BACKSPACE:
                self.wp_backspace()
            elif key_code == ecodes.KEY_UP:
                self.wp_move_up()
            elif key_code == ecodes.KEY_DOWN:
                self.wp_move_down()
            elif key_code == ecodes.KEY_LEFT:
                self.wp_move_left()
            elif key_code == ecodes.KEY_RIGHT:
                self.wp_move_right()
            elif char and char.isprintable():
                self.wp_type_char(char)
        except ImportError:
            if char and char.isprintable():
                self.wp_type_char(char)

    # ==================== Rendering ====================

    def _draw_battery_icon(self, draw: ImageDraw.Draw, x: int, y: int, percentage: int, is_charging: bool = False):
        """Draw battery icon with percentage (1-bit: 0=black, 1=white)"""
        battery_width = 30
        battery_height = 14
        terminal_width = 2
        terminal_height = 6

        battery_x = x - battery_width
        draw.rectangle(
            [(battery_x, y), (battery_x + battery_width, y + battery_height)],
            outline=0, width=1
        )

        terminal_x = battery_x + battery_width
        terminal_y = y + (battery_height - terminal_height) // 2
        draw.rectangle(
            [(terminal_x, terminal_y), (terminal_x + terminal_width, terminal_y + terminal_height)],
            fill=0
        )

        fill_width = int((battery_width - 4) * (percentage / 100))
        if fill_width > 0:
            draw.rectangle(
                [(battery_x + 2, y + 2), (battery_x + 2 + fill_width, y + battery_height - 2)],
                fill=0
            )

        if is_charging:
            bolt_center_x = battery_x + battery_width // 2
            bolt_center_y = y + battery_height // 2
            bolt_points = [
                (bolt_center_x + 2, bolt_center_y - 6),
                (bolt_center_x - 2, bolt_center_y - 1),
                (bolt_center_x + 3, bolt_center_y - 1),
                (bolt_center_x - 2, bolt_center_y + 6),
                (bolt_center_x + 2, bolt_center_y + 1),
                (bolt_center_x - 3, bolt_center_y + 1),
            ]
            draw.polygon(bolt_points, fill=1, outline=0)

        percentage_text = f"{percentage}%"
        try:
            bbox = draw.textbbox((0, 0), percentage_text, font=self.small_font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(percentage_text) * 8

        text_x = battery_x - text_width - 5
        draw.text((text_x, y), percentage_text, font=self.small_font, fill=0)

    def _render_header(self, draw: ImageDraw.Draw):
        """Render header with tabs and battery"""
        # Draw tab bar background (1-bit: 0=black, 1=white)
        draw.rectangle([(0, 0), (self.width, self.header_height - 5)], fill=1)

        # Draw tabs
        tab_width = 150
        tab_height = 35
        tab_y = 8

        # Terminal tab
        term_x = 20
        if self.current_mode == self.MODE_TERMINAL:
            draw.rectangle([(term_x, tab_y), (term_x + tab_width, tab_y + tab_height)],
                          fill=1, outline=0, width=2)
        else:
            draw.rectangle([(term_x, tab_y), (term_x + tab_width, tab_y + tab_height)],
                          fill=1, outline=0, width=1)
        draw.text((term_x + 30, tab_y + 8), "Terminal", font=self.title_font, fill=0)

        # Word Processor tab
        wp_x = term_x + tab_width + 10
        if self.current_mode == self.MODE_WORDPROC:
            draw.rectangle([(wp_x, tab_y), (wp_x + tab_width, tab_y + tab_height)],
                          fill=1, outline=0, width=2)
        else:
            draw.rectangle([(wp_x, tab_y), (wp_x + tab_width, tab_y + tab_height)],
                          fill=1, outline=0, width=1)
        draw.text((wp_x + 15, tab_y + 8), "Word Proc", font=self.title_font, fill=0)

        # Battery icon
        if self.battery_monitor:
            try:
                pct = self.battery_monitor.get_percentage()
                charging = self.battery_monitor.is_charging()
                self._draw_battery_icon(draw, self.width - 10, 10, pct, charging)
            except:
                pass

        # Separator line
        draw.line([(0, self.header_height - 1), (self.width, self.header_height - 1)],
                 fill=0, width=1)

    def _render_footer(self, draw: ImageDraw.Draw):
        """Render footer with help text"""
        footer_y = self.height - self.footer_height

        # Separator line
        draw.line([(0, footer_y), (self.width, footer_y)], fill=0, width=1)

        if self.current_mode == self.MODE_TERMINAL:
            help_text = "Alt: Switch Tab | Enter: Execute | Esc: Main Menu"
        else:
            word_count = self.wp_get_word_count()
            help_text = f"Alt: Switch Tab | Ctrl+S: Save | Words: {word_count} | Esc: Menu"

        draw.text((self.margin, footer_y + 8), help_text, font=self.small_font, fill=0)

    def _render_terminal(self, draw: ImageDraw.Draw):
        """Render terminal content"""
        y = self.header_height + 5
        line_num = 0

        # Build all lines
        all_lines = []
        for cmd, output in self.terminal_history:
            # Prompt line
            prompt = f"{os.path.basename(self.current_dir)}$ {cmd}"
            all_lines.append(('prompt', prompt))

            # Output lines (wrap long lines)
            for out_line in output.split('\n'):
                while len(out_line) > self.chars_per_line:
                    all_lines.append(('output', out_line[:self.chars_per_line]))
                    out_line = out_line[self.chars_per_line:]
                all_lines.append(('output', out_line))

        # Current input line
        prompt = f"{os.path.basename(self.current_dir)}$ {self.terminal_input}_"
        all_lines.append(('input', prompt))

        # Render visible lines
        start_line = self.terminal_scroll
        end_line = min(start_line + self.visible_lines, len(all_lines))

        for i in range(start_line, end_line):
            line_type, text = all_lines[i]

            if line_type == 'prompt':
                draw.text((self.margin, y), text, font=self.mono_bold, fill=0)
            elif line_type == 'input':
                draw.text((self.margin, y), text, font=self.mono_bold, fill=0)
            else:
                draw.text((self.margin, y), text, font=self.mono_font, fill=0)

            y += self.char_height

    def _render_wordproc(self, draw: ImageDraw.Draw):
        """Render word processor content"""
        y = self.header_height + 5

        # Render visible lines
        start_line = self.wp_scroll
        end_line = min(start_line + self.visible_lines, len(self.document_lines))

        for i in range(start_line, end_line):
            line = self.document_lines[i]

            # Draw cursor if on this line
            if i == self.cursor_line:
                # Insert cursor character
                display_line = line[:self.cursor_col] + "|" + line[self.cursor_col:]
                draw.text((self.margin, y), display_line, font=self.mono_font, fill=0)
            else:
                draw.text((self.margin, y), line if line else " ", font=self.mono_font, fill=0)

            y += self.char_height

        # Show document name if exists
        if self.current_document:
            doc_text = f"[{self.current_document}]"
            try:
                bbox = draw.textbbox((0, 0), doc_text, font=self.small_font)
                text_width = bbox[2] - bbox[0]
            except:
                text_width = len(doc_text) * 8
            draw.text((self.width - text_width - self.margin, self.header_height + 5),
                     doc_text, font=self.small_font, fill=0)

    def render(self) -> Image.Image:
        """
        Render the typewriter screen

        Returns:
            PIL Image of the screen (1-bit for fast partial refresh)
        """
        # Create 1-bit image for fast partial refresh on e-ink
        image = Image.new('1', (self.width, self.height), 1)  # 1 = white
        draw = ImageDraw.Draw(image)

        # Render components
        self._render_header(draw)

        if self.current_mode == self.MODE_TERMINAL:
            self._render_terminal(draw)
        else:
            self._render_wordproc(draw)

        self._render_footer(draw)

        return image
