class ShutdownScreen:
    """
    Shutdown confirmation screen
    Displays a large "OFF" message before system shutdown
    """

    def __init__(self, width: int = 800, height: int = 480):
        """
        Initialize shutdown screen

        Args:
            width: Screen width
            height: Screen height
        """
        self.width = width
        self.height = height
        try:
            # Use Serif-Bold as it is known to exist from MainMenuScreen
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 120)
        except:
            self.font = ImageFont.load_default()

    def render(self) -> Image.Image:
        """
        Render shutdown screen

        Returns:
            PIL Image (1-bit, for e-ink display)
        """
        # Create image with WHITE background (1)
        image = Image.new('1', (self.width, self.height), 1)
        draw = ImageDraw.Draw(image)

        # Draw thick outer black border (20px)
        draw.rectangle([(0, 0), (self.width-1, self.height-1)], outline=0, width=20)
        
        # Draw inner black border (10px) for extra visibility
        draw.rectangle([(30, 30), (self.width-30, self.height-30)], outline=0, width=10)

        text = "SHUTTING\nDOWN"
        try:
            bbox = draw.textbbox((0, 0), text, font=self.font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            text_width = len(text) * 60
            text_height = 120

        x = (self.width - text_width) // 2
        y = (self.height - text_height) // 2

        # Draw text in BLACK (0)
        draw.multiline_text((x, y), text, font=self.font, fill=0, align="center")

        return image
