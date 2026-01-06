# PiBook Quick Start Guide

## Transfer to Raspberry Pi

### Option 1: SCP (Network Transfer)
```bash
# From your computer
scp -r PiBook pi@raspberrypi.local:/home/pi/
```

### Option 2: USB Drive
1. Copy the entire `PiBook` folder to a USB drive
2. Plug USB drive into your Pi
3. Copy to home directory:
   ```bash
   cp -r /media/pi/YOUR_USB/PiBook /home/pi/
   ```

## Installation (On Raspberry Pi)

```bash
# SSH into your Pi
ssh pi@raspberrypi.local

# Navigate to project
cd /home/pi/PiBook

# Run installation
chmod +x scripts/install_dependencies.sh
./scripts/install_dependencies.sh

# Reboot to enable SPI
sudo reboot
```

## First Run

```bash
# SSH back in after reboot
ssh pi@raspberrypi.local
cd /home/pi/PiBook

# Add some EPUB books
cp /path/to/your/books/*.epub books/

# Run PiBook
python3 src/main.py
```

## Connect Button (Optional)

Wire a single push button between GPIO 5 and GND:

- **GPIO 5** → Toggle (Library↔Reader)
  - On library: Opens selected book
  - On reader: Returns to library

## Auto-Start on Boot

```bash
sudo cp scripts/pibook.service /etc/systemd/system/
sudo systemctl enable pibook.service
sudo systemctl start pibook.service
```

## For Pi Zero 2 W

If you experience memory issues:

1. Edit `config/config.yaml`:
   ```yaml
   reader:
     page_cache_size: 3
   performance:
     gc_threshold: 50
   ```

2. Enable ZRAM:
   ```bash
   ./scripts/setup_zram.sh
   sudo reboot
   ```

## Troubleshooting

**Display doesn't work:**
```bash
# Check SPI is enabled
ls /dev/spi*

# Enable SPI if needed
sudo raspi-config nonint do_spi 0
sudo reboot
```

**Python errors:**
```bash
# Reinstall dependencies
pip3 install -r requirements.txt
```

That's it! Happy reading! 📚

For more details, see [README.md](README.md)
