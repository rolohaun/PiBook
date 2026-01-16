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
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
        except:
            self.font = ImageFont.load_default()

    def render(self) -> Image.Image:
        """
        Render shutdown screen

        Returns:
            PIL Image (1-bit, for e-ink display)
        """
        image = Image.new('1', (self.width, self.height), 1)  # White background
        draw = ImageDraw.Draw(image)

        text = "OFF"
        try:
            bbox = draw.textbbox((0, 0), text, font=self.font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            text_width = len(text) * 60
            text_height = 80

        x = (self.width - text_width) // 2
        y = (self.height - text_height) // 2

        draw.text((x, y), text, font=self.font, fill=0)  # Black text

        return image
