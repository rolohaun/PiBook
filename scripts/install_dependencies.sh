#!/bin/bash
# PiBook Installation Script
# Installs all dependencies for Pi 3B+ or Pi Zero 2 W
# PORTABILITY: Works identically on both platforms

set -e

echo "=================================================="
echo "PiBook E-Reader Installation"
echo "=================================================="
echo ""

# Detect Pi model
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(cat /proc/device-tree/model)
    echo "Detected: $PI_MODEL"
    echo ""
fi

# Update system
echo "Step 1/6: Updating system packages..."
sudo apt-get update
echo ""

# Install system dependencies
echo "Step 2/6: Installing system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-pil \
    python3-dev \
    python3-yaml \
    libopenjp2-7 \
    libtiff5 \
    libfreetype6-dev \
    libjpeg-dev \
    libmupdf-dev \
    fonts-dejavu \
    fonts-dejavu-core \
    git \
    build-essential

echo ""

# Enable SPI interface
echo "Step 3/6: Enabling SPI interface..."
if ! grep -q "^dtparam=spi=on" /boot/config.txt; then
    echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
    echo "SPI enabled in /boot/config.txt"
else
    echo "SPI already enabled"
fi

# Alternative method using raspi-config
sudo raspi-config nonint do_spi 0
echo ""

# Install Python dependencies
echo "Step 4/6: Installing Python packages..."
pip3 install --upgrade pip
pip3 install -r requirements.txt
echo ""

# Setup Waveshare library
echo "Step 5/6: Setting up Waveshare e-Paper library..."
if [ ! -d "lib/waveshare_epd" ]; then
    mkdir -p lib
    cd lib

    # Clone Waveshare library
    if [ ! -d "e-Paper" ]; then
        git clone https://github.com/waveshare/e-Paper
    fi

    # Copy Python library
    cp -r e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd .

    cd ..
    echo "Waveshare library installed"
else
    echo "Waveshare library already installed"
fi
echo ""

# Create directories
echo "Step 6/6: Creating application directories..."
mkdir -p books
mkdir -p cache
mkdir -p logs
mkdir -p output

echo "Directories created"
echo ""

# Set permissions
chmod +x scripts/*.sh

echo "=================================================="
echo "Installation Complete!"
echo "=================================================="
echo ""
echo "IMPORTANT: Reboot your Raspberry Pi to enable SPI:"
echo "  sudo reboot"
echo ""
echo "After reboot, run PiBook with:"
echo "  python3 src/main.py"
echo ""
echo "Or install as a service:"
echo "  sudo cp scripts/pibook.service /etc/systemd/system/"
echo "  sudo systemctl enable pibook.service"
echo "  sudo systemctl start pibook.service"
echo ""
echo "Add EPUB files to: $(pwd)/books/"
echo "=================================================="
