#!/bin/bash
# PiBook Undervolt Testing Script
# Helps you safely test different undervolt levels to find optimal power savings
# Based on: https://forums.raspberrypi.com/viewtopic.php?t=324988

set -e

echo "========================================"
echo "PiBook Undervolt Testing Utility"
echo "========================================"
echo ""
echo "This script helps you find the optimal undervolt setting for your Pi."
echo "Forum testing showed -8 (200mV reduction) on Pi Zero 2 W reduced power"
echo "from 2.07W to 1.06W during active use."
echo ""
echo "⚠️  WARNING: Setting too low may prevent boot!"
echo "   Have an SD card reader ready to edit config.txt if needed."
echo ""

CONFIG_FILE="/boot/firmware/config.txt"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Check current setting
echo "Current CPU voltage status:"
vcgencmd measure_volts core
echo ""

# Check current undervolt setting
if grep -q "^over_voltage=" "$CONFIG_FILE"; then
    CURRENT=$(grep "^over_voltage=" "$CONFIG_FILE" | cut -d'=' -f2)
    echo "Current over_voltage setting: $CURRENT"
    VOLTAGE_REDUCTION=$((CURRENT * -25))
    echo "Voltage reduction: ${VOLTAGE_REDUCTION}mV"
else
    echo "No undervolt currently applied (over_voltage not set)"
    CURRENT=0
fi
echo ""

# Suggested progression
echo "========================================"
echo "Recommended Testing Progression:"
echo "========================================"
echo "1. Start:      -2  (50mV  reduction) - Very safe"
echo "2. If stable:  -4  (100mV reduction) - Safe for most Pi's"
echo "3. If stable:  -6  (150mV reduction) - Good power savings"
echo "4. If stable:  -8  (200mV reduction) - Maximum tested (forum)"
echo ""
echo "For each level:"
echo "  1. Apply the setting and reboot"
echo "  2. Run stress test for 10-15 minutes"
echo "  3. Monitor for crashes, freezes, or errors"
echo "  4. If stable, proceed to next level"
echo ""

# Menu
echo "What would you like to do?"
echo "1) Test current setting (stress test)"
echo "2) Apply undervolt -2 (50mV reduction - safe starting point)"
echo "3) Apply undervolt -4 (100mV reduction)"
echo "4) Apply undervolt -6 (150mV reduction)"
echo "5) Apply undervolt -8 (200mV reduction - maximum from forum)"
echo "6) Remove undervolt (reset to default)"
echo "7) Exit"
echo ""
read -p "Enter choice [1-7]: " choice

case $choice in
    1)
        echo ""
        echo "Running 10-minute stress test..."
        echo "Monitor for crashes, freezes, or errors."
        echo "If system becomes unstable, power off and remove undervolt."
        echo ""
        echo "Starting in 5 seconds... (Ctrl+C to cancel)"
        sleep 5

        # Run stress test with sysbench or stress-ng if available
        if command -v sysbench &> /dev/null; then
            echo "Using sysbench for CPU stress test..."
            sysbench cpu --time=600 run
        elif command -v stress-ng &> /dev/null; then
            echo "Using stress-ng for CPU stress test..."
            stress-ng --cpu 4 --timeout 600s --metrics-brief
        else
            echo "Installing stress-ng..."
            apt-get update && apt-get install -y stress-ng
            stress-ng --cpu 4 --timeout 600s --metrics-brief
        fi

        echo ""
        echo "✅ Stress test completed without crashes!"
        echo "Current voltage:"
        vcgencmd measure_volts core
        echo ""
        echo "System appears stable at current settings."
        ;;
    2|3|4|5)
        LEVEL=$([ "$choice" = "2" ] && echo "-2" || [ "$choice" = "3" ] && echo "-4" || [ "$choice" = "4" ] && echo "-6" || echo "-8")
        REDUCTION=$((LEVEL * -25))

        echo ""
        echo "Applying undervolt: $LEVEL ($REDUCTION mV reduction)"

        # Backup config
        BACKUP_FILE="/boot/firmware/config.txt.undervolt_backup.$(date +%Y%m%d_%H%M%S)"
        cp "$CONFIG_FILE" "$BACKUP_FILE"
        echo "Backup saved to: $BACKUP_FILE"

        # Update or add over_voltage setting
        if grep -q "^over_voltage=" "$CONFIG_FILE"; then
            # Update existing
            sed -i "s/^over_voltage=.*/over_voltage=$LEVEL/" "$CONFIG_FILE"
        elif grep -q "^# over_voltage=" "$CONFIG_FILE"; then
            # Uncomment existing
            sed -i "s/^# over_voltage=.*/over_voltage=$LEVEL/" "$CONFIG_FILE"
        else
            # Add new setting (look for CPU Power Management section)
            if grep -q "# ---- CPU Power Management ----" "$CONFIG_FILE"; then
                sed -i "/# ---- CPU Power Management ----/a over_voltage=$LEVEL" "$CONFIG_FILE"
            else
                # Append to end
                echo "over_voltage=$LEVEL" >> "$CONFIG_FILE"
            fi
        fi

        echo "✅ Undervolt setting applied: $LEVEL"
        echo ""
        echo "⚠️  REBOOT REQUIRED"
        echo ""
        echo "After reboot:"
        echo "  1. Check voltage: vcgencmd measure_volts core"
        echo "  2. Run stress test: sudo bash scripts/test_undervolt.sh"
        echo "  3. Use PiBook normally for 30+ minutes"
        echo "  4. If stable, consider increasing to next level"
        echo ""
        echo "If system fails to boot:"
        echo "  1. Remove SD card"
        echo "  2. Mount on another computer"
        echo "  3. Restore backup: $BACKUP_FILE"
        echo ""
        read -p "Reboot now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Rebooting..."
            reboot
        else
            echo "Please reboot manually: sudo reboot"
        fi
        ;;
    6)
        echo ""
        echo "Removing undervolt (resetting to default)..."

        # Backup config
        BACKUP_FILE="/boot/firmware/config.txt.remove_undervolt.$(date +%Y%m%d_%H%M%S)"
        cp "$CONFIG_FILE" "$BACKUP_FILE"

        # Comment out over_voltage
        sed -i 's/^over_voltage=/# over_voltage=/' "$CONFIG_FILE"

        echo "✅ Undervolt removed"
        echo "Backup saved to: $BACKUP_FILE"
        echo ""
        echo "Reboot for changes to take effect."
        read -p "Reboot now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Rebooting..."
            reboot
        fi
        ;;
    7)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
