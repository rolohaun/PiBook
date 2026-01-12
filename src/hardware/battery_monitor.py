"""
Battery monitoring with support for multiple backends.
Supports PiSugar2, ADS1115 ADC, and mock mode with auto-detection.
PORTABILITY: 100% portable - includes mock mode for testing without hardware
"""

import logging
import time
import socket
from typing import Optional
from collections import deque
from abc import ABC, abstractmethod


class BatteryBackend(ABC):
    """Abstract base class for battery monitoring backends"""

    @abstractmethod
    def read_voltage(self) -> float:
        """Read battery voltage in volts"""
        pass

    @abstractmethod
    def read_percentage(self) -> int:
        """Read battery percentage (0-100)"""
        pass

    @abstractmethod
    def is_charging(self) -> bool:
        """Check if battery is currently charging"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get backend name"""
        pass


class PiSugar2Backend(BatteryBackend):
    """PiSugar2 battery backend using Unix socket"""
    
    def __init__(self, socket_path: str = "/tmp/pisugar-server.sock"):
        self.logger = logging.getLogger(__name__)
        self.socket_path = socket_path
        self._available = self._check_available()
    
    def _check_available(self) -> bool:
        """Check if PiSugar2 socket is available"""
        try:
            import os
            return os.path.exists(self.socket_path)
        except:
            return False
    
    def _send_command(self, command: str) -> Optional[str]:
        """Send command to PiSugar socket and get response"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect(self.socket_path)
            sock.sendall(f"{command}\n".encode())
            response = sock.recv(1024).decode().strip()
            sock.close()
            return response
        except Exception as e:
            self.logger.error(f"PiSugar2 socket error: {e}")
            return None
    
    def read_voltage(self) -> float:
        """Read battery voltage from PiSugar2"""
        response = self._send_command("get battery_v")
        if response:
            try:
                # Response format: "battery_v: 3.85"
                voltage_str = response.split(":")[-1].strip()
                return float(voltage_str)
            except:
                pass
        return 0.0
    
    def read_percentage(self) -> int:
        """Read battery percentage from PiSugar2"""
        response = self._send_command("get battery")
        if response:
            try:
                # Response format: "battery: 75.5"
                percentage_str = response.split(":")[-1].strip()
                return int(float(percentage_str))
            except:
                pass
        return 0

    def is_charging(self) -> bool:
        """Check if battery is charging from PiSugar2"""
        # Try multiple methods to detect charging
        
        # Method 1: battery_charging command
        response = self._send_command("get battery_charging")
        if response:
            try:
                # Response format: "battery_charging: true" or "battery_charging: false"
                charging_str = response.split(":")[-1].strip().lower()
                is_charging = charging_str == "true"
                self.logger.debug(f"Charging status (battery_charging): {is_charging} (response: {response})")
                return is_charging
            except Exception as e:
                self.logger.warning(f"Failed to parse battery_charging: {e}")
        
        # Method 2: Try battery_power_plugged (alternative command)
        response2 = self._send_command("get battery_power_plugged")
        if response2:
            try:
                plugged_str = response2.split(":")[-1].strip().lower()
                is_plugged = plugged_str == "true"
                self.logger.debug(f"Charging status (power_plugged): {is_plugged} (response: {response2})")
                return is_plugged
            except Exception as e:
                self.logger.warning(f"Failed to parse battery_power_plugged: {e}")
        
        self.logger.debug("No charging status detected, returning False")
        return False

    def is_available(self) -> bool:
        return self._available
    
    def get_name(self) -> str:
        return "PiSugar2"


class ADS1115Backend(BatteryBackend):
    """ADS1115 ADC battery backend"""
    
    def __init__(
        self,
        adc_channel: int = 0,
        voltage_divider_ratio: float = 2.0,
        min_voltage: float = 3.0,
        max_voltage: float = 4.2
    ):
        self.logger = logging.getLogger(__name__)
        self.adc_channel = adc_channel
        self.voltage_divider_ratio = voltage_divider_ratio
        self.min_voltage = min_voltage
        self.max_voltage = max_voltage
        self._available = False
        self.ads = None
        self.channel = None
        
        self._init_adc()
    
    def _init_adc(self):
        """Initialize ADS1115 ADC"""
        try:
            import board
            import busio
            import adafruit_ads1x15.ads1115 as ADS
            from adafruit_ads1x15.analog_in import AnalogIn
            
            # Create I2C bus
            i2c = busio.I2C(board.SCL, board.SDA)
            
            # Create ADS1115 object
            self.ads = ADS.ADS1115(i2c)
            
            # Create analog input on specified channel
            channels = {0: ADS.P0, 1: ADS.P1, 2: ADS.P2, 3: ADS.P3}
            if self.adc_channel in channels:
                self.channel = AnalogIn(self.ads, channels[self.adc_channel])
                self._available = True
                self.logger.info(f"ADS1115 initialized on channel {self.adc_channel}")
            else:
                raise ValueError(f"Invalid ADC channel: {self.adc_channel}")
        
        except ImportError:
            self.logger.debug("ADS1115 libraries not available")
        except Exception as e:
            self.logger.debug(f"ADS1115 initialization failed: {e}")
    
    def read_voltage(self) -> float:
        """Read battery voltage from ADC"""
        if not self._available:
            return 0.0
        
        try:
            adc_voltage = self.channel.voltage
            battery_voltage = adc_voltage * self.voltage_divider_ratio
            return battery_voltage
        except Exception as e:
            self.logger.error(f"Error reading ADC: {e}")
            return 0.0
    
    def read_percentage(self) -> int:
        """Calculate percentage from voltage"""
        voltage = self.read_voltage()
        voltage = max(self.min_voltage, min(self.max_voltage, voltage))
        percentage = ((voltage - self.min_voltage) / (self.max_voltage - self.min_voltage)) * 100
        return int(round(percentage))

    def is_charging(self) -> bool:
        """ADS1115 doesn't detect charging status"""
        return False

    def is_available(self) -> bool:
        return self._available
    
    def get_name(self) -> str:
        return "ADS1115"


class MockBackend(BatteryBackend):
    """Mock battery backend for testing"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def read_voltage(self) -> float:
        """Return simulated voltage (75% charge)"""
        return 3.9
    
    def read_percentage(self) -> int:
        """Return simulated percentage"""
        return 75

    def is_charging(self) -> bool:
        """Mock backend always returns False for charging"""
        return False

    def is_available(self) -> bool:
        return True
    
    def get_name(self) -> str:
        return "Mock"


class BatteryMonitor:
    """
    Unified battery monitor with auto-detection of available backends
    """
    
    def __init__(
        self,
        adc_channel: int = 0,
        voltage_divider_ratio: float = 2.0,
        min_voltage: float = 3.0,
        max_voltage: float = 4.2,
        smoothing_samples: int = 5,
        update_interval: float = 30.0,
        pisugar_socket: str = "/tmp/pisugar-server.sock"
    ):
        """
        Initialize battery monitor with auto-detection

        Args:
            adc_channel: ADC channel number (0-3 for ADS1115)
            voltage_divider_ratio: Voltage divider ratio (e.g., 2.0 for 2:1)
            min_voltage: Battery empty voltage (V)
            max_voltage: Battery full voltage (V)
            smoothing_samples: Number of samples to average
            update_interval: Seconds between readings
            pisugar_socket: Path to PiSugar2 socket
        """
        self.logger = logging.getLogger(__name__)
        self.smoothing_samples = smoothing_samples
        self.update_interval = update_interval
        
        # Voltage reading buffer for smoothing
        self.voltage_buffer = deque(maxlen=smoothing_samples)
        
        # Last update timestamp
        self.last_update = 0
        
        # Cached values
        self._cached_voltage: Optional[float] = None
        self._cached_percentage: Optional[int] = None
        self._cached_charging: Optional[bool] = None

        # Auto-detect backend
        self.backend = self._detect_backend(
            pisugar_socket=pisugar_socket,
            adc_channel=adc_channel,
            voltage_divider_ratio=voltage_divider_ratio,
            min_voltage=min_voltage,
            max_voltage=max_voltage
        )
        
        self.logger.info(f"Battery backend: {self.backend.get_name()}")
        
        # Initialize with first reading
        self._update_reading()
    
    def _detect_backend(
        self,
        pisugar_socket: str,
        adc_channel: int,
        voltage_divider_ratio: float,
        min_voltage: float,
        max_voltage: float
    ) -> BatteryBackend:
        """Auto-detect available battery backend"""
        
        # Try PiSugar2 first
        pisugar = PiSugar2Backend(pisugar_socket)
        if pisugar.is_available():
            self.logger.info("Detected PiSugar2 battery module")
            return pisugar
        
        # Try ADS1115
        ads1115 = ADS1115Backend(
            adc_channel=adc_channel,
            voltage_divider_ratio=voltage_divider_ratio,
            min_voltage=min_voltage,
            max_voltage=max_voltage
        )
        if ads1115.is_available():
            self.logger.info("Detected ADS1115 ADC module")
            return ads1115
        
        # Fallback to mock
        self.logger.warning("No battery hardware detected. Using mock mode.")
        return MockBackend()
    
    def _update_reading(self):
        """Update voltage reading and cache"""
        # Read new voltage
        voltage = self.backend.read_voltage()
        
        # Add to buffer
        self.voltage_buffer.append(voltage)
        
        # Calculate smoothed voltage (average)
        self._cached_voltage = sum(self.voltage_buffer) / len(self.voltage_buffer)
        
        # Get percentage (use backend's calculation for PiSugar2, smoothed for others)
        if isinstance(self.backend, PiSugar2Backend):
            # PiSugar2 provides percentage directly
            self._cached_percentage = self.backend.read_percentage()
        else:
            # Calculate from smoothed voltage for other backends
            self._cached_percentage = self.backend.read_percentage()

        # Get charging status
        self._cached_charging = self.backend.is_charging()

        # Update timestamp
        self.last_update = time.time()

        self.logger.debug(
            f"Battery: {self._cached_voltage:.2f}V ({self._cached_percentage}%) Charging: {self._cached_charging}"
        )
    
    def get_voltage(self) -> float:
        """
        Get current battery voltage (smoothed)

        Returns:
            Battery voltage (V)
        """
        # Update if needed
        if time.time() - self.last_update >= self.update_interval:
            self._update_reading()
        
        return self._cached_voltage if self._cached_voltage is not None else 0.0
    
    def get_percentage(self) -> int:
        """
        Get current battery percentage

        Returns:
            Battery percentage (0-100)
        """
        # Update if needed
        if time.time() - self.last_update >= self.update_interval:
            self._update_reading()

        return self._cached_percentage if self._cached_percentage is not None else 0

    def is_charging(self) -> bool:
        """
        Check if battery is currently charging

        Returns:
            True if battery is charging
        """
        # Update if needed
        if time.time() - self.last_update >= self.update_interval:
            self._update_reading()

        return self._cached_charging if self._cached_charging is not None else False

    def force_update(self):
        """Force an immediate battery reading update"""
        self._update_reading()

    def is_low_battery(self, threshold: int = 20) -> bool:
        """
        Check if battery is below threshold

        Args:
            threshold: Low battery threshold (%)

        Returns:
            True if battery is low
        """
        return self.get_percentage() <= threshold
    
    def get_status(self) -> dict:
        """
        Get complete battery status

        Returns:
            Dictionary with voltage, percentage, charging status, and other info
        """
        percentage = self.get_percentage()
        voltage = self.get_voltage()
        charging = self.is_charging()

        return {
            'voltage': voltage,
            'percentage': percentage,
            'is_charging': charging,
            'is_low': self.is_low_battery(),
            'backend': self.backend.get_name(),
            'last_update': self.last_update
        }
    
    @property
    def hardware_available(self) -> bool:
        """For backward compatibility"""
        return not isinstance(self.backend, MockBackend)
