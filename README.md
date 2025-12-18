# PiBook E-Reader

A Python-based E-reader for Raspberry Pi with Waveshare 7.5" e-ink display.

## Features

- **EPUB Support**: Renders EPUBs with full formatting using PyMuPDF
- **E-ink Display**: Optimized for Waveshare 7.5" e-Paper HAT (800×480)
- **Button Navigation**: GPIO-based controls for page turning and menu navigation
- **Web Interface**: Manage books and control e-reader from any device
  - Upload/delete EPUB files wirelessly
  - Remote page navigation (Next/Prev/Select)
  - File management (rename, delete)
  - Works on phone, tablet, or computer
- **IP Address Display**: Shows Pi's IP on library screen
- **Memory Efficient**: Designed for Pi Zero 2 W (512MB RAM)
- **100% Portable**: Same code runs on Pi 3B+ and Pi Zero 2 W

## Hardware Requirements

- Raspberry Pi 3B+ or Pi Zero 2 W
- Waveshare 7.5inch e-Paper HAT (800×480, black/white)
- MicroSD card (8GB+)
- Power supply
- 5× Push buttons (for GPIO control)

## Technology Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| EPUB Rendering | PyMuPDF (fitz) | Renders EPUB pages to images |
| Image Processing | Pillow (PIL) | Resizes and converts to 1-bit for e-ink |
| Hardware Driver | waveshare-epd | E-ink display driver |
| GPIO Input | gpiozero | Button handling |
| Configuration | PyYAML | Config file management |

## Installation

### On Your Raspberry Pi

1. **Copy this directory to your Pi:**
   ```bash
   # On your computer, transfer files to Pi
   scp -r PiBook pi@raspberrypi.local:/home/pi/

   # Or use a USB drive
   ```

2. **SSH into your Pi:**
   ```bash
   ssh pi@raspberrypi.local
   cd /home/pi/PiBook
   ```

3. **Run installation script:**
   ```bash
   chmod +x scripts/install_dependencies.sh
   ./scripts/install_dependencies.sh
   ```

4. **Reboot to enable SPI:**
   ```bash
   sudo reboot
   ```

5. **Add EPUB books:**
   ```bash
   # Copy your EPUB files to the books directory
   cp /path/to/your/*.epub /home/pi/PiBook/books/
   ```

6. **Run PiBook:**
   ```bash
   cd /home/pi/PiBook
   python3 src/main.py
   ```

## Button Wiring (GPIO)

Connect buttons between GPIO pins and GND:

| Button | GPIO Pin (BCM) | Function |
|--------|---------------|----------|
| Next | GPIO 5 | Next page/item |
| Previous | GPIO 6 | Previous page/item |
| Select | GPIO 13 | Open book |
| Back | GPIO 19 | Return to library |
| Menu | GPIO 26 | Go to main menu |

**Wiring:**
- Connect one side of each button to the GPIO pin
- Connect the other side to GND
- Internal pull-up resistors are enabled in software

## Configuration

Edit `config/config.yaml` to customize:

```yaml
display:
  width: 800
  height: 480
  dpi: 150

reader:
  page_cache_size: 5  # Reduce to 3 for Pi Zero 2 W if needed

performance:
  gc_threshold: 100   # Reduce to 50 for Pi Zero 2 W if needed
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

## Migrating from Pi 3B+ to Pi Zero 2 W

**No code changes needed!** Just:

1. Shutdown Pi 3B+
2. Remove SD card
3. Insert SD card into Pi Zero 2 W
4. Boot
5. (Optional) Reduce cache sizes in `config/config.yaml`

### Optional: ZRAM for Pi Zero 2 W

For better memory usage on Pi Zero 2 W:

```bash
cd /home/pi/PiBook
./scripts/setup_zram.sh
sudo reboot
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

### Out of memory (Pi Zero 2 W)

1. Reduce cache sizes in `config/config.yaml`:
   ```yaml
   reader:
     page_cache_size: 3

   performance:
     gc_threshold: 50
   ```

2. Enable ZRAM:
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
```

## Usage

### Web Interface (Recommended for Easy Management)

1. **Find the IP address**: Displayed at the top of the library screen
2. **Open in browser**: Navigate to `http://<pi-ip>:5000` on any device
3. **Upload books**: Click "Choose File" and upload EPUB files
4. **Remote control**: Use on-screen buttons to navigate:
   - **Previous/Next**: Navigate through book list or pages
   - **Select**: Open selected book
   - **Back**: Return to library from book
   - **Menu**: Always return to library
   - **Refresh**: Reload the page to see updated book list

### Physical Buttons (Optional)

Wire buttons to GPIO pins as specified in `config/gpio_mapping.yaml`:

#### Library Screen
- **Next/Prev buttons** (GPIO 5/6): Navigate book list
- **Select button** (GPIO 13): Open selected book

#### Reader Screen
- **Next/Prev buttons**: Turn pages
- **Back button** (GPIO 19): Return to library
- **Menu button** (GPIO 26): Return to library

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

## Performance

**Pi 3B+ (1GB RAM):**
- EPUB loading: ~2-5 seconds
- Page rendering: ~0.5-1 second (cached: instant)
- Recommended cache size: 5-10 pages

**Pi Zero 2 W (512MB RAM):**
- EPUB loading: ~5-10 seconds
- Page rendering: ~1-2 seconds (cached: instant)
- Recommended cache size: 3-5 pages

## Future Enhancements

- [ ] Bookmarks and reading progress persistence
- [ ] Chapter navigation via table of contents
- [ ] Font size adjustment
- [ ] PDF support (PyMuPDF supports PDFs natively)
- [ ] Search within books
- [ ] Dictionary lookup
- [ ] Book metadata editing
- [ ] Wi-Fi sync with Calibre
- [ ] Battery level indicator (for battery HATs)
- [ ] Sleep timer

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
