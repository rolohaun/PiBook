# Battery Monitoring Setup Guide (DIY with ADS1115)

> [!NOTE]
> **Recommended**: For easier setup, consider using [PiSugar2](PISUGAR2_SETUP.md) instead. This guide is for DIY battery monitoring with an ADC module.

This guide explains how to add battery monitoring to your PiBook e-reader using an 18650 battery with a 5V boost converter and ADS1115 ADC.

## Hardware Requirements

- **ADS1115 16-bit ADC module** (I2C interface)
- **2× 10kΩ resistors** (for voltage divider)
- **Jumper wires**
- **Breadboard** (optional, for prototyping)

## Parts List

| Component | Quantity | Purpose |
|-----------|----------|---------|
| ADS1115 ADC Module | 1 | Measure battery voltage via I2C |
| 10kΩ Resistor | 2 | Create 2:1 voltage divider |
| Jumper Wires | 6 | Connections |

## Circuit Diagram

### Voltage Divider Circuit

The voltage divider reduces the battery voltage (2.5V-4.2V) to a safe range for the ADC:

```
Battery+ ----[10kΩ]---- ADC A0 ----[10kΩ]---- Battery-/GND
```

**Why a voltage divider?**
- 18650 voltage range: 3.0V (empty) to 4.2V (full)
- The 2:1 divider outputs: 1.5V to 2.1V
- This is well within the ADC's safe input range (0-5V)

### Complete Wiring Diagram

```
18650 Battery (via 5V Boost Converter)
│
├─── Battery+ ───[10kΩ]─── ADC A0 (Channel 0)
│                          │
│                          [10kΩ]
│                          │
└─── Battery- ────────────── GND ─── Pi GND
                                 └─ ADC GND

ADS1115 ADC Module:
- VDD  → Pi 3.3V (Pin 1)
- GND  → Pi GND (Pin 6)
- SCL  → Pi GPIO 3 (Pin 5) - I2C Clock
- SDA  → Pi GPIO 2 (Pin 3) - I2C Data
- A0   → Voltage divider midpoint
- ADDR → GND (sets I2C address to 0x48)
```

## Step-by-Step Wiring Instructions

### 1. Enable I2C on Raspberry Pi

```bash
# Enable I2C interface
sudo raspi-config nonint do_i2c 0

# Reboot to apply changes
sudo reboot
```

### 2. Wire the Voltage Divider

1. Connect **Battery+** to one end of the first 10kΩ resistor
2. Connect the other end of the first resistor to **ADC A0** pin
3. Connect **ADC A0** to one end of the second 10kΩ resistor
4. Connect the other end of the second resistor to **Battery-/GND**

> [!CAUTION]
> **IMPORTANT**: Make sure the voltage divider is connected BEFORE the boost converter output, not after. You want to measure the battery voltage, not the boosted 5V output.

### 3. Wire the ADS1115 Module

| ADS1115 Pin | Connect To | Pi Pin | Notes |
|-------------|------------|--------|-------|
| VDD | 3.3V | Pin 1 | Power supply |
| GND | GND | Pin 6 | Ground |
| SCL | GPIO 3 (SCL) | Pin 5 | I2C Clock |
| SDA | GPIO 2 (SDA) | Pin 3 | I2C Data |
| A0 | Voltage Divider | - | Middle point of divider |
| ADDR | GND | - | Sets I2C address to 0x48 |

### 4. Verify I2C Connection

After wiring, verify the ADC is detected:

```bash
# Install i2c-tools if not already installed
sudo apt-get install -y i2c-tools

# Scan for I2C devices (should show 0x48)
sudo i2cdetect -y 1
```

Expected output:
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- -- 
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
40: -- -- -- -- -- -- -- -- -- 48 -- -- -- -- -- -- 
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
70: -- -- -- -- -- -- -- --
```

If you see `48`, the ADS1115 is detected correctly!

## Software Installation

### 1. Install Dependencies

```bash
cd /home/pi/PiBook
pip3 install -r requirements.txt
```

This will install the `adafruit-circuitpython-ads1x15` library.

### 2. Configure Battery Monitoring

The battery monitoring is already configured in `config/config.yaml`:

```yaml
battery:
  enabled: true               # Enable/disable battery monitoring
  adc_channel: 0              # ADC channel (0-3 for ADS1115)
  voltage_divider_ratio: 2.0  # Voltage divider ratio (2:1)
  min_voltage: 3.0            # Battery empty voltage (V)
  max_voltage: 4.2            # Battery full voltage (V)
  update_interval: 30         # Seconds between readings
  show_percentage: true       # Show percentage number
  low_battery_threshold: 20   # Warning threshold (%)
```

**Configuration Notes:**
- `voltage_divider_ratio: 2.0` - For two equal resistors (2:1 ratio)
- `min_voltage: 3.0` - 18650 cutoff voltage (0% charge)
- `max_voltage: 4.2` - 18650 full charge voltage (100% charge)
- `update_interval: 30` - Read battery every 30 seconds (saves power)

### 3. Test Battery Monitoring

Run PiBook and check the logs:

```bash
cd /home/pi/PiBook
python3 src/main.py
```

Look for these log messages:
```
Battery monitor initialized
Battery: 3.85V (75%)
```

The battery icon should appear in the **top-right corner** of both the Library and Reader screens.

## Calibration

If the displayed voltage doesn't match your multimeter reading:

### 1. Measure Actual Battery Voltage

Use a multimeter to measure the actual battery voltage directly.

### 2. Compare with Displayed Voltage

Check the PiBook logs for the displayed voltage:
```bash
tail -f /home/pi/PiBook/logs/app.log | grep Battery
```

### 3. Adjust Voltage Divider Ratio

If there's a discrepancy, adjust the `voltage_divider_ratio` in `config/config.yaml`:

```yaml
battery:
  voltage_divider_ratio: 2.05  # Adjust this value
```

**Formula:**
```
voltage_divider_ratio = actual_voltage / displayed_voltage
```

For example:
- Multimeter reads: 4.1V
- PiBook displays: 4.0V
- New ratio: 4.1 / 4.0 = 2.05

### 4. Restart and Verify

```bash
sudo systemctl restart pibook.service
```

## Troubleshooting

### ADC Not Detected (no 0x48 in i2cdetect)

**Check:**
1. I2C is enabled: `ls /dev/i2c*` (should show `/dev/i2c-1`)
2. Wiring is correct (VDD to 3.3V, GND to GND, SDA/SCL to correct pins)
3. ADS1115 module is not damaged

**Fix:**
```bash
# Re-enable I2C
sudo raspi-config nonint do_i2c 0
sudo reboot
```

### Battery Percentage Shows 0% or 100% Always

**Possible causes:**
1. Voltage divider not connected properly
2. Wrong ADC channel configured
3. Voltage divider ratio incorrect

**Fix:**
1. Check voltage divider wiring
2. Verify `adc_channel: 0` in config
3. Measure voltage with multimeter and calibrate

### Battery Icon Not Showing

**Check:**
1. Battery monitoring is enabled: `battery.enabled: true` in config
2. No errors in logs: `tail -f /home/pi/PiBook/logs/app.log`
3. ADC library installed: `pip3 list | grep adafruit-circuitpython-ads1x15`

### Voltage Reading is Unstable

**Possible causes:**
1. Loose connections
2. Electrical noise
3. Resistor values not matched

**Fix:**
1. Solder connections instead of using breadboard
2. Add a 0.1µF capacitor across A0 and GND (optional, reduces noise)
3. Use 1% tolerance resistors for better accuracy

## Advanced: Using Different ADC Channels

The ADS1115 has 4 channels (A0-A3). To use a different channel:

1. Wire voltage divider to desired channel (A1, A2, or A3)
2. Update config:
   ```yaml
   battery:
     adc_channel: 1  # For A1 (0=A0, 1=A1, 2=A2, 3=A3)
   ```

## Safety Notes

> [!CAUTION]
> - **Never exceed 5V on ADC inputs** - The voltage divider ensures this
> - **Use proper 18650 protection** - Use batteries with built-in protection circuits
> - **Monitor battery temperature** - Stop charging if battery gets hot
> - **Don't over-discharge** - The 3.0V cutoff protects the battery

## Battery Life Optimization

To maximize battery life:

1. **Increase update interval:**
   ```yaml
   battery:
     update_interval: 60  # Check every minute instead of 30 seconds
   ```

2. **Use sleep mode** - PiBook automatically sleeps after 5 minutes of inactivity

3. **Reduce display refreshes** - Use partial refresh mode when possible (already implemented)

---

**Happy Reading with Battery Power!** 🔋📚
