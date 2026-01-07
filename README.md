# PiBook E-Reader

A Python-based E-reader for Raspberry Pi with Waveshare 7.5" e-ink display.

## Features

- **EPUB Support**: Renders EPUBs with full formatting including tables, SVG, custom fonts, and CSS
- **Hardware**: Raspberry Pi Zero 2 W, Waveshare 7.5" e-Paper HAT
- **Battery**: PiSugar2 (1200mAh) with UPS functionality
- **Display**: 800x480 e-ink display with partial refresh support
- **Storage**: MicroSD card for books and OS
- **Connectivity**: WiFi for web interface and book uploads
- **Expected Battery Life**: 18-24 hours reading time
- **PiSugar2 Integration**: Battery monitoring and custom button support with auto-detection
- **Reading Progress**: Automatically saves and restores your page position
- **Battery Optimized**: 2-3x battery life with aggressive power management
- **Web Interface**: Manage books and control e-reader from any device
  - Upload/delete EPUB files wirelessly
  - Remote page navigation
  - File management
- **Network Status**: WiFi and Bluetooth status indicators
- **Memory Efficient**: Optimized for Pi Zero 2 W (512MB RAM)

## Hardware Requirements

### Essential
- Raspberry Pi Zero 2 W
- Waveshare 7.5inch e-Paper HAT (800×480, black/white)
- MicroSD card (8GB+)
- **1 Push button** (GPIO control - recommended for daily use)
- **PiSugar2** battery module (battery, charging, monitoring, button)

### Setup Guides
- [PISUGAR2_SETUP.md](PISUGAR2_SETUP.md) - PiSugar2 installation and configuration
- [QUICKSTART.md](QUICKSTART.md) - Quick setup guide

## Technology Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| EPUB Rendering | PillowTextRenderer | Renders EPUB pages with full formatting |
| Image Processing | Pillow (PIL) | Image manipulation and 1-bit conversion |
| Hardware Driver | waveshare-epd | E-ink display driver with partial refresh |
| GPIO Input | gpiozero | Button handling with press detection |
| Battery Monitor | PiSugar2 | Battery status and custom button |
| Configuration | PyYAML | Config file management |
| Web Server | Flask | Web interface for book management |

## Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/rolohaun/PiBook.git
cd PiBook

# Run the installation script
chmod +x scripts/install_dependencies.sh
./scripts/install_dependencies.sh

# Reboot to enable SPI
sudo reboot
```

### Add Books

```bash
# Copy your EPUB files to the books directory
cp /path/to/your/*.epub /home/pi/PiBook/books/
```

### Run PiBook

```bash
cd /home/pi/PiBook
python3 src/main.py
```

## Button Wiring (GPIO)

Connect a single button between GPIO 5 and GND:

| Button | GPIO Pin (BCM) | Physical Pin | Function |
|--------|----------------|--------------|----------|
| Toggle | GPIO 5 | Pin 29 | Short press: Next page<br>Long press: Toggle library/reader |

**Wiring:**
- Connect one side of the button to GPIO 5 (Physical Pin 29)
- Connect the other side to GND (Physical Pin 30)
- Internal pull-up resistor is enabled in software

**Functionality:**
- **Short press** (< 0.8s): Turn to next page
- **Long press** (≥ 0.8s): Toggle between library and reader
- Same behavior as PiSugar2 custom button

## Configuration

Edit `config/config.yaml` to customize:

```yaml
display:
  width: 480
  height: 800
  rotation: 90
  partial_refresh: true
  full_refresh_interval: 10  # Battery optimization

reader:
  page_cache_size: 3  # Optimized for battery life

performance:
  gc_threshold: 50
  gc_on_page_turn: true  # Battery optimization

power:
  sleep_timeout: 120  # 2 minutes
  cpu_scaling: true
  wifi_power_save: true
```

Edit `config/gpio_mapping.yaml` to change button pins.

## Running as a Service

To auto-start PiBook on boot:

```bash
sudo cp scripts/pibook.service /etc/systemd/system/
sudo systemctl enable pibook.service
sudo systemctl start pibook.service
```

Check status:
```bash
sudo systemctl status pibook.service
```

View logs:
```bash
sudo journalctl -u pibook.service -f
```

## Troubleshooting

### Display not working

```bash
# Check SPI enabled
ls /dev/spi*  # Should see spidev0.0 and spidev0.1

# Enable SPI
sudo raspi-config nonint do_spi 0
sudo reboot
```

### Import errors

```bash
# Reinstall Python packages
pip3 install -r requirements.txt
```

### Permission errors

```bash
# Add pi user to gpio and spi groups
sudo usermod -a -G gpio,spi pi
sudo reboot
```

### Out of memory

1. Cache sizes are already optimized in `config/config.yaml`
2. Enable ZRAM if needed:
   ```bash
   ./scripts/setup_zram.sh
   ```

## Project Structure

```
PiBook/
├── src/
│   ├── main.py                    # Application entry point
│   ├── config.py                  # Configuration manager
│   ├── display/
│   │   └── display_driver.py      # E-ink display driver
│   ├── reader/
│   │   ├── epub_renderer.py       # PyMuPDF EPUB renderer
│   │   └── page_cache.py          # LRU page cache
│   ├── ui/
│   │   ├── navigation.py          # Screen navigation
│   │   └── screens.py             # Library & Reader screens
│   └── hardware/
│       └── gpio_handler.py        # GPIO button handler
├── config/
│   ├── config.yaml                # Main configuration
│   └── gpio_mapping.yaml          # GPIO pin mapping
├── scripts/
│   ├── install_dependencies.sh    # Installation script
│   ├── setup_zram.sh              # ZRAM setup (Pi Zero 2 W)
│   └── pibook.service             # Systemd service
├── books/                          # Place EPUB files here
├── logs/                           # Application logs
└── requirements.txt

## Usage


#### Toggle Button (GPIO 5)
- **Short press**: Next page (in reader) or move down (in library)
- **Long press**: Toggle between library and reader

## Development

### Mock Mode (Testing without hardware)

The application runs in mock mode when hardware is not available:
- Display output saved to `output/display_output.png`
- GPIO buttons can be triggered programmatically
- Useful for testing on development machine

### Logging

Logs are written to:
- Console (if enabled in config)
- `/home/pi/PiBook/logs/app.log`

Log level can be adjusted in `config/config.yaml`:
```yaml
logging:
  level: "DEBUG"  # DEBUG, INFO, WARNING, ERROR
```

### Performance Specifications

**With All Optimizations Enabled:**
- **Battery**: PiSugar2 1200mAh
- **Reading Time**: 18-24 hours continuous reading
- **Standby Time**: 60-80 hours
- **Page Turn Speed**: ~1-2 seconds (partial refresh)
- **Full Refresh**: Every 10 pages (configurable)
- **WiFi**: Off during reading, on in library
- **Sleep Mode**: 2 minutes inactivity (configurable)

## Implemented Features

- [x] Reading progress persistence (auto-saves page position)
- [x] Battery level indicator (PiSugar2 integration)
- [x] Battery optimization (2-3x battery life)
- [x] Short/long press button detection
- [x] Partial refresh for e-ink display
- [x] WiFi and Bluetooth status indicators

## Future Enhancements

- [ ] Chapter navigation via table of contents
- [ ] Font size adjustment
- [ ] PDF support (renderer supports PDFs)
- [ ] Search within books
- [ ] Dictionary lookup
- [ ] Book metadata editing
- [ ] Wi-Fi sync with Calibre

## License

MIT License - feel free to modify and distribute

## Credits

- **PyMuPDF**: PDF/EPUB rendering engine
- **Waveshare**: E-ink display drivers
- **Pillow**: Python imaging library
- **gpiozero**: GPIO control library

## Support

For issues, questions, or contributions, please create an issue on the project repository.

---

**Happy Reading!** 📚
