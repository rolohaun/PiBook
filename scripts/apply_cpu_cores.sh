#!/bin/bash
# Apply CPU cores at boot setting to /boot/firmware/config.txt
# This script is called by the web interface with sudo permissions via sudoers
# Reference: https://www.jeffgeerling.com/blog/2021/disabling-cores-reduce-pi-zero-2-ws-power-consumption-half

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <num_cores>"
    echo "Example: $0 2"
    exit 1
fi

NUM_CORES="$1"
CONFIG_FILE="/boot/firmware/config.txt"

# Validate input (must be between 1 and 4)
if ! [[ "$NUM_CORES" =~ ^[1-4]$ ]]; then
    echo "Error: Number of cores must be between 1 and 4"
    exit 1
fi

# Backup config
BACKUP_FILE="/boot/firmware/config.txt.web_cpu_cores.$(date +%Y%m%d_%H%M%S)"
cp "$CONFIG_FILE" "$BACKUP_FILE"

# Handle the setting based on value
if [ "$NUM_CORES" -eq 4 ]; then
    # Remove or comment out the setting to use all cores (default)
    if grep -q "^arm_nr_cores=" "$CONFIG_FILE"; then
        # Comment out existing setting
        sed -i "s|^arm_nr_cores=.*|# arm_nr_cores=4  # Disabled - using all cores|" "$CONFIG_FILE"
        echo "Removed arm_nr_cores setting - will use all 4 cores (default)"
    else
        echo "No arm_nr_cores setting found - already using all 4 cores"
    fi
else
    # Set specific number of cores
    if grep -q "^arm_nr_cores=" "$CONFIG_FILE"; then
        # Update existing
        sed -i "s|^arm_nr_cores=.*|arm_nr_cores=$NUM_CORES|" "$CONFIG_FILE"
    elif grep -q "^# arm_nr_cores=" "$CONFIG_FILE"; then
        # Uncomment and update existing
        sed -i "s|^# arm_nr_cores=.*|arm_nr_cores=$NUM_CORES|" "$CONFIG_FILE"
    else
        # Add new setting (look for CPU Power Management section or append)
        if grep -q "# ---- CPU Power Management ----" "$CONFIG_FILE"; then
            # Add after CPU Power Management header
            sed -i "/# ---- CPU Power Management ----/a arm_nr_cores=$NUM_CORES" "$CONFIG_FILE"
        elif grep -q "over_voltage=" "$CONFIG_FILE"; then
            # Add near other power settings
            sed -i "/over_voltage=/a arm_nr_cores=$NUM_CORES" "$CONFIG_FILE"
        else
            # Append to end with comment
            echo "" >> "$CONFIG_FILE"
            echo "# CPU core limit for power savings (1-4, default 4)" >> "$CONFIG_FILE"
            echo "arm_nr_cores=$NUM_CORES" >> "$CONFIG_FILE"
        fi
    fi
    echo "Set arm_nr_cores=$NUM_CORES"
fi

echo "Successfully applied CPU cores setting: $NUM_CORES"
echo "Backup saved to: $BACKUP_FILE"
echo "Reboot required for changes to take effect"
