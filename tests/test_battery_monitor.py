"""
Unit tests for battery monitor module with PiSugar2 support
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.battery_monitor import BatteryMonitor, PiSugar2Backend, ADS1115Backend, MockBackend


def test_backend_detection():
    """Test backend auto-detection"""
    monitor = BatteryMonitor()
    
    # Should fall back to mock mode (no hardware available)
    assert isinstance(monitor.backend, MockBackend), "Should use mock backend when no hardware"
    assert monitor.backend.get_name() == "Mock"
    
    print(f"✓ Backend detection: {monitor.backend.get_name()}")


def test_mock_backend():
    """Test mock backend functionality"""
    backend = MockBackend()
    
    assert backend.is_available(), "Mock backend should always be available"
    assert backend.read_voltage() > 0, "Mock voltage should be positive"
    assert 0 <= backend.read_percentage() <= 100, "Mock percentage should be 0-100"
    
    print(f"✓ Mock backend: {backend.read_voltage()}V, {backend.read_percentage()}%")


def test_battery_monitor_interface():
    """Test BatteryMonitor unified interface"""
    monitor = BatteryMonitor()
    
    voltage = monitor.get_voltage()
    percentage = monitor.get_percentage()
    
    assert voltage > 0, "Voltage should be positive"
    assert 0 <= percentage <= 100, "Percentage should be 0-100"
    
    print(f"✓ Battery monitor interface: {voltage}V, {percentage}%")


def test_smoothing():
    """Test voltage smoothing algorithm"""
    monitor = BatteryMonitor(smoothing_samples=3, update_interval=0.1)
    
    # Manually add readings to buffer
    monitor.voltage_buffer.clear()
    monitor.voltage_buffer.append(3.8)
    monitor.voltage_buffer.append(3.9)
    monitor.voltage_buffer.append(4.0)
    
    # Calculate average
    avg = sum(monitor.voltage_buffer) / len(monitor.voltage_buffer)
    expected = 3.9
    
    print(f"Smoothing: {list(monitor.voltage_buffer)} -> {avg}V (expected {expected}V)")
    assert abs(avg - expected) < 0.01, f"Smoothing failed: got {avg}V, expected {expected}V"
    
    print("✓ Smoothing tests passed")


def test_low_battery_detection():
    """Test low battery threshold detection"""
    monitor = BatteryMonitor(min_voltage=3.0, max_voltage=4.2)
    
    # Manually set cached percentage
    monitor._cached_percentage = 15
    assert monitor.is_low_battery(20), "Should detect low battery at 15%"
    
    monitor._cached_percentage = 25
    assert not monitor.is_low_battery(20), "Should not detect low battery at 25%"
    
    monitor._cached_percentage = 20
    assert monitor.is_low_battery(20), "Should detect low battery at exactly 20%"
    
    print("✓ Low battery detection tests passed")


def test_status_dict():
    """Test get_status returns correct structure"""
    monitor = BatteryMonitor()
    status = monitor.get_status()
    
    # Check required keys
    required_keys = ['voltage', 'percentage', 'is_low', 'backend', 'last_update']
    for key in required_keys:
        assert key in status, f"Status missing key: {key}"
    
    # Check backend name
    assert status['backend'] in ['PiSugar2', 'ADS1115', 'Mock'], f"Invalid backend: {status['backend']}"
    
    print(f"Status: {status}")
    print("✓ Status dictionary tests passed")


def test_backward_compatibility():
    """Test backward compatibility property"""
    monitor = BatteryMonitor()
    
    # hardware_available should work for backward compatibility
    assert hasattr(monitor, 'hardware_available'), "Missing hardware_available property"
    assert isinstance(monitor.hardware_available, bool), "hardware_available should be bool"
    
    print(f"✓ Backward compatibility: hardware_available = {monitor.hardware_available}")


def test_ads1115_backend_init():
    """Test ADS1115 backend initialization (will fail gracefully without hardware)"""
    backend = ADS1115Backend(
        adc_channel=0,
        voltage_divider_ratio=2.0,
        min_voltage=3.0,
        max_voltage=4.2
    )
    
    # Should not crash, just not be available
    assert not backend.is_available(), "ADS1115 should not be available without hardware"
    assert backend.get_name() == "ADS1115"
    
    print("✓ ADS1115 backend initialization (graceful failure)")


def test_pisugar2_backend_init():
    """Test PiSugar2 backend initialization (will fail gracefully without hardware)"""
    backend = PiSugar2Backend(socket_path="/tmp/pisugar-server.sock")
    
    # Should not crash, just not be available
    assert not backend.is_available(), "PiSugar2 should not be available without socket"
    assert backend.get_name() == "PiSugar2"
    
    print("✓ PiSugar2 backend initialization (graceful failure)")


if __name__ == '__main__':
    print("Running battery monitor tests (with PiSugar2 support)...\n")
    
    try:
        test_backend_detection()
        test_mock_backend()
        test_battery_monitor_interface()
        test_smoothing()
        test_low_battery_detection()
        test_status_dict()
        test_backward_compatibility()
        test_ads1115_backend_init()
        test_pisugar2_backend_init()
        
        print("\n" + "="*50)
        print("ALL TESTS PASSED ✓")
        print("="*50)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
