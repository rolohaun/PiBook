#!/bin/bash
# Apply undervolt setting to /boot/firmware/config.txt
# This script is called by the web interface with sudo permissions via sudoers

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <undervolt_level>"
    echo "Example: $0 -4"
    exit 1
fi

LEVEL="$1"
CONFIG_FILE="/boot/firmware/config.txt"

# Validate input (must be between -8 and 0)
if ! [[ "$LEVEL" =~ ^-?[0-8]$ ]] || [ "$LEVEL" -lt -8 ] || [ "$LEVEL" -gt 0 ]; then
    echo "Error: Undervolt level must be between -8 and 0"
    exit 1
fi

# Backup config
BACKUP_FILE="/boot/firmware/config.txt.web_undervolt.$(date +%Y%m%d_%H%M%S)"
cp "$CONFIG_FILE" "$BACKUP_FILE"

# Update or add over_voltage setting
if grep -q "^over_voltage=" "$CONFIG_FILE"; then
    # Update existing (use | as delimiter to avoid issues with negative numbers)
    sed -i "s|^over_voltage=.*|over_voltage=$LEVEL|" "$CONFIG_FILE"
elif grep -q "^# over_voltage=" "$CONFIG_FILE"; then
    # Uncomment existing
    sed -i "s|^# over_voltage=.*|over_voltage=$LEVEL|" "$CONFIG_FILE"
else
    # Add new setting (look for CPU Power Management or Undervolting section)
    if grep -q "# ---- CPU Undervolting" "$CONFIG_FILE"; then
        sed -i "/# ---- CPU Undervolting/a over_voltage=$LEVEL" "$CONFIG_FILE"
    elif grep -q "# ---- CPU Power Management ----" "$CONFIG_FILE"; then
        # Find the end of CPU Power Management section and add there
        awk -v level="$LEVEL" '
        /# ---- CPU Power Management ----/ {found=1}
        found && /^$/ && !added {print "over_voltage=" level; added=1}
        {print}
        END {if (!added) print "over_voltage=" level}
        ' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
    else
        # Append to end
        echo "" >> "$CONFIG_FILE"
        echo "# Undervolt setting" >> "$CONFIG_FILE"
        echo "over_voltage=$LEVEL" >> "$CONFIG_FILE"
    fi
fi

echo "Successfully applied undervolt setting: $LEVEL"
echo "Backup saved to: $BACKUP_FILE"
echo "Reboot required for changes to take effect"
