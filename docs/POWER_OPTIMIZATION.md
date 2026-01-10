# Power Optimization Setup

This script applies boot-level power optimizations to maximize battery life.

## What It Does

- Disables HDMI output (~14mA savings)
- Disables Bluetooth (~25mA savings)
- Disables audio (~8mA savings)
- Disables activity/power LEDs (~3mA savings)
- Disables unnecessary hardware probing
- Stops unused system services
- **CPU Undervolting** (experimental - additional power savings)

**Total savings: ~50mA + undervolt savings** (undervolt can add 30-50% additional power reduction based on forum testing)

## Usage

```bash
cd /home/pi/PiBook
sudo chmod +x scripts/setup_power_optimization.sh
sudo ./scripts/setup_power_optimization.sh
```

The script will:
1. Backup your current `/boot/firmware/config.txt`
2. Add power optimization settings
3. Disable unnecessary services
4. Prompt for reboot

## Expected Results

- **Before optimizations**: ~20-24 hours reading time
- **After basic optimizations**: ~30-40 hours reading time
- **After undervolting**: ~40-60+ hours reading time (depends on undervolt level and usage)

Forum testing on Pi Zero 2 W showed undervolting from default to -8 reduced power consumption by nearly 50% (from 2.07W to 1.06W during active use). During sleep, savings should be even more significant.

## Rollback

If you need to undo the changes:

```bash
# Find your backup
ls -la /boot/firmware/config.txt.backup.*

# Restore it
sudo cp /boot/firmware/config.txt.backup.YYYYMMDD_HHMMSS /boot/firmware/config.txt
sudo reboot
```

## What Still Works

✅ E-ink display
✅ GPIO buttons  
✅ PiSugar2 battery monitoring
✅ WiFi (when enabled)
✅ All PiBook features

## What's Disabled

❌ HDMI output (never needed)
❌ Bluetooth (not used)
❌ Audio (not used)
❌ Activity/Power LEDs (visual feedback lost)

## Verification

After reboot, check that:
- PiBook starts normally
- E-ink display works
- Buttons work
- Battery monitoring works

Check current draw with PiSugar2:
```bash
echo "get battery_current" | nc -U /tmp/pisugar-server.sock
```

## CPU Undervolting (Experimental)

### What is Undervolting?

Undervolting reduces the CPU core voltage to save power. This is particularly effective during sleep mode when you want maximum battery life.

### Safety Warning

⚠️ **IMPORTANT**: Setting undervolt too aggressively may prevent your Pi from booting!

**Before you begin:**
- Have an SD card reader available to edit config.txt from another computer if needed
- Start with conservative settings and test stability before increasing
- Keep backups of your config.txt

### Quick Start

The setup script applies a safe starting point of `-2` (50mV reduction). To experiment with more aggressive settings:

```bash
cd /home/pi/PiBook
sudo bash scripts/test_undervolt.sh
```

### Recommended Testing Progression

1. **-2 (50mV)**: Safe starting point - applied by default
2. **-4 (100mV)**: Safe for most Pi's - good power savings
3. **-6 (150mV)**: Aggressive but usually stable - better savings
4. **-8 (200mV)**: Maximum tested - best savings but test carefully

For each level:
1. Apply the setting and reboot
2. Run the stress test (option 1 in test script)
3. Use PiBook normally for 30+ minutes
4. If stable, proceed to next level
5. If unstable (crashes, freezes), reduce by one level

### Manual Configuration

Edit `/boot/firmware/config.txt` and modify the `over_voltage` setting:

```bash
# Example: -4 = 100mV reduction
over_voltage=-4
```

Then reboot:
```bash
sudo reboot
```

### Checking Current Voltage

```bash
vcgencmd measure_volts core
```

The PiBook app also logs the current voltage on startup (check logs with DEBUG level enabled).

### Recovery from Failed Boot

If your Pi won't boot after undervolting:

1. Power off the Pi
2. Remove the SD card
3. Insert SD card into another computer
4. Edit `/boot/firmware/config.txt`
5. Change `over_voltage=-X` to `over_voltage=-2` or comment it out with `#`
6. Safely eject SD card and reinsert into Pi
7. Boot normally

### Performance Trade-off

Forum testing showed that with `-8` undervolt:
- Power consumption: **Reduced by ~50%** (2.07W → 1.06W)
- Processing time: **Increased by ~67%** (413s → 691s)

For an e-reader where most time is spent sleeping or displaying static pages, this trade-off is excellent for battery life.

### Configuration

The undervolt setting is also stored in `config/config.yaml`:

```yaml
power:
  undervolt: -2  # Start here, increase after testing
```

This setting is informational and logged by the app. The actual undervolt is applied via `/boot/firmware/config.txt`.

## References

- Base optimizations: https://kittenlabs.de/blog/2024/09/01/extreme-pi-boot-optimization/
- Undervolting guide: https://forums.raspberrypi.com/viewtopic.php?t=324988
