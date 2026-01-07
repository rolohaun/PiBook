# Power Optimization Setup

This script applies boot-level power optimizations to maximize battery life.

## What It Does

- Disables HDMI output (~14mA savings)
- Disables Bluetooth (~25mA savings)
- Disables audio (~8mA savings)
- Disables activity/power LEDs (~3mA savings)
- Disables unnecessary hardware probing
- Stops unused system services

**Total savings: ~50mA continuously**

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

- **Before**: ~20-24 hours reading time
- **After**: ~30-40 hours reading time

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

## Based On

https://kittenlabs.de/blog/2024/09/01/extreme-pi-boot-optimization/
