"""
Power Management Module
Handles CPU core management, sleep mode, and power optimization
"""

import os
import time
import logging
import subprocess
from PIL import Image, ImageDraw, ImageFont


class PowerManager:
    """Manages power-related functionality for battery optimization"""
    
    def __init__(self, config, display, logger=None):
        """
        Initialize power manager
        
        Args:
            config: Config instance
            display: DisplayDriver instance
            logger: Logger instance (optional)
        """
        self.config = config
        self.display = display
        self.logger = logger or logging.getLogger(__name__)
        
        # Sleep mode state
        self.is_sleeping = False
        self.last_activity_time = time.time()
        self.sleep_enabled = True
        self.sleep_timeout = config.get('power.sleep_timeout', 120)
        
    def set_cpu_cores(self, num_cores: int):
        """
        Set number of active CPU cores for power management
        
        Args:
            num_cores: Number of cores to keep online (1-4)
        """
        try:
            # Check if feature is enabled
            if not self.config.get('power.single_core_reading', True):
                return
            
            # Get total cores
            with open('/sys/devices/system/cpu/present', 'r') as f:
                present = f.read().strip()
                if '-' in present:
                    total_cores = int(present.split('-')[1]) + 1
                else:
                    total_cores = 1
            
            # Clamp to valid range
            num_cores = max(1, min(num_cores, total_cores))
            
            # Set cores online/offline
            for cpu_num in range(1, total_cores):  # cpu0 cannot be disabled
                target_state = '1' if cpu_num < num_cores else '0'
                cpu_path = f'/sys/devices/system/cpu/cpu{cpu_num}/online'

                try:
                    # Use shell command with echo pipe to tee for reliable sysfs writing
                    result = subprocess.run(
                        f'echo {target_state} | sudo tee {cpu_path}',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode != 0:
                        self.logger.warning(f"Failed to set CPU{cpu_num} to {target_state}: {result.stderr}")
                    else:
                        self.logger.debug(f"CPU{cpu_num} set to {'online' if target_state == '1' else 'offline'}")
                except Exception as e:
                    self.logger.warning(f"Failed to set CPU{cpu_num} state: {e}")
            
            # Verify the change by reading back the states
            online_cores = self._count_online_cores()
            self.logger.info(f"CPU cores set to {num_cores}/{total_cores} (verified: {online_cores} online)")

        except Exception as e:
            self.logger.warning(f"Failed to manage CPU cores: {e}")

    def _count_online_cores(self) -> int:
        """Count the number of online CPU cores"""
        try:
            online = 1  # cpu0 is always online
            for cpu_num in range(1, 4):
                cpu_path = f'/sys/devices/system/cpu/cpu{cpu_num}/online'
                if os.path.exists(cpu_path):
                    with open(cpu_path, 'r') as f:
                        if f.read().strip() == '1':
                            online += 1
            return online
        except Exception:
            return -1  # Unknown

    def enable_single_core_mode(self):
        """Enable single-core mode for power saving during reading"""
        self.set_cpu_cores(1)

    def restore_all_cores(self):
        """Restore all CPU cores when not reading"""
        try:
            with open('/sys/devices/system/cpu/present', 'r') as f:
                present = f.read().strip()
                if '-' in present:
                    total_cores = int(present.split('-')[1]) + 1
                else:
                    total_cores = 1
            self.set_cpu_cores(total_cores)
        except:
            self.set_cpu_cores(4)  # Default to 4 cores if detection fails
    
    def reset_activity(self):
        """Reset activity timer"""
        self.last_activity_time = time.time()
    
    def should_enter_sleep(self):
        """Check if device should enter sleep mode"""
        if not self.sleep_enabled or self.is_sleeping:
            return False
        return time.time() - self.last_activity_time > self.sleep_timeout
    
    def enter_sleep(self, sleep_message="Shh I'm sleeping"):
        """
        Enter sleep mode
        
        Args:
            sleep_message: Message to display on sleep screen
        """
        self.logger.info("Entering sleep mode (inactive)")
        self.is_sleeping = True
        
        # Create sleep image
        image = Image.new('1', (self.display.width, self.display.height), 1)
        draw = ImageDraw.Draw(image)
        
        # Try to load a font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 48)
        except:
            font = ImageFont.load_default()
        
        try:
            bbox = draw.textbbox((0, 0), sleep_message, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text(((self.display.width - w)//2, (self.display.height - h)//2), sleep_message, font=font, fill=0)
        except:
            draw.text((100, 100), sleep_message, fill=0)  # Fallback
            
        # Full refresh for sleep screen
        self.display.display_image(image, use_partial=False)
    
    def wake_from_sleep(self):
        """Wake from sleep mode"""
        self.logger.info("Waking from sleep")
        self.is_sleeping = False
        self.reset_activity()
    
    def disable_wifi(self):
        """Disable WiFi for battery savings"""
        if not self.config.get('web.always_on', False):
            try:
                os.system("sudo ifconfig wlan0 down")
                self.logger.info("📶 WiFi disabled for battery savings")
            except Exception as e:
                self.logger.warning(f"Failed to disable WiFi: {e}")
    
    def enable_wifi(self):
        """Enable WiFi"""
        if not self.config.get('web.always_on', False):
            try:
                os.system("sudo ifconfig wlan0 up")
                self.logger.info("📶 WiFi enabled")
                # Wait a moment for WiFi to come up
                time.sleep(2)
            except Exception as e:
                self.logger.warning(f"Failed to enable WiFi: {e}")
