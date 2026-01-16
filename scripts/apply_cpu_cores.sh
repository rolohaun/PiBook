#!/bin/bash
# Apply CPU cores at boot setting via maxcpus kernel parameter in cmdline.txt
# This script is called by the web interface with sudo permissions via sudoers
# Reference: https://www.jeffgeerling.com/blog/2021/disabling-cores-reduce-pi-zero-2-ws-power-consumption-half

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <num_cores>"
    echo "Example: $0 2"
    exit 1
fi

NUM_CORES="$1"
CMDLINE_FILE="/boot/firmware/cmdline.txt"

# Validate input (must be between 1 and 4)
if ! [[ "$NUM_CORES" =~ ^[1-4]$ ]]; then
    echo "Error: Number of cores must be between 1 and 4"
    exit 1
fi

# Backup cmdline.txt
BACKUP_FILE="/boot/firmware/cmdline.txt.backup.$(date +%Y%m%d_%H%M%S)"
cp "$CMDLINE_FILE" "$BACKUP_FILE"

# Read current cmdline
CMDLINE=$(cat "$CMDLINE_FILE")

# Handle the setting based on value
if [ "$NUM_CORES" -eq 4 ]; then
    # Remove maxcpus parameter to use all cores (default)
    if echo "$CMDLINE" | grep -q "maxcpus="; then
        # Remove existing maxcpus parameter
        NEW_CMDLINE=$(echo "$CMDLINE" | sed 's/ maxcpus=[0-9]*//g')
        echo "$NEW_CMDLINE" > "$CMDLINE_FILE"
        echo "Removed maxcpus parameter - will use all 4 cores (default)"
    else
        echo "No maxcpus parameter found - already using all 4 cores"
    fi
else
    # Set specific number of cores
    if echo "$CMDLINE" | grep -q "maxcpus="; then
        # Update existing maxcpus parameter
        NEW_CMDLINE=$(echo "$CMDLINE" | sed "s/maxcpus=[0-9]*/maxcpus=$NUM_CORES/g")
        echo "$NEW_CMDLINE" > "$CMDLINE_FILE"
    else
        # Add maxcpus parameter (append to end of line)
        NEW_CMDLINE="$CMDLINE maxcpus=$NUM_CORES"
        echo "$NEW_CMDLINE" > "$CMDLINE_FILE"
    fi
    echo "Set maxcpus=$NUM_CORES"
fi

echo "Successfully applied CPU cores setting: $NUM_CORES"
echo "Backup saved to: $BACKUP_FILE"
echo "Reboot required for changes to take effect"

# Show current cmdline for verification
echo "Current cmdline.txt:"
cat "$CMDLINE_FILE"
