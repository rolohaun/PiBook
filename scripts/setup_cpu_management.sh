#!/bin/bash
# Setup script for CPU core management permissions
# Allows PiBook to manage CPU cores without password for power optimization

echo "Setting up CPU core management permissions..."

# Add sudoers rule for CPU core management
SUDOERS_FILE="/etc/sudoers.d/pibook-cpu-management"

# Create sudoers entry
cat > /tmp/pibook-sudoers << 'HEREDOC'
# Allow pi user to manage CPU cores for power optimization
pi ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/devices/system/cpu/cpu*/online
HEREDOC

# Move to sudoers directory with sudo
sudo mv /tmp/pibook-sudoers "$SUDOERS_FILE"

# Set correct permissions on sudoers file
sudo chmod 0440 "$SUDOERS_FILE"

# Verify the file was created correctly
if sudo visudo -c -f "$SUDOERS_FILE" > /dev/null 2>&1; then
    echo "✓ CPU core management permissions configured successfully"
    echo "  PiBook can now manage CPU cores for power saving"
else
    echo "✗ Error: sudoers file has syntax errors"
    sudo rm -f "$SUDOERS_FILE"
    exit 1
fi

echo ""
echo "Setup complete! PiBook will now:"
echo "  - Use 1 CPU core when reading books (power saving)"
echo "  - Use all CPU cores in library/menu (normal performance)"
echo ""
echo "You can disable this feature by setting power.single_core_reading: false in config.yaml"
