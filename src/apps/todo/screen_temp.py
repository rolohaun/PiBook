class ToDoScreen:
    """
    To Do list screen for managing tasks
    """

    def __init__(self, width: int = 800, height: int = 480, font_size: int = 18, battery_monitor=None):
        """
        Initialize To Do screen

        Args:
            width: Screen width
            height: Screen height
            font_size: Base font size
            battery_monitor: Optional BatteryMonitor instance
        """
        self.width = width
        self.height = height
        self.font_size = font_size
        self.battery_monitor = battery_monitor
        self.logger = logging.getLogger(__name__)

        # Load fonts
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", font_size)
            self.title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 28)
            self.item_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 32)  # Doubled from 16
        except:
            self.font = ImageFont.load_default()
            self.title_font = ImageFont.load_default()
            self.item_font = ImageFont.load_default()

        # To do items: list of dicts with 'text' and 'completed' keys
        self.todos: List[Dict[str, Any]] = []
        self.current_index = 0  # Currently selected item
        self.items_per_page = 8  # Reduced from 15 for larger font
        self.current_page = 0

        # Load todos from file (same location as web server)
        self.todos_file = "todos.json"
        self._load_todos()

    def _load_todos(self):
        """Load todos from JSON file"""
        import os
        import json

        if os.path.exists(self.todos_file):
            try:
                with open(self.todos_file, 'r') as f:
                    data = json.load(f)
                    # Extract tasks array from JSON structure
                    self.todos = data.get('tasks', [])
                self.logger.info(f"Loaded {len(self.todos)} todos from {self.todos_file}")
            except Exception as e:
                self.logger.error(f"Failed to load todos: {e}")
                self.todos = []
        else:
            self.logger.info("No todos file found, starting with empty list")
            self.todos = []

    def _save_todos(self):
        """Save todos to JSON file"""
        import os
        import json

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.todos_file), exist_ok=True)

        try:
            with open(self.todos_file, 'w') as f:
                json.dump({'tasks': self.todos}, f, indent=2)
            self.logger.info(f"Saved {len(self.todos)} todos to {self.todos_file}")
        except Exception as e:
            self.logger.error(f"Failed to save todos: {e}")

    def _draw_battery_icon(self, draw: ImageDraw.Draw, x: int, y: int, percentage: int, is_charging: bool = False):
        """
        Draw battery icon with percentage and charging indicator

        Args:
            draw: ImageDraw object
            x: X position (top-right corner)
            y: Y position
            percentage: Battery percentage (0-100)
            is_charging: Whether battery is currently charging
        """
        self.logger.debug(f"Drawing battery icon: {percentage}% charging={is_charging}")
        
        # Battery dimensions
        battery_width = 30
        battery_height = 14
        terminal_width = 2
        terminal_height = 6

        # Draw battery outline
        battery_x = x - battery_width
        draw.rectangle(
            [(battery_x, y), (battery_x + battery_width, y + battery_height)],
            outline='black',
            width=1
        )

        # Draw battery terminal (positive end)
        terminal_x = battery_x + battery_width
        terminal_y = y + (battery_height - terminal_height) // 2
        draw.rectangle(
            [(terminal_x, terminal_y), (terminal_x + terminal_width, terminal_y + terminal_height)],
            fill='black'
        )

        # Draw battery fill based on percentage
        fill_width = int((battery_width - 4) * (percentage / 100))
        if fill_width > 0:
            draw.rectangle(
                [(battery_x + 2, y + 2), (battery_x + 2 + fill_width, y + battery_height - 2)],
                fill='black'
            )

        # Draw charging indicator (lightning bolt) if charging
        if is_charging:
            bolt_center_x = battery_x + battery_width // 2
            bolt_center_y = y + battery_height // 2
            # Larger, more visible lightning bolt
            bolt_points = [
                (bolt_center_x + 2, bolt_center_y - 6),    # Top tip
                (bolt_center_x - 2, bolt_center_y - 1),    # Upper left
                (bolt_center_x + 3, bolt_center_y - 1),    # Upper right
                (bolt_center_x - 2, bolt_center_y + 6),    # Bottom tip
                (bolt_center_x + 2, bolt_center_y + 1),    # Lower right
                (bolt_center_x - 3, bolt_center_y + 1),    # Lower left
            ]
            # Draw white bolt so it's visible against battery fill
            draw.polygon(bolt_points, fill='white', outline='black')

        # Draw percentage text
        percentage_text = f"{percentage}%"
        try:
            bbox = draw.textbbox((0, 0), percentage_text, font=self.font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(percentage_text) * 8

        text_x = battery_x - text_width - 5
        draw.text((text_x, y), percentage_text, font=self.font, fill='black')

    def add_todo(self, text: str):
        """Add a new todo item"""
        self.todos.append({
            'text': text,
            'completed': False
        })
        self._save_todos()
        self.logger.info(f"Added todo: {text}")

    def toggle_todo(self):
        """Toggle completion status of current todo"""
        if 0 <= self.current_index < len(self.todos):
            self.todos[self.current_index]['completed'] = not self.todos[self.current_index]['completed']
            self._save_todos()
            status = "completed" if self.todos[self.current_index]['completed'] else "uncompleted"
            self.logger.info(f"Marked todo as {status}: {self.todos[self.current_index]['text']}")

    def delete_todo(self):
        """Delete current todo item"""
        if 0 <= self.current_index < len(self.todos):
            deleted = self.todos.pop(self.current_index)
            self._save_todos()
            # Adjust current index if needed
            if self.current_index >= len(self.todos) and len(self.todos) > 0:
                self.current_index = len(self.todos) - 1
            self.logger.info(f"Deleted todo: {deleted['text']}")

    def next_item(self):
        """Move to next todo item"""
        if len(self.todos) > 0:
            self.current_index = (self.current_index + 1) % len(self.todos)
            # Update page if needed
            self.current_page = self.current_index // self.items_per_page

    def prev_item(self):
        """Move to previous todo item"""
        if len(self.todos) > 0:
            self.current_index = (self.current_index - 1) % len(self.todos)
            # Update page if needed
            self.current_page = self.current_index // self.items_per_page

    def render(self) -> Image.Image:
        """
        Render the To Do screen

        Returns:
            PIL Image of the screen
        """
        # Reload todos from file to get latest changes
        self._load_todos()
        
        # Create blank image (white background)
        image = Image.new('RGB', (self.width, self.height), 'white')
        draw = ImageDraw.Draw(image)

        y_offset = 10

        # Draw title
        title = "To Do List"
        title_bbox = draw.textbbox((0, 0), title, font=self.title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.width - title_width) // 2
        draw.text((title_x, y_offset), title, fill='black', font=self.title_font)
        y_offset += 40

        # Draw battery status if available (top right corner)
        if self.battery_monitor:
            try:
                battery_pct = self.battery_monitor.get_percentage()
                charging = self.battery_monitor.is_charging()
                # Use drawn battery icon instead of emoji (emojis show as boxes on e-ink)
                self._draw_battery_icon(draw, self.width - 10, 10, battery_pct, charging)
            except Exception as e:
                self.logger.warning(f"Failed to get battery status: {e}")

        # Draw separator line
        draw.line([(10, y_offset), (self.width - 10, y_offset)], fill='black', width=2)
        y_offset += 10

        # If no todos, show message
        if len(self.todos) == 0:
            msg = "No tasks yet"
            msg_bbox = draw.textbbox((0, 0), msg, font=self.font)
            msg_width = msg_bbox[2] - msg_bbox[0]
            draw.text(((self.width - msg_width) // 2, self.height // 2), msg, fill='gray', font=self.font)
        else:
            # Draw todo items
            line_height = 40  # Increased from 24 for larger font
            start_idx = self.current_page * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.todos))

            for i in range(start_idx, end_idx):
                todo = self.todos[i]

                # Highlight current selection
                if i == self.current_index:
                    # Draw selection background
                    draw.rectangle(
                        [(10, y_offset - 2), (self.width - 10, y_offset + line_height - 2)],
                        fill='lightgray'
                    )

                # Draw checkbox - centered with text line
                checkbox_x = 20
                checkbox_size = 24  # Increased from 16 for better visibility
                # Center checkbox vertically with text
                text_bbox_temp = draw.textbbox((0, 0), "A", font=self.item_font)
                text_height = text_bbox_temp[3] - text_bbox_temp[1]
                checkbox_y = y_offset + (text_height - checkbox_size) // 2
                
                draw.rectangle(
                    [(checkbox_x, checkbox_y), (checkbox_x + checkbox_size, checkbox_y + checkbox_size)],
                    outline='black',
                    width=2
                )

                # Draw X if completed
                if todo['completed']:
                    # Draw X in checkbox
                    draw.line([(checkbox_x + 4, checkbox_y + 4), (checkbox_x + checkbox_size - 4, checkbox_y + checkbox_size - 4)], fill='black', width=3)
                    draw.line([(checkbox_x + checkbox_size - 4, checkbox_y + 4), (checkbox_x + 4, checkbox_y + checkbox_size - 4)], fill='black', width=3)

                # Draw todo text - multi-line word wrap
                text_x = checkbox_x + checkbox_size + 10
                text_color = 'black'
                max_width = self.width - text_x - 20
                max_lines = 3  # Maximum lines per task
                
                # Word wrap implementation
                text = todo['text']
                words = text.split()
                lines = []
                current_line = []
                
                for word in words:
                    # Test if adding this word would exceed max width
                    test_line = ' '.join(current_line + [word])
                    test_bbox = draw.textbbox((0, 0), test_line, font=self.item_font)
                    test_width = test_bbox[2] - test_bbox[0]
                    
                    if test_width <= max_width:
                        current_line.append(word)
                    else:
                        # Save current line if it has content
                        if current_line:
                            lines.append(' '.join(current_line))
                            current_line = [word]
                        else:
                            # Single word is too long, truncate it
                            truncated = word
                            while len(truncated) > 0:
                                test_word = truncated + "..."
                                test_bbox = draw.textbbox((0, 0), test_word, font=self.item_font)
                                if test_bbox[2] - test_bbox[0] <= max_width:
                                    lines.append(test_word)
                                    break
                                truncated = truncated[:-1]
                            current_line = []
                        
                        # Stop if we've reached max lines
                        if len(lines) >= max_lines:
                            break
                
                # Add remaining words if we haven't hit max lines
                if current_line and len(lines) < max_lines:
                    lines.append(' '.join(current_line))
                
                # Limit to max_lines and add ellipsis if truncated
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    lines[-1] = lines[-1] + "..."
                
                # Draw each line
                line_spacing = 36  # Spacing between lines
                current_y = y_offset
                
                for i, line_text in enumerate(lines):
                    draw.text((text_x, current_y), line_text, fill=text_color, font=self.item_font)
                    
                    # Add strikethrough if completed (on all lines)
                    if todo['completed']:
                        text_bbox = draw.textbbox((text_x, current_y), line_text, font=self.item_font)
                        text_height = text_bbox[3] - text_bbox[1]
                        strike_y = current_y + text_height // 2
                        draw.line([(text_x, strike_y), (text_bbox[2], strike_y)], fill='black', width=4)
                    
                    current_y += line_spacing

                # Adjust y_offset based on number of lines drawn
                y_offset += max(line_height, len(lines) * line_spacing)

            # Draw page indicator if multiple pages
            total_pages = (len(self.todos) + self.items_per_page - 1) // self.items_per_page
            if total_pages > 1:
                page_info = f"Page {self.current_page + 1}/{total_pages}"
                page_bbox = draw.textbbox((0, 0), page_info, font=self.item_font)
                page_width = page_bbox[2] - page_bbox[0]
                draw.text(
                    ((self.width - page_width) // 2, self.height - 30),
                    page_info,
                    fill='black',
                    font=self.item_font
                )

        # Draw help text at bottom
        help_text = "Hold GPIO5: Return to Menu"
        # Use smaller font for help text
        try:
            help_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 18)
        except:
            help_font = self.item_font
        help_bbox = draw.textbbox((0, 0), help_text, font=help_font)
        help_width = help_bbox[2] - help_bbox[0]
        help_height = help_bbox[3] - help_bbox[1]
        draw.text(
            ((self.width - help_width) // 2, self.height - help_height - 15),
            help_text,
            fill='gray',
            font=help_font
        )

        return image
