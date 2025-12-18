"""
E-ink display driver abstraction for Waveshare 7.5" e-Paper HAT.
PORTABILITY: 100% portable - SPI interface identical on Pi 3B+ and Pi Zero 2 W
"""

import sys
import os
from PIL import Image
import logging

# Add Waveshare library to path
LIB_PATH = os.path.join(os.path.dirname(__file__), '../../lib')
if os.path.exists(LIB_PATH):
    sys.path.insert(0, LIB_PATH)


class DisplayDriver:
    """
    Hardware abstraction for Waveshare 7.5" e-Paper HAT (800x480)
    """

    def __init__(self, width: int = 800, height: int = 480):
        """
        Initialize display driver

        Args:
            width: Display width in pixels
            height: Display height in pixels
        """
        self.width = width
        self.height = height
        self.epd = None
        self.logger = logging.getLogger(__name__)

        # Try to import Waveshare library
        try:
            from waveshare_epd import epd7in5_V2
            self.epd_module = epd7in5_V2
            self.hardware_available = True
            self.logger.info("Using Waveshare 7.5inch V2 driver (800x480)")
        except ImportError:
            self.logger.warning("Waveshare V2 library not found. Running in mock mode.")
            self.hardware_available = False

    def initialize(self):
        """Initialize the display hardware"""
        if not self.hardware_available:
            self.logger.info("Mock display initialized (no hardware)")
            return

        try:
            self.epd = self.epd_module.EPD()
            self.epd.init()
            self.logger.info("E-ink display initialized successfully")
        except Exception as e:
            self.logger.error(f"Display initialization failed: {e}")
            raise

    def clear(self):
        """Clear the display to white"""
        if not self.hardware_available or not self.epd:
            self.logger.debug("Mock clear")
            return

        try:
            self.epd.Clear()
            self.logger.info("Display cleared")
        except Exception as e:
            self.logger.error(f"Display clear failed: {e}")

    def display_image(self, image: Image.Image):
        """
        Display a PIL Image on the screen

        Args:
            image: PIL Image object (will be resized to 800x480 and converted to 1-bit)
        """
        # Ensure image is correct size
        if image.size != (self.width, self.height):
            self.logger.warning(f"Resizing image from {image.size} to ({self.width}, {self.height})")
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)

        # Ensure image is 1-bit (black and white)
        if image.mode != '1':
            self.logger.debug(f"Converting image from {image.mode} to 1-bit")
            image = image.convert('1')

        if not self.hardware_available or not self.epd:
            # Mock mode - save image to file
            output_file = "output/display_output.png"
            os.makedirs("output", exist_ok=True)
            image.save(output_file)
            self.logger.info(f"Mock display: Image saved to {output_file}")
            return

        try:
            self.epd.display(self.epd.getbuffer(image))
            self.logger.info("Image displayed on e-ink screen")
        except Exception as e:
            self.logger.error(f"Display image failed: {e}")
            raise

    def sleep(self):
        """Put display into low-power sleep mode"""
        if not self.hardware_available or not self.epd:
            self.logger.debug("Mock sleep")
            return

        try:
            self.epd.sleep()
            self.logger.info("Display entered sleep mode")
        except Exception as e:
            self.logger.error(f"Display sleep failed: {e}")

    def cleanup(self):
        """Clean up resources and put display to sleep"""
        if not self.hardware_available or not self.epd:
            self.logger.debug("Mock cleanup")
            return

        try:
            self.epd.sleep()
            self.logger.info("Display cleaned up")
        except Exception as e:
            self.logger.error(f"Display cleanup failed: {e}")
