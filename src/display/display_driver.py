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

    def __init__(self, width: int = 800, height: int = 480, rotation: int = 0):
        """
        Initialize display driver

        Args:
            width: Display width in pixels (logical, after rotation)
            height: Display height in pixels (logical, after rotation)
            rotation: Rotation angle (0, 90, 180, 270)
        """
        self.width = width
        self.height = height
        self.rotation = rotation
        self.epd = None
        self.logger = logging.getLogger(__name__)
        self.partial_refresh_count = 0
        self.full_refresh_interval = 5  # Full refresh every N page turns
        
        # Physical hardware dimensions (always 800x480 for this display)
        self.hw_width = 800
        self.hw_height = 480
        
        # Track if partial refresh mode has been initialized
        self.partial_mode_initialized = False

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

    def display_image(self, image: Image.Image, use_partial: bool = True):
        """
        Display a PIL Image on the screen with partial or full refresh

        Args:
            image: PIL Image object (will be resized and rotated as needed)
            use_partial: Use partial refresh if True, full refresh if False
        """
        # Ensure image is correct size
        if image.size != (self.width, self.height):
            self.logger.warning(f"Resizing image from {image.size} to ({self.width}, {self.height})")
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)

        # Ensure image is 1-bit (black and white)
        if image.mode != '1':
            self.logger.debug(f"Converting image from {image.mode} to 1-bit")
            image = image.convert('1')

        # Apply rotation if needed (for portrait mode)
        if self.rotation != 0:
            # Rotate the image (negative angle for clockwise rotation in PIL)
            image = image.rotate(-self.rotation, expand=True)
            self.logger.debug(f"Rotated image by {self.rotation} degrees")

        if not self.hardware_available or not self.epd:
            # Mock mode - save image to file
            output_file = "output/display_output.png"
            os.makedirs("output", exist_ok=True)
            image.save(output_file)
            self.logger.info(f"Mock display: Image saved to {output_file}")
            return

        try:
            # Decide whether to use partial or full refresh
            should_full_refresh = not use_partial or (self.partial_refresh_count >= self.full_refresh_interval)

            if should_full_refresh:
                # Full refresh - clears ghosting
                self.logger.info(f"Performing FULL refresh (count reset from {self.partial_refresh_count})")
                
                # If we were in partial mode, reinitialize for full refresh
                # The display needs init() to properly do a full refresh after init_part()
                if self.partial_mode_initialized:
                    self.logger.info("Reinitializing display for full refresh mode")
                    self.epd.init()
                    self.partial_mode_initialized = False
                
                self.epd.display(self.epd.getbuffer(image))
                self.partial_refresh_count = 0
            else:
                # Partial refresh - faster but may cause ghosting
                buffer_data = self.epd.getbuffer(image)

                # Waveshare 7.5" V2 uses display_Partial(Image, Xstart, Ystart, Xend, Yend)
                # IMPORTANT: Use physical hardware dimensions, not logical rotated dimensions
                if hasattr(self.epd, 'display_Partial'):
                    try:
                        # Initialize partial refresh mode if not already done
                        # This is required for Waveshare 7.5" V2 - without init_part(),
                        # the display does a full refresh internally before partial update
                        if not self.partial_mode_initialized and hasattr(self.epd, 'init_part'):
                            self.logger.info("Initializing partial refresh mode (init_part)")
                            self.epd.init_part()
                            self.partial_mode_initialized = True
                        
                        # Full screen partial refresh with HARDWARE coordinates (always 800x480)
                        self.epd.display_Partial(buffer_data, 0, 0, self.hw_width, self.hw_height)
                        self.partial_refresh_count += 1
                        self.logger.info(f"PARTIAL refresh {self.partial_refresh_count}/{self.full_refresh_interval} (0.4s)")
                    except Exception as e:
                        self.logger.warning(f"Partial refresh failed: {e}, using full refresh")
                        self.epd.display(buffer_data)
                        self.partial_refresh_count = 0
                        self.partial_mode_initialized = False
                else:
                    # Fallback: try other method names
                    partial_method = None
                    if hasattr(self.epd, 'displayPartial'):
                        partial_method = self.epd.displayPartial
                    elif hasattr(self.epd, 'DisplayPartial'):
                        partial_method = self.epd.DisplayPartial

                    if partial_method:
                        try:
                            partial_method(buffer_data)
                            self.partial_refresh_count += 1
                            self.logger.info(f"PARTIAL refresh {self.partial_refresh_count}/{self.full_refresh_interval}")
                        except Exception as e:
                            self.logger.warning(f"Partial refresh failed: {e}, using full refresh")
                            self.epd.display(buffer_data)
                            self.partial_refresh_count = 0
                    else:
                        # Partial refresh not supported
                        self.logger.warning("Partial refresh not available on this display, using full refresh")
                        self.epd.display(buffer_data)

        except Exception as e:
            self.logger.error(f"Display image failed: {e}")
            raise

    def set_full_refresh_interval(self, interval: int):
        """
        Set how many partial refreshes before a full refresh

        Args:
            interval: Number of partial refreshes (e.g., 5 = full refresh every 5 page turns)
        """
        self.full_refresh_interval = max(1, interval)
        self.logger.info(f"Full refresh interval set to {self.full_refresh_interval}")

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
