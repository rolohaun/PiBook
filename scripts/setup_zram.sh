#!/bin/bash
# ZRAM Setup for Pi Zero 2 W
# Enables compressed swap for better memory usage
# Optional - only needed if experiencing memory pressure on Pi Zero 2 W

set -e

echo "=================================================="
echo "ZRAM Setup for Raspberry Pi"
echo "=================================================="
echo ""

# Check if already installed
if dpkg -l | grep -q zram-config; then
    echo "ZRAM is already installed"
    echo ""
    echo "Current ZRAM status:"
    sudo zramctl
    exit 0
fi

echo "Installing ZRAM..."
sudo apt-get update
sudo apt-get install -y zram-config

echo ""
echo "Configuring ZRAM..."

# Configure ZRAM for Pi Zero 2 W
# Allocate 50% of RAM (256MB on Pi Zero 2 W)
sudo bash -c 'cat > /etc/default/zramswap <<EOF
# ZRAM configuration
# Allocate 50% of RAM to ZRAM (256MB on Pi Zero 2 W)
PERCENTAGE=50
ALGO=lz4
EOF'

echo "ZRAM configured"
echo ""

# Enable and start service
sudo systemctl enable zramswap
sudo systemctl start zramswap

echo "=================================================="
echo "ZRAM Setup Complete!"
echo "=================================================="
echo ""
echo "ZRAM Status:"
sudo zramctl
echo ""
echo "Memory Status:"
free -h
echo ""
echo "Reboot recommended: sudo reboot"
echo "=================================================="
