# PiSugar2 Setup Guide

Complete guide for setting up PiSugar2 battery module with PiBook e-reader.

## What is PiSugar2?

PiSugar2 is an all-in-one battery solution for Raspberry Pi that includes:
- **18650 battery holder** with built-in battery
- **Charging circuit** (charges via USB-C)
- **5V boost converter** (powers the Pi)
- **Battery monitoring** via I2C
- **Real-Time Clock (RTC)** for timekeeping
- **Custom button** for user input
- **Safe shutdown** on low battery

**No resistors or ADC modules needed!** Everything is integrated.

## Hardware Installation

### 1. Physical Installation

1. **Attach PiSugar2 to Raspberry Pi**:
   - Align the GPIO pins
   - Press firmly to connect
   - PiSugar2 sits on top/bottom of Pi (depending on model)

2. **Insert Battery**:
   - Slide 18650 battery into holder
   - Ensure correct polarity (+ and - markings)

3. **Power On**:
   - Flip the power switch on PiSugar2
   - Pi should boot normally

### 2. Enable I2C

PiSugar2 communicates via I2C, so it must be enabled:

```bash
# Enable I2C
sudo raspi-config nonint do_i2c 0

# Reboot
sudo reboot
```

### 3. Verify I2C Connection

After reboot, check that PiSugar2 is detected:

```bash
# Install i2c-tools if needed
sudo apt-get install -y i2c-tools

# Scan for I2C devices
sudo i2cdetect -y 1
```

Expected output should show devices at **0x75** and **0x32**:
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- -- 
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
30: -- -- 32 -- -- -- -- -- -- -- -- -- -- -- -- -- 
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
70: -- -- -- -- -- 75 -- -- 
```

## Software Installation

### 1. Install PiSugar Power Manager

```bash
# Download and install
curl http://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash
```

This installs:
- PiSugar server (communicates with hardware)
- Web UI (for configuration)
- Command-line tools

### 2. Verify Installation

```bash
# Check service status
sudo systemctl status pisugar-server

# Should show "active (running)"
```

### 3. Access Web UI

Open a browser and navigate to:
```
http://<pi-ip-address>:8421
```

You should see the PiSugar Power Manager dashboard showing:
- Battery percentage
- Voltage
- Charging status
- Temperature

## PiBook Integration

### 1. Battery Monitoring (Automatic)

PiBook automatically detects PiSugar2! No configuration needed.

When you run PiBook, check the logs:
```bash
cd /home/pi/PiBook
python3 src/main.py
```

Look for:
```
Battery backend: PiSugar2
Battery monitor initialized
```

The battery icon will appear in the top-right corner of all screens.

### 2. Button Configuration

Configure the PiSugar2 button to control PiBook:

#### Step 1: Open PiSugar Web UI

Navigate to `http://<pi-ip>:8421` in your browser.

#### Step 2: Configure Custom Button Functions

In the web UI, find the **"Custom Button Function"** section.

Configure the following:

**Single Tap** (Next Page):
```bash
echo "next_page" | nc -U /tmp/pibook-button.sock
```

**Double Tap** (Previous Page):
```bash
echo "prev_page" | nc -U /tmp/pibook-button.sock
```

**Long Press** (Menu/Library):
```bash
echo "menu" | nc -U /tmp/pibook-button.sock
```

#### Step 3: Save Configuration

Click "Apply" or "Save" in the web UI.

#### Step 4: Test Button

1. Make sure PiBook is running
2. Press the PiSugar2 button:
   - **Single tap** → Next page
   - **Double tap** → Previous page
   - **Long press** → Return to library

Check PiBook logs for confirmation:
```bash
tail -f /home/pi/PiBook/logs/app.log | grep "PiSugar button"
```

## Configuration Options

Edit `config/config.yaml` to customize PiSugar2 integration:

```yaml
battery:
  enabled: true               # Enable battery monitoring
  # Backend auto-detected (PiSugar2 → ADS1115 → Mock)

pisugar:
  socket_path: "/tmp/pisugar-server.sock"  # PiSugar server socket
  button_enabled: true        # Enable button integration
  button_socket_path: "/tmp/pibook-button.sock"  # Button IPC socket
```

### Disable Button Integration

If you don't want to use the PiSugar2 button:

```yaml
pisugar:
  button_enabled: false
```

### Use Different Socket Paths

If you need custom socket paths:

```yaml
pisugar:
  socket_path: "/tmp/custom-pisugar.sock"
  button_socket_path: "/tmp/custom-button.sock"
```

## Troubleshooting

### Battery Icon Not Showing

**Check:**
1. PiSugar Power Manager is running: `sudo systemctl status pisugar-server`
2. I2C is enabled: `ls /dev/i2c*`
3. Socket exists: `ls -la /tmp/pisugar-server.sock`
4. Battery monitoring is enabled in `config.yaml`

**Fix:**
```bash
# Restart PiSugar server
sudo systemctl restart pisugar-server

# Restart PiBook
sudo systemctl restart pibook.service
```

### Button Not Working

**Check:**
1. PiBook is running
2. Button socket exists: `ls -la /tmp/pibook-button.sock`
3. Button is enabled in `config.yaml`
4. Custom commands are configured in PiSugar web UI

**Test manually:**
```bash
# Send test command
echo "next_page" | nc -U /tmp/pibook-button.sock

# Check if page turns
```

**Fix:**
1. Verify PiBook logs show: "PiSugar button handler started"
2. Re-configure button in PiSugar web UI
3. Restart PiBook

### Wrong Battery Percentage

**Possible causes:**
- PiSugar needs calibration
- Battery is old/degraded

**Fix:**
1. Fully charge battery (100%)
2. Fully discharge to 0%
3. Charge back to 100%
4. PiSugar will auto-calibrate

### PiSugar Server Not Starting

**Check:**
```bash
# View service logs
sudo journalctl -u pisugar-server -n 50
```

**Fix:**
```bash
# Reinstall PiSugar Power Manager
curl http://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash

# Reboot
sudo reboot
```

## Advanced Features

### Auto Power-On Schedule

Configure PiSugar2 to automatically power on at specific times:

1. Open PiSugar web UI
2. Navigate to "Auto Power On"
3. Set schedule (e.g., 8:00 AM daily)
4. Save configuration

Perfect for automatic wake-up!

### Safe Shutdown on Low Battery

PiSugar2 can automatically shut down the Pi when battery is low:

1. Open PiSugar web UI
2. Navigate to "Auto Shutdown"
3. Set threshold (e.g., 5%)
4. Enable safe shutdown

This prevents SD card corruption.

### RTC (Real-Time Clock)

PiSugar2 includes an RTC to keep time when powered off:

```bash
# Sync system time to RTC
echo "rtc_alarm_set $(date +"%Y-%m-%d %H:%M:%S")" | nc -U /tmp/pisugar-server.sock

# Read RTC time
echo "get rtc_time" | nc -U /tmp/pisugar-server.sock
```

## Battery Life Expectations

With PiSugar2 and Pi Zero 2 W:

| Battery Capacity | Continuous Reading | Light Use (1hr/day) | Moderate Use (2hr/day) |
|------------------|-------------------|---------------------|------------------------|
| **1200mAh** (standard) | 3-4 hours | 15-20 days | 7-10 days |
| **5000mAh** (extended) | 12-15 hours | 60+ days | 30-40 days |

**Tips for longer battery life:**
- Use Pi Zero 2 W (not Pi 3B+)
- Enable sleep mode (automatic after 5 min)
- Reduce screen refresh frequency
- Disable web server when not needed

## Comparison: PiSugar2 vs. DIY ADC

| Feature | PiSugar2 | DIY (ADS1115) |
|---------|----------|---------------|
| **Setup Complexity** | ✅ Easy (plug & play) | ⚠️ Moderate (wiring required) |
| **Components Needed** | ✅ 1 (all-in-one) | ⚠️ 4+ (ADC, resistors, battery, boost) |
| **Charging** | ✅ Built-in (USB-C) | ❌ Separate charger needed |
| **Safe Shutdown** | ✅ Yes | ❌ No |
| **RTC** | ✅ Yes | ❌ No |
| **Button** | ✅ Yes | ❌ No |
| **Cost** | ⚠️ Higher (~$30-40) | ✅ Lower (~$10-15) |
| **Auto-Detection** | ✅ Yes | ✅ Yes (fallback) |

**Recommendation**: Use PiSugar2 for production builds. Use DIY for learning or budget builds.

---

**Happy Reading with PiSugar2!** 🔋📚
