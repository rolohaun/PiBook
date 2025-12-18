# PiBook E-Reader Implementation Plan

## Quick Start (On Your Raspberry Pi)

**Prerequisites:**
- Raspberry Pi 3B+ or Zero 2 W with Raspberry Pi OS installed
- Waveshare 7.5" e-Paper HAT connected
- SSH or terminal access to your Pi
- Internet connection for package installation

**To implement this plan:**
1. Copy this entire markdown file to your Pi at: `/home/pi/pibook_plan.md`
2. On your Pi, create the project directory:
   ```bash
   mkdir -p /home/pi/PiBook
   cd /home/pi/PiBook
   ```
3. Start Claude Code and provide this message:
   ```
   Implement the PiBook E-reader according to /home/pi/pibook_plan.md
   Create all files, scripts, and code as specified in the plan.
   ```
4. Claude will create the complete project structure with all code

**Expected Implementation Time:** 30-60 minutes

**Files to be Created:**
- 8 Python source files
- 2 configuration files
- 4 shell scripts
- 1 systemd service file
- Project structure with books/, cache/, tests/ directories

---

## Project Overview

Build a Python-based E-reader for Raspberry Pi using:
- **Hardware:** Waveshare 7.5" e-ink display (800×480, black/white)
- **Development:** Raspberry Pi 3B+
- **Production:** Raspberry Pi Zero 2 W
- **Technology Stack:** PyMuPDF (fitz) for EPUB rendering, Pillow for image processing, gpiozero for buttons

## Executive Summary

Python-based E-reader with **95-98% code portability** between Pi 3B+ (development) and Pi Zero 2 W (production).

### Key Answer to Your Question: What WON'T Need to Change?

**100% Portable (No Changes Required):**
- ✅ All Python application code
- ✅ All GPIO pin assignments (identical 40-pin headers)
- ✅ All SPI interface configuration (same `/dev/spidev0.0`)
- ✅ Display driver code (same Waveshare library)
- ✅ Button handling logic
- ✅ EPUB parsing and text rendering
- ✅ UI/Navigation system
- ✅ Configuration file structure
- ✅ All Python library dependencies

**Optional Adjustments (Configuration Only):**
- ⚙️ `config.yaml`: May reduce cache sizes for Pi Zero 2 W's 512MB RAM
  - `page_cache_size`: 10 → 5
  - `font_cache_limit`: 5 → 3
  - `gc_threshold`: 100 → 50
- ⚙️ Optional: Enable ZRAM on Pi Zero 2 W for memory optimization

**Migration Process:**
1. Shutdown Pi 3B+
2. Move SD card to Pi Zero 2 W
3. Boot and run
4. (Optional) Tune config values if needed

---

## Architecture: The PyMuPDF Advantage

### Why PyMuPDF (fitz)?

**Traditional Approach (NOT using):**
- Parse EPUB → Extract text → Calculate layout → Wrap text → Render to image
- Problems: Manual font handling, complex pagination, loses formatting, doesn't support images in EPUBs

**PyMuPDF Approach (USING THIS):**
- Open EPUB → Render page N → Done!
- PyMuPDF does ALL the heavy lifting: fonts, images, layout, formatting

### Core Loop

```python
# 1. Load EPUB
doc = fitz.open("book.epub")

# 2. Render page to image
page = doc[page_num]
pix = page.get_pixmap(dpi=150)
img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

# 3. Convert to e-ink format (1-bit black/white)
img = img.resize((800, 480))
img = img.convert('1')

# 4. Display on e-ink
display.display_image(img)

# 5. Wait for button press → repeat with next page
```

**Benefits:**
✅ Preserves original EPUB formatting, fonts, images
✅ No manual text wrapping or pagination needed
✅ Works with complex EPUBs (tables, styled text, embedded fonts)
✅ Simpler codebase (~200 lines vs ~800 lines for manual text layout)
✅ Better user experience (sees book as author intended)

---

## Recommended Technology Stack

| Component | Library | Why? |
|-----------|---------|------|
| **EPUB Rendering** | PyMuPDF (fitz) | Renders EPUB pages directly to images with formatting preserved |
| **Image Processing** | Pillow (PIL) | Resize to screen resolution, convert to 1-bit for e-ink |
| **Hardware Driver** | waveshare-epd | Standard driver for Waveshare e-ink displays |
| **GPIO Input** | gpiozero | Simpler than RPi.GPIO, cleaner API for buttons |
| **Configuration** | PyYAML | YAML config files |

### Event-Driven Architecture

E-ink displays work like a digital picture frame, not a continuous display. The application flow:

```
┌─────────────────────────────────────────┐
│  Initialize Hardware                    │
│  - E-ink display                        │
│  - GPIO buttons                         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Render Current Screen                  │
│  - Library: Show book list              │
│  - Reader: Render current EPUB page     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Wait for Button Press (sleep)          │
│  - Next/Prev: Navigate pages/menu       │
│  - Select: Open book                    │
│  - Back: Return to library              │
└──────────────┬──────────────────────────┘
               │
               └──────> Loop back to Render
```

**Key Insight:** Don't build a GUI that constantly redraws. Render once, sleep, wake on button press, render again.

---

## Project Structure

```
PiBook/
├── src/
│   ├── main.py                    # Application entry point
│   ├── config.py                  # Configuration manager
│   ├── display/
│   │   └── display_driver.py      # Waveshare display abstraction
│   ├── reader/
│   │   ├── epub_renderer.py       # EPUB rendering (PyMuPDF/fitz)
│   │   └── page_cache.py          # Page image caching (LRU)
│   ├── ui/
│   │   ├── screens.py             # Library & Reader screens
│   │   ├── navigation.py          # State machine
│   │   └── components.py          # UI components (optional)
│   └── hardware/
│       └── gpio_handler.py        # Button input (gpiozero)
├── lib/
│   └── waveshare_epd/             # Waveshare drivers (git submodule)
│       └── epd7in5.py
├── books/                          # EPUB library storage
├── cache/                          # Runtime page cache (optional)
├── config/
│   ├── config.yaml                # Main configuration
│   └── gpio_mapping.yaml          # Button pin assignments
├── scripts/
│   ├── install_dependencies.sh    # System setup
│   ├── setup_spi.sh               # Enable SPI interface
│   ├── setup_zram.sh              # ZRAM for Pi Zero 2 W (optional)
│   └── pibook.service             # Systemd auto-start
├── tests/
│   ├── test_epub_renderer.py
│   └── test_page_cache.py
└── requirements.txt
```

---

## Implementation Steps

### Phase 1: Environment Setup

**File: `scripts/install_dependencies.sh`**
- Update system packages
- Install system dependencies:
  - `python3-pip`, `python3-pil`, `python3-dev`
  - `libmupdf-dev` (for PyMuPDF)
  - `fonts-noto-serif`, `fonts-noto-sans`
  - SPI tools
- Enable SPI interface (`sudo raspi-config nonint do_spi 0`)
- Install Python packages from requirements.txt
- Clone Waveshare e-Paper library into `lib/waveshare_epd/`
- Create directories (books/, cache/, logs/)

**File: `requirements.txt`**
```txt
PyMuPDF==1.23.8             # EPUB rendering (fitz) - THE KEY LIBRARY
Pillow==10.2.0              # Image processing (resize, 1-bit conversion)
gpiozero==2.0.1             # GPIO control (simpler than RPi.GPIO)
spidev==3.6                 # SPI interface
PyYAML==6.0.1               # Config parsing
```

### Phase 2: Configuration System

**File: `config/config.yaml`**
```yaml
display:
  width: 800
  height: 480
  dpi: 150                    # DPI for PyMuPDF rendering

library:
  books_directory: "/home/pi/PiBook/books"
  items_per_page: 8
  font_size: 20               # For library menu rendering only

reader:
  page_cache_size: 5          # Rendered page cache (reduce to 3 for Pi Zero 2 W)
  zoom: 1.0                   # Page zoom factor (1.0 = fit to screen)

performance:
  gc_threshold: 100           # Reduce to 50 for Pi Zero 2 W
  preload_next_page: true     # Preload next page in background

logging:
  level: "INFO"
  file: "/var/log/pibook/app.log"
```

**File: `config/gpio_mapping.yaml`**
```yaml
buttons:
  next_page:
    pin: 5                    # BCM numbering
    pull: "up"
    edge: "falling"
  prev_page:
    pin: 6
    pull: "up"
    edge: "falling"
  select:
    pin: 13
    pull: "up"
    edge: "falling"
  back:
    pin: 19
    pull: "up"
    edge: "falling"
  menu:
    pin: 26
    pull: "up"
    edge: "falling"

debounce:
  time_ms: 200
```

**File: `src/config.py`**
- Load YAML configuration
- Dot-notation access (e.g., `config.get('display.width')`)
- Environment variable expansion

### Phase 3: Hardware Abstraction Layer

**File: `src/display/display_driver.py`**
- Import Waveshare `epd7in5` driver
- Initialize display with SPI
- Provide methods: `initialize()`, `clear()`, `display_image(PIL.Image)`, `sleep()`, `cleanup()`
- Abstract all hardware specifics from application code

**File: `src/hardware/gpio_handler.py`**
- Use `gpiozero.Button` for each button (simpler than RPi.GPIO)
- Setup GPIO pins from config
- Built-in debouncing (bounce_time parameter)
- Register callbacks using `button.when_pressed = callback_fn`
- Methods: `register_callback(button_name, callback_fn)`, `cleanup()`

**Key Design:** Complete hardware abstraction ensures zero code changes when switching Pi models.

### Phase 4: EPUB Rendering Engine (PyMuPDF)

**File: `src/reader/epub_renderer.py`**

**Core Architecture:** PyMuPDF handles ALL layout/formatting. We just render pages to images.

```python
import fitz  # PyMuPDF
from PIL import Image

class EPUBRenderer:
    def __init__(self, epub_path: str, config: dict):
        self.doc = fitz.open(epub_path)  # Open EPUB
        self.page_count = len(self.doc)
        self.width = config['width']
        self.height = config['height']
        self.dpi = config.get('dpi', 150)

    def render_page(self, page_num: int) -> Image.Image:
        """Render EPUB page to PIL Image"""
        page = self.doc[page_num]

        # Calculate zoom to fit screen
        zoom = min(self.width / page.rect.width,
                   self.height / page.rect.height)
        mat = fitz.Matrix(zoom, zoom)

        # Render to pixmap (RGB image)
        pix = page.get_pixmap(matrix=mat, dpi=self.dpi)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Resize to exact screen size
        img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)

        # Convert to 1-bit (black/white) for e-ink
        img = img.convert('1')

        return img

    def get_page_count(self) -> int:
        return self.page_count

    def get_metadata(self) -> dict:
        return {
            'title': self.doc.metadata.get('title', 'Unknown'),
            'author': self.doc.metadata.get('author', 'Unknown')
        }

    def close(self):
        self.doc.close()
```

**Key Benefits:**
- PyMuPDF preserves original EPUB formatting, fonts, images
- No manual text wrapping or pagination needed
- Works with complex EPUBs (tables, images, styled text)

**File: `src/reader/page_cache.py`**
- LRU cache for rendered page images
- Configurable cache size (5 on Pi 3B+, 3 on Pi Zero 2 W)
- Optional: Preload next page in background thread
- Methods: `get_page(page_num)`, `cache_page(page_num, image)`, `clear()`

**Optimization:** Cache rendered images (PIL Image objects) to avoid re-rendering on navigation

### Phase 5: User Interface

**File: `src/ui/navigation.py`**
- State machine with screens: LIBRARY, READER, BOOK_INFO
- Track current/previous screen
- Pass state between screens (selected book, page number)
- Methods: `navigate_to(screen, state)`, `go_back()`, `get_state(key)`, `set_state(key, value)`

**File: `src/ui/screens.py`**

**LibraryScreen:**
- Load EPUB files from books directory
- Display list with selection cursor
- Pagination for large libraries
- Render title, list items, footer with PIL
- Methods: `load_books(dir)`, `next_item()`, `prev_item()`, `get_selected_book()`, `render()` → PIL Image

**ReaderScreen:**
- Uses `EPUBRenderer` to get page images
- Uses `PageCache` for caching
- Navigation between pages (next/prev)
- Display page counter overlay (optional)
- Methods: `load_epub(epub_path)`, `next_page()`, `prev_page()`, `get_current_image()` → PIL Image

**Simplified flow:**
```python
# In ReaderScreen
def get_current_image(self) -> Image.Image:
    # Check cache first
    cached = self.page_cache.get_page(self.current_page)
    if cached:
        return cached

    # Render and cache
    img = self.epub_renderer.render_page(self.current_page)
    self.page_cache.cache_page(self.current_page, img)
    return img
```

### Phase 6: Main Application

**File: `src/main.py`**

**PiBookApp class:**
- Initialize all components (display, GPIO, screens, navigation)
- Setup logging
- Register GPIO callbacks for buttons:
  - Next/Prev: Navigate lists or pages
  - Select: Open book
  - Back: Return to library
  - Menu: Always return to library
- Main loop: `signal.pause()` (event-driven)
- Render current screen on state changes
- Graceful shutdown on Ctrl+C

**Button Handlers:**
```python
def _handle_next(self):
    if current_screen == LIBRARY:
        library_screen.next_item()
    elif current_screen == READER:
        reader_screen.next_page()
    self._render_current_screen()

def _handle_select(self):
    if current_screen == LIBRARY:
        book = library_screen.get_selected_book()
        self._open_book(book)  # Open EPUB with PyMuPDF

def _open_book(self, book):
    # Simple! PyMuPDF handles everything
    reader_screen.load_epub(book['path'])
    navigation.navigate_to(READER, {'book': book})
    self._render_current_screen()
```

**Entry Point:**
```python
def main():
    config_path = os.environ.get('PIBOOK_CONFIG', '/home/pi/PiBook/config/config.yaml')
    app = PiBookApp(config_path)
    app.start()  # Blocks until shutdown
```

### Phase 7: System Integration

**File: `scripts/pibook.service`** (systemd)
```ini
[Unit]
Description=PiBook E-Reader Application
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/PiBook
Environment="PIBOOK_CONFIG=/home/pi/PiBook/config/config.yaml"
ExecStart=/usr/bin/python3 /home/pi/PiBook/src/main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**Installation:**
```bash
sudo cp scripts/pibook.service /etc/systemd/system/
sudo systemctl enable pibook.service
sudo systemctl start pibook.service
```

### Phase 8: Testing & Optimization

**File: `tests/test_epub_renderer.py`**
- Test EPUB loading with PyMuPDF
- Verify page rendering produces correct image format (800x480, 1-bit)
- Test metadata extraction
- Test page count accuracy

**File: `tests/test_page_cache.py`**
- Test LRU cache eviction
- Test cache hit/miss scenarios
- Test memory cleanup

**Pi Zero 2 W Optimizations:**

1. **Memory Management:**
   - Reduce cache sizes in config.yaml
   - More aggressive garbage collection
   - Lazy loading enabled by default

2. **ZRAM Setup** (optional - `scripts/setup_zram.sh`):
   ```bash
   sudo apt-get install zram-config
   # Allocate 50% of RAM (256MB) to compressed swap
   ```

3. **Performance Monitoring:**
   - Add GC trigger every N page turns
   - Log memory usage periodically
   - Monitor page render times

---

## Critical Files Summary

1. **`src/main.py`** - Central orchestration, lifecycle management, button callbacks
2. **`src/reader/epub_renderer.py`** - PyMuPDF rendering engine (THE KEY FILE)
3. **`src/display/display_driver.py`** - Hardware abstraction for e-ink display
4. **`src/hardware/gpio_handler.py`** - Button input handling with gpiozero
5. **`config/config.yaml`** - Only file needing adjustment between Pi models

---

## Portability Architecture

### Why This Design Is Portable

1. **Identical Hardware Interfaces:**
   - Both Pi 3B+ and Zero 2 W have same 40-pin GPIO header
   - Both use `/dev/spidev0.0` for SPI
   - Waveshare library works identically

2. **Platform-Agnostic Code:**
   - Pure Python (no compiled platform-specific extensions)
   - PIL for all rendering (same on both platforms)
   - Standard library for text processing

3. **Hardware Abstraction Layers:**
   - Display driver wraps Waveshare specifics
   - GPIO handler wraps RPi.GPIO
   - Configuration-driven, not hard-coded

4. **Memory-Conscious Design:**
   - Designed for Pi Zero 2 W's 512MB constraint
   - LRU caching with configurable limits
   - Lazy loading by default
   - Works even better on Pi 3B+'s 1GB RAM

### Migration Checklist

**Pi 3B+ → Pi Zero 2 W:**
1. ✅ Shutdown Pi 3B+, remove SD card
2. ✅ Insert SD card into Pi Zero 2 W
3. ✅ Boot - everything works!
4. ⚙️ Optional: Edit `config.yaml` to reduce cache sizes
5. ⚙️ Optional: Run `scripts/setup_zram.sh` for extra memory

**What Changes:** Configuration values only (3-5 lines in config.yaml)
**What Stays Same:** 100% of code, GPIO mappings, display setup, all libraries

---

## Development Workflow

### Initial Setup on Pi 3B+
```bash
cd /home/pi/PiBook
chmod +x scripts/install_dependencies.sh
./scripts/install_dependencies.sh
sudo reboot

# After reboot
python3 src/main.py
```

### Testing
```bash
# Unit tests
python3 -m pytest tests/

# Run with logging
python3 src/main.py

# View logs
tail -f /var/log/pibook/app.log
```

### Deployment
```bash
# Enable auto-start
sudo systemctl enable pibook.service
sudo systemctl start pibook.service

# Check status
sudo systemctl status pibook.service
```

---

## Implementation Checklist

Execute these steps **in order** on your Raspberry Pi:

### Step 1: Environment Setup
```bash
cd /home/pi/PiBook
chmod +x scripts/install_dependencies.sh
./scripts/install_dependencies.sh
sudo reboot
```

### Step 2: Test Hardware
```bash
cd /home/pi/PiBook
# Test display
python3 -c "import sys; sys.path.insert(0, 'lib'); from waveshare_epd import epd7in5; epd = epd7in5.EPD(); epd.init(); epd.Clear(); print('Display OK')"

# Test GPIO
python3 -c "from gpiozero import Button; print('GPIO OK')"
```

### Step 3: Add EPUB Books
```bash
# Copy your EPUB files to the books directory
cp /path/to/your/*.epub /home/pi/PiBook/books/
```

### Step 4: Run Application
```bash
# Run directly
python3 src/main.py

# Or install as service
sudo cp scripts/pibook.service /etc/systemd/system/
sudo systemctl enable pibook.service
sudo systemctl start pibook.service
```

### Step 5: View Logs
```bash
# If running as service
sudo journalctl -u pibook.service -f

# If using file logging
tail -f /var/log/pibook/app.log
```

---

## Next Steps After Implementation

1. Test with various EPUB files
2. Tune cache settings if needed for Pi Zero 2 W
3. Optional: Enable ZRAM on Pi Zero 2 W (`./scripts/setup_zram.sh`)
4. Optional: Wire up physical buttons to GPIO pins per config

### Future Enhancements
- Bookmarks/reading progress persistence (SQLite database)
- Chapter navigation (use PyMuPDF's table of contents)
- Font size adjustment (zoom parameter in config)
- PDF support (PyMuPDF supports PDFs natively!)
- Sleep timer
- Battery monitoring (if using battery HAT)
- Book sync via network/USB

---

## Troubleshooting

**Display not working:**
```bash
# Check SPI enabled
ls /dev/spi*  # Should see spidev0.0
sudo raspi-config nonint do_spi 0  # Enable
```

**Import errors:**
```bash
pip3 install -r requirements.txt
```

**Permission errors:**
```bash
sudo usermod -a -G spi,gpio pi
```

**Out of memory (Pi Zero 2 W):**
- Reduce cache sizes in config.yaml
- Enable ZRAM: `./scripts/setup_zram.sh`
