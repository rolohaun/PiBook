#!/bin/bash
# PiBook Power Optimization Script
# Applies boot-level optimizations to /boot/firmware/config.txt
# Based on: https://kittenlabs.de/blog/2024/09/01/extreme-pi-boot-optimization/

set -e

echo "========================================"
echo "PiBook Power Optimization Setup"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

CONFIG_FILE="/boot/firmware/config.txt"
BACKUP_FILE="/boot/firmware/config.txt.backup.$(date +%Y%m%d_%H%M%S)"

# Backup current config
echo "📋 Backing up current config to: $BACKUP_FILE"
cp "$CONFIG_FILE" "$BACKUP_FILE"

# Check if optimizations already applied
if grep -q "# PiBook Power Optimizations" "$CONFIG_FILE"; then
    echo "⚠️  Power optimizations already applied!"
    echo "To reapply, restore from backup first:"
    echo "   sudo cp $BACKUP_FILE $CONFIG_FILE"
    exit 0
fi

echo "✏️  Applying power optimizations to $CONFIG_FILE"

# Add optimizations to config.txt
cat >> "$CONFIG_FILE" << 'EOF'

# ========================================
# PiBook Power Optimizations
# Added by setup_power_optimization.sh
# ========================================

# ---- HDMI Disabled (saves ~14mA) ----
dtoverlay=vc4-kms-v3d,nohdmi
max_framebuffers=1
disable_fw_kms_setup=1
disable_overscan=1
enable_tvout=0
hdmi_blanking=2
hdmi_ignore_edid=0xa5000080
hdmi_ignore_cec_init=1
hdmi_ignore_cec=1

# ---- LEDs Disabled (saves ~3mA) ----
dtparam=act_led_trigger=none
dtparam=act_led_activelow=on
dtparam=pwr_led_trigger=none
dtparam=pwr_led_activelow=off

# ---- Bluetooth Disabled (saves ~25mA) ----
dtoverlay=disable-bt

# ---- Audio Disabled (saves ~8mA) ----
dtparam=audio=off

# ---- Disable Unnecessary Hardware Probing ----
force_eeprom_read=0
disable_poe_fan=1
ignore_lcd=1
disable_touchscreen=1
camera_auto_detect=0
display_auto_detect=0

# ---- CPU Power Management ----
force_turbo=0
arm_boost=0
arm_freq_min=600

# ---- CPU Undervolting (EXPERIMENTAL) ----
# Reduces core voltage to save power during sleep
# Range: 0 to -16 (each step = -25mV), but -8 is practical max
# Forum testing: -8 reduced power from 2.07W to 1.06W on Pi Zero 2 W
# WARNING: Too low may prevent boot - have SD card reader ready!
# Start with -2 (50mV), test stability, then increase to -4 or -6
over_voltage=-2

# ---- Minimize GPU Memory (more RAM for CPU) ----
gpu_mem=16

EOF

echo "✅ Power optimizations added to config.txt"
echo ""

# Disable Bluetooth service
echo "🔵 Disabling Bluetooth service..."
systemctl disable bluetooth 2>/dev/null || true
systemctl stop bluetooth 2>/dev/null || true

# Disable audio services
echo "🔊 Disabling audio services..."
systemctl disable alsa-state 2>/dev/null || true
systemctl stop alsa-state 2>/dev/null || true

# Disable other unnecessary services
echo "🛑 Disabling unnecessary services..."
systemctl disable triggerhappy 2>/dev/null || true
systemctl stop triggerhappy 2>/dev/null || true
systemctl disable ModemManager 2>/dev/null || true
systemctl stop ModemManager 2>/dev/null || true

echo ""
echo "========================================"
echo "✅ Power Optimizations Applied!"
echo "========================================"
echo ""
echo "Expected power savings: ~50mA + undervolt savings"
echo "Expected battery life: 30-40+ hours reading"
echo ""
echo "Changes made:"
echo "  ✓ HDMI disabled (~14mA)"
echo "  ✓ Bluetooth disabled (~25mA)"
echo "  ✓ Audio disabled (~8mA)"
echo "  ✓ LEDs disabled (~3mA)"
echo "  ✓ CPU undervolted -2 steps (50mV reduction)"
echo "  ✓ Unnecessary services stopped"
echo ""
echo "⚠️  REBOOT REQUIRED for changes to take effect!"
echo ""
echo "After reboot, check voltage with:"
echo "  vcgencmd measure_volts core"
echo ""
echo "If stable, you can increase undervolt to -4 or -6 in config.txt"
echo "Edit: $CONFIG_FILE (search for 'over_voltage')"
echo ""
echo "Backup saved to: $BACKUP_FILE"
echo ""
read -p "Reboot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Rebooting..."
    reboot
else
    echo "Please reboot manually: sudo reboot"
fi
