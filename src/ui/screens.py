"""
UI screen implementations for Library and Reader.
Uses Pillow for library menu, PyMuPDF for reader pages.
PORTABILITY: 100% portable between Pi 3B+ and Pi Zero 2 W
"""

from PIL import Image, ImageDraw, ImageFont
from typing import List, Optional, Dict
import os
import logging
import socket
import subprocess


def get_ip_address():
    """Get the Pi's local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "No Network"


def get_wifi_status():
    """Check if WiFi is enabled and connected"""
    try:
        # Check if wlan0 interface exists and is up
        result = subprocess.run(['ip', 'link', 'show', 'wlan0'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            # Check if interface is UP
            if 'state UP' in result.stdout or 'UP' in result.stdout:
                return True
        return False
    except Exception:
        return False


def get_bluetooth_status():
    """Check if Bluetooth is enabled"""
    try:
        # Check if bluetooth service is active
        result = subprocess.run(['systemctl', 'is-active', 'bluetooth'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip() == 'active':
            # Also check if hci0 is up
            hci_result = subprocess.run(['hciconfig', 'hci0'],
                                      capture_output=True, text=True, timeout=2)
            if hci_result.returncode == 0 and 'UP RUNNING' in hci_result.stdout:
                return True
        return False
    except Exception:
        return False


class MainMenuScreen:
    """
    Main menu screen showing available apps
    Users can navigate with single button: press=next app, hold=select app
    """

    def __init__(self, width: int = 800, height: int = 480, font_size: int = 24, battery_monitor=None):
        """
        Initialize main menu screen

        Args:
            width: Screen width
            height: Screen height
            font_size: Base font size
            battery_monitor: Optional BatteryMonitor instance
        """
        self.width = width
        self.height = height
        self.font_size = font_size
        self.battery_monitor = battery_monitor
        self.logger = logging.getLogger(__name__)

        # Load fonts
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", font_size)
            self.title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 36)
            self.app_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 20)
        except:
            self.font = ImageFont.load_default()
            self.title_font = ImageFont.load_default()
            self.app_font = ImageFont.load_default()

        # Define available apps
        self.apps = [
            {
                'name': 'eReader',
                'icon_filename': 'ereader.png',
                'description': 'Read EPUB books',
                'screen': 'library'
            },
            {
                'name': 'IP Scanner',
                'icon_filename': 'ip_scanner.png',
                'description': 'Scan network devices',
                'screen': 'ip_scanner'
            },
            {
                'name': 'To Do',
                'icon_filename': 'todo.png',
                'description': 'Manage tasks',
                'screen': 'todo'
            }
        ]

        # Pre-load icons
        self.icons = {}
        icon_size = (120, 120)  # Standard size for icons
        
        # Calculate absolute path to assets directory
        # src/ui/screens.py -> src/ui -> src -> root -> assets/icons
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        # Adjust for differing structures if needed, but assuming standard:
        # If __file__ is in src/ui/screens.py:
        # dirname -> src/ui
        # grandparent -> src
        # great-grandparent -> root
        
        # Correct calculation:
        # os.path.dirname(__file__) is .../src/ui
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets', 'icons')
        
        self.logger.info(f"Looking for icons in: {assets_dir}")

        for app in self.apps:
            try:
                icon_path = os.path.join(assets_dir, app['icon_filename'])
                if os.path.exists(icon_path):
                    img = Image.open(icon_path)
                    # Resize if needed
                    if img.size != icon_size:
                        img = img.resize(icon_size, Image.Resampling.LANCZOS)
                    # Convert to 1-bit if needed (or keep as is and convert during paste)
                    self.icons[app['name']] = img
                    self.logger.info(f"Loaded icon for {app['name']}")
                else:
                    self.logger.warning(f"Icon not found: {icon_path}")
            except Exception as e:
                self.logger.error(f"Failed to load icon for {app['name']}: {e}")

        self.current_index = 0  # Currently selected app

    def next_app(self):
        """Move to next app in menu"""
        self.current_index = (self.current_index + 1) % len(self.apps)
        self.logger.info(f"Main menu: selected {self.apps[self.current_index]['name']}")

    def get_selected_app(self):
        """Get currently selected app"""
        return self.apps[self.current_index]

    def _draw_battery_icon(self, draw: ImageDraw.Draw, x: int, y: int, percentage: int, is_charging: bool = False):
        """Draw battery icon (same as LibraryScreen)"""
        battery_width = 30
        battery_height = 14
        terminal_width = 2
        terminal_height = 6

        battery_x = x - battery_width
        draw.rectangle(
            [(battery_x, y), (battery_x + battery_width, y + battery_height)],
            outline=0,
            width=1
        )

        terminal_x = battery_x + battery_width
        terminal_y = y + (battery_height - terminal_height) // 2
        draw.rectangle(
            [(terminal_x, terminal_y), (terminal_x + terminal_width, terminal_y + terminal_height)],
            fill=0
        )

        fill_width = int((battery_width - 4) * (percentage / 100))
        if fill_width > 0:
            draw.rectangle(
                [(battery_x + 2, y + 2), (battery_x + 2 + fill_width, y + battery_height - 2)],
                fill=0
            )

        if is_charging:
            bolt_center_x = battery_x + battery_width // 2
            bolt_center_y = y + battery_height // 2
            bolt_points = [
                (bolt_center_x + 1, bolt_center_y - 5),
                (bolt_center_x - 1, bolt_center_y - 1),
                (bolt_center_x + 2, bolt_center_y - 1),
                (bolt_center_x - 1, bolt_center_y + 5),
                (bolt_center_x + 1, bolt_center_y + 1),
                (bolt_center_x - 2, bolt_center_y + 1),
            ]
            bolt_color = 1 if fill_width > battery_width - 6 else 0
            draw.polygon(bolt_points, fill=bolt_color)

        percentage_text = f"{percentage}%"
        try:
            bbox = draw.textbbox((0, 0), percentage_text, font=self.font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(percentage_text) * 8

        text_x = battery_x - text_width - 5
        draw.text((text_x, y), percentage_text, font=self.font, fill=0)

    def render(self) -> Image.Image:
        """Render main menu screen"""
        # Create white background
        image = Image.new('1', (self.width, self.height), 1)
        draw = ImageDraw.Draw(image)

        # Draw battery status in top-right corner
        if self.battery_monitor:
            battery_percentage = self.battery_monitor.get_percentage()
            is_charging = self.battery_monitor.is_charging()
            self._draw_battery_icon(draw, self.width - 10, 5, battery_percentage, is_charging)

        # Draw title centered at top
        title_text = "PiBook"
        try:
            bbox = draw.textbbox((0, 0), title_text, font=self.title_font)
            title_width = bbox[2] - bbox[0]
        except:
            title_width = len(title_text) * 20

        title_x = (self.width - title_width) // 2
        draw.text((title_x, 30), title_text, font=self.title_font, fill=0)

        # Calculate app icon layout (centered, grid style)
        icon_size = 120
        icon_spacing = 40
        start_y = 120

        # Draw apps in a grid
        for idx, app in enumerate(self.apps):
            # Calculate position (2 apps per row)
            col = idx % 2
            row = idx // 2

            x = self.width // 4 + col * (self.width // 2)
            y = start_y + row * (icon_size + icon_spacing + 60)

            # Highlight selected app with border
            if idx == self.current_index:
                # Draw selection box
                box_size = icon_size + 20
                box_x = x - box_size // 2
                box_y = y - 10
                draw.rectangle(
                    [(box_x, box_y), (box_x + box_size, box_y + box_size + 50)],
                    outline=0,
                    width=3
                )

            # Draw app icon
            if app['name'] in self.icons:
                # Center the 120x120 icon
                icon_x = x - 60
                icon_y = y
                image.paste(self.icons[app['name']], (icon_x, icon_y))
            else:
                # Fallback: draw placeholder box
                icon_x = x - 60
                icon_y = y
                draw.rectangle([(icon_x, icon_y), (icon_x + 120, icon_y + 120)], outline=0, width=2)
                draw.text((icon_x + 45, icon_y + 40), app['name'][0], font=self.title_font, fill=0)

            # Draw app name below icon
            name_text = app['name']
            try:
                bbox = draw.textbbox((0, 0), name_text, font=self.app_font)
                name_width = bbox[2] - bbox[0]
            except:
                name_width = len(name_text) * 10

            name_x = x - name_width // 2
            name_y = y + 90
            draw.text((name_x, name_y), name_text, font=self.app_font, fill=0)

        # Draw instruction text at bottom
        instruction = "Press: Next App  |  Hold: Select App"
        try:
            bbox = draw.textbbox((0, 0), instruction, font=self.app_font)
            instr_width = bbox[2] - bbox[0]
        except:
            instr_width = len(instruction) * 8

        instr_x = (self.width - instr_width) // 2
        draw.text((instr_x, self.height - 40), instruction, font=self.app_font, fill=0)

        return image


class IPScannerScreen:
    """
    IP Scanner screen - scans local network and displays devices
    """

    def __init__(self, width: int = 800, height: int = 480, font_size: int = 18, battery_monitor=None):
        """
        Initialize IP scanner screen

        Args:
            width: Screen width
            height: Screen height
            font_size: Base font size
            battery_monitor: Optional BatteryMonitor instance
        """
        self.width = width
        self.height = height
        self.font_size = font_size
        self.battery_monitor = battery_monitor
        self.logger = logging.getLogger(__name__)

        # Load fonts
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            self.title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            self.small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            self.font = ImageFont.load_default()
            self.title_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()

        # Scan state
        self.devices: List[Dict[str, str]] = []
        self.scanning = False
        self.scan_progress = 0
        self.current_page = 0
        self.items_per_page = 17  # Increased from 12 to 17 (fits on 480px height)

    def start_scan(self):
        """Start network scan in background"""
        import threading
        if not self.scanning:
            self.scanning = True
            self.scan_progress = 0
            self.devices = []
            thread = threading.Thread(target=self._scan_network, daemon=True)
            thread.start()

    def _scan_network(self):
        """Scan the local network for devices"""
        try:
            # Get local IP and network
            local_ip = get_ip_address()
            if local_ip == "No Network":
                self.scanning = False
                return

            # Extract network prefix (e.g., 192.168.1)
            ip_parts = local_ip.split('.')
            network_prefix = '.'.join(ip_parts[:3])
            network = f"{network_prefix}.0/24"

            self.logger.info(f"Scanning network {network}")

            # Try using arp-scan first (much faster)
            try:
                self.scan_progress = 10
                self.logger.info("Trying arp-scan...")
                result = subprocess.run(
                    ['sudo', 'arp-scan', '--localnet', '--interface=wlan0'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                self.logger.info(f"arp-scan return code: {result.returncode}")
                if result.returncode == 0:
                    self.logger.info("Using arp-scan for network discovery")
                    self.logger.debug(f"arp-scan output: {result.stdout}")
                    self._parse_arp_scan_output(result.stdout)
                    self.scanning = False
                    self.scan_progress = 100
                    return
                else:
                    self.logger.warning(f"arp-scan failed with stderr: {result.stderr}")

            except FileNotFoundError:
                self.logger.info("arp-scan not installed, falling back to nmap")
            except subprocess.TimeoutExpired:
                self.logger.warning("arp-scan timed out, falling back to nmap")
            except Exception as e:
                self.logger.error(f"arp-scan error: {e}", exc_info=True)

            # Try nmap as second option
            try:
                self.scan_progress = 20
                self.logger.info("Trying nmap...")
                result = subprocess.run(
                    ['nmap', '-sn', network],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                self.logger.info(f"nmap return code: {result.returncode}")
                if result.returncode == 0:
                    self.logger.info("Using nmap for network discovery")
                    self.logger.debug(f"nmap output: {result.stdout}")
                    self._parse_nmap_output(result.stdout)
                    self.scanning = False
                    self.scan_progress = 100
                    return
                else:
                    self.logger.warning(f"nmap failed with stderr: {result.stderr}")

            except FileNotFoundError:
                self.logger.info("nmap not installed, falling back to ping sweep")
            except subprocess.TimeoutExpired:
                self.logger.warning("nmap timed out, falling back to ping sweep")
            except Exception as e:
                self.logger.error(f"nmap error: {e}", exc_info=True)

            # Fall back to ping sweep (slowest but most reliable)
            self.logger.info("Using ping sweep for network discovery")
            self.scan_progress = 0

            # Scan range 1-254
            for i in range(1, 255):
                if not self.scanning:
                    break

                ip = f"{network_prefix}.{i}"
                self.scan_progress = int((i / 254) * 100)

                # Ping the IP (quick timeout)
                try:
                    result = subprocess.run(
                        ['ping', '-c', '1', '-W', '1', ip],
                        capture_output=True,
                        timeout=2
                    )

                    if result.returncode == 0:
                        # Get hostname
                        hostname = self._get_hostname(ip)
                        self.devices.append({
                            'ip': ip,
                            'hostname': hostname
                        })
                        self.logger.info(f"Found device: {ip} ({hostname})")

                except Exception as e:
                    self.logger.debug(f"Error pinging {ip}: {e}")
                    continue

            self.scanning = False
            self.scan_progress = 100
            self.logger.info(f"Scan complete. Found {len(self.devices)} devices")

        except Exception as e:
            self.logger.error(f"Network scan error: {e}", exc_info=True)
            self.scanning = False

    def _parse_arp_scan_output(self, output: str):
        """Parse arp-scan output and extract devices with vendor info"""
        lines = output.strip().split('\n')
        for line in lines:
            # arp-scan output format: IP    MAC    Vendor/Hostname
            # Skip header/footer lines
            if line and not line.startswith('Interface:') and not line.startswith('Starting') and not line.startswith('Ending') and not line.startswith('Packets'):
                parts = line.split('\t')  # arp-scan uses tabs
                if len(parts) < 2:
                    parts = line.split()  # Fallback to spaces

                if len(parts) >= 2:
                    # Check if first part looks like an IP
                    ip = parts[0].strip()
                    if ip.count('.') == 3:
                        try:
                            # Validate IP format
                            octets = ip.split('.')
                            if all(0 <= int(octet) <= 255 for octet in octets):
                                # Try to get vendor name from arp-scan output (3rd column)
                                vendor = None
                                if len(parts) >= 3:
                                    vendor = ' '.join(parts[2:]).strip()
                                    # Clean up vendor name
                                    if vendor and vendor != '(Unknown)':
                                        # Remove common suffixes
                                        vendor = vendor.replace(', Inc.', '').replace(' Inc.', '')
                                        vendor = vendor.replace(', Ltd.', '').replace(' Ltd.', '')
                                        vendor = vendor.replace(' Corporation', '').replace(' Corp.', '')

                                # Try to get proper hostname
                                hostname = self._get_hostname(ip, vendor)

                                self.devices.append({
                                    'ip': ip,
                                    'hostname': hostname
                                })
                                self.logger.info(f"Found device: {ip} ({hostname})")
                        except:
                            continue

    def _parse_nmap_output(self, output: str):
        """Parse nmap output and extract devices"""
        lines = output.strip().split('\n')
        for line in lines:
            # nmap output includes lines like: "Nmap scan report for 192.168.1.1"
            if 'Nmap scan report for' in line:
                parts = line.split()
                ip = parts[-1]
                # Remove parentheses if present
                ip = ip.strip('()')

                # Validate IP
                if ip.count('.') == 3:
                    try:
                        octets = ip.split('.')
                        if all(0 <= int(octet) <= 255 for octet in octets):
                            hostname = self._get_hostname(ip)
                            self.devices.append({
                                'ip': ip,
                                'hostname': hostname
                            })
                            self.logger.info(f"Found device: {ip} ({hostname})")
                    except:
                        continue

    def _get_hostname(self, ip: str, vendor: str = None) -> str:
        """Get hostname for an IP address with multiple methods"""
        try:
            # Set socket timeout for faster lookups
            socket.setdefaulttimeout(1.0)

            # Try reverse DNS lookup
            hostname = socket.gethostbyaddr(ip)[0]

            # Don't return IP as hostname
            if hostname != ip:
                # Clean up hostname (remove domain suffix for brevity)
                hostname = hostname.split('.')[0]
                return hostname

        except (socket.herror, socket.gaierror, socket.timeout):
            pass
        except Exception as e:
            self.logger.debug(f"Hostname lookup error for {ip}: {e}")

        # Try mDNS/Avahi lookup for .local hostnames
        try:
            # Try common mDNS patterns
            for suffix in ['.local', '.home', '.lan']:
                try:
                    result = socket.gethostbyname(f"{ip.split('.')[-1]}{suffix}")
                    if result == ip:
                        return f"Device-{ip.split('.')[-1]}"
                except:
                    pass
        except:
            pass

        # Try getfqdn as fallback
        try:
            fqdn = socket.getfqdn(ip)
            if fqdn and fqdn != ip:
                return fqdn.split('.')[0]
        except:
            pass

        # Use vendor name if available
        if vendor and vendor != '(Unknown)':
            return vendor

        # Last resort: descriptive unknown
        return f"Device-{ip.split('.')[-1]}"

    def next_page(self):
        """Move to next page"""
        if len(self.devices) > 0:
            total_pages = (len(self.devices) + self.items_per_page - 1) // self.items_per_page
            self.current_page = (self.current_page + 1) % total_pages

    def prev_page(self):
        """Move to previous page"""
        if len(self.devices) > 0:
            total_pages = (len(self.devices) + self.items_per_page - 1) // self.items_per_page
            self.current_page = (self.current_page - 1 + total_pages) % total_pages

    def _draw_battery_icon(self, draw: ImageDraw.Draw, x: int, y: int, percentage: int, is_charging: bool = False):
        """
        Draw battery icon with percentage and charging indicator
        (Same implementation as MainMenuScreen)
        """
        # Battery body (20x10 rectangle)
        battery_width = 25
        battery_height = 12
        battery_x = x - battery_width - 5
        battery_y = y

        # Draw battery outline
        draw.rectangle(
            [(battery_x, battery_y), (battery_x + battery_width, battery_y + battery_height)],
            outline=0,
            width=2
        )

        # Draw battery terminal (small rectangle on right)
        terminal_width = 2
        terminal_height = 6
        terminal_x = battery_x + battery_width
        terminal_y = battery_y + (battery_height - terminal_height) // 2
        draw.rectangle(
            [(terminal_x, terminal_y), (terminal_x + terminal_width, terminal_y + terminal_height)],
            fill=0
        )

        # Fill battery based on percentage
        if percentage > 0:
            fill_width = int((battery_width - 4) * (percentage / 100))
            draw.rectangle(
                [(battery_x + 2, battery_y + 2),
                 (battery_x + 2 + fill_width, battery_y + battery_height - 2)],
                fill=0
            )

        # Draw charging indicator (lightning bolt) if charging
        if is_charging:
            bolt_x = battery_x + battery_width // 2 - 2
            bolt_y = battery_y + 2
            draw.text((bolt_x, bolt_y), "⚡", font=self.small_font, fill=0)

        # Draw percentage text to the left
        percentage_text = f"{percentage}%"
        try:
            bbox = draw.textbbox((0, 0), percentage_text, font=self.font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(percentage_text) * 8

        text_x = battery_x - text_width - 5
        draw.text((text_x, y), percentage_text, font=self.font, fill=0)

    def render(self) -> Image.Image:
        """Render IP scanner screen"""
        # Create white background
        image = Image.new('1', (self.width, self.height), 1)
        draw = ImageDraw.Draw(image)

        # Draw battery status in top-right corner
        if self.battery_monitor:
            battery_percentage = self.battery_monitor.get_percentage()
            is_charging = self.battery_monitor.is_charging()
            self._draw_battery_icon(draw, self.width - 10, 5, battery_percentage, is_charging)

        # Draw title
        draw.text((40, 30), "IP Scanner", font=self.title_font, fill=0)
        draw.line([(40, 65), (self.width - 40, 65)], fill=0, width=2)

        # Show local IP
        local_ip = get_ip_address()
        draw.text((40, 75), f"Local IP: {local_ip}", font=self.font, fill=0)

        if self.scanning:
            # Show scanning progress
            draw.text((40, 110), f"Scanning network... {self.scan_progress}%", font=self.font, fill=0)

            # Draw progress bar
            bar_width = self.width - 80
            bar_height = 20
            bar_x = 40
            bar_y = 140

            # Outline
            draw.rectangle(
                [(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)],
                outline=0,
                width=2
            )

            # Fill
            fill_width = int(bar_width * (self.scan_progress / 100))
            if fill_width > 0:
                draw.rectangle(
                    [(bar_x + 2, bar_y + 2), (bar_x + fill_width - 2, bar_y + bar_height - 2)],
                    fill=0
                )

            draw.text((40, 170), f"Found {len(self.devices)} devices so far", font=self.small_font, fill=0)

        elif len(self.devices) == 0:
            # No devices found yet
            draw.text((40, 110), "No devices found.", font=self.font, fill=0)
            draw.text((40, 140), "Press button to start scan", font=self.small_font, fill=0)

        else:
            # Display device list with pagination
            total_pages = (len(self.devices) + self.items_per_page - 1) // self.items_per_page

            draw.text((40, 100), f"Found {len(self.devices)} devices (Page {self.current_page + 1}/{total_pages}):", font=self.font, fill=0)

            y = 130
            line_height = 20  # Reduced to 20 to fit 17 items

            # Calculate visible range based on current page
            start_idx = self.current_page * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.devices))

            for i in range(start_idx, end_idx):
                device = self.devices[i]

                # Draw IP address
                draw.text((40, y), device['ip'], font=self.font, fill=0)

                # Draw hostname on the same line (right side)
                hostname = device['hostname']
                if len(hostname) > 35:
                    hostname = hostname[:32] + "..."
                draw.text((200, y), hostname, font=self.small_font, fill=0)

                y += line_height

        # Draw instructions at bottom
        if self.scanning:
            instruction = "Scanning... Please wait"
        elif len(self.devices) > 0:
            instruction = "Press: Next  |  Hold: Scan  |  Menu: Home"
        else:
            instruction = "Hold: Start Scan  |  Menu: Home"

        try:
            bbox = draw.textbbox((0, 0), instruction, font=self.small_font)
            instr_width = bbox[2] - bbox[0]
        except:
            instr_width = len(instruction) * 7

        instr_x = (self.width - instr_width) // 2
        draw.text((instr_x, self.height - 30), instruction, font=self.small_font, fill=0)

        return image


class LibraryScreen:
    """
    Book library/selection screen
    Renders a list of available EPUB files using Pillow
    """

    def __init__(self, width: int = 800, height: int = 480, items_per_page: int = 8, font_size: int = 20, web_port: int = 5000, battery_monitor=None):
        """
        Initialize library screen

        Args:
            width: Screen width
            height: Screen height
            items_per_page: Number of books to show per page
            font_size: Font size for menu text
            web_port: Web server port number
            battery_monitor: Optional BatteryMonitor instance
        """
        self.logger = logging.getLogger(__name__)
        self.width = width
        self.height = height
        self.items_per_page = items_per_page
        self.font_size = font_size
        self.web_port = web_port

        self.current_index = 0
        self.current_page = 0
        self.books: List[Dict[str, str]] = []
        self.battery_monitor = battery_monitor
        self.sleep_enabled = True  # Will be updated from main app

        # Try to load fonts
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            self.title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except Exception:
            self.logger.warning("TrueType fonts not found, using default")
            self.font = ImageFont.load_default()
            self.title_font = ImageFont.load_default()
        # Initialize cover extractor
        from src.utils.cover_extractor import CoverExtractor
        self.cover_extractor = CoverExtractor()
        self.cover_size = (100, 150)  # Larger for better detail on e-ink
        
        # Cache for WiFi/BT status (avoid expensive subprocess calls)
        self._wifi_status = None
        self._wifi_check_time = 0
        self._status_cache_duration = 5  # seconds

    def load_books(self, books_dir: str):
        """
        Load list of EPUB files from directory

        Args:
            books_dir: Path to books directory
        """
        self.books = []

        if not os.path.exists(books_dir):
            self.logger.warning(f"Books directory not found: {books_dir}")
            return

        for filename in os.listdir(books_dir):
            if filename.lower().endswith('.epub'):
                # Remove .epub extension and replace underscores with spaces
                title = filename[:-5].replace('_', ' ')
                self.books.append({
                    'filename': filename,
                    'path': os.path.join(books_dir, filename),
                    'title': title
                })

        self.books.sort(key=lambda x: x['title'].lower())

        # Add Home icon at the end of the list
        self.books.append({
            'filename': '__home__',
            'path': '__home__',
            'title': '🏠 Home'
        })

        self.logger.info(f"Loaded {len(self.books) - 1} books")
    
    def _get_cached_wifi_status(self) -> bool:
        """Get WiFi status with caching to avoid expensive subprocess calls"""
        import time
        now = time.time()
        if now - self._wifi_check_time > self._status_cache_duration:
            self._wifi_status = get_wifi_status()
            self._wifi_check_time = now
        return self._wifi_status if self._wifi_status is not None else False
    
    def _wrap_text(self, text: str, max_width: int, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> list:
        """
        Wrap text to fit within max_width pixels
        
        Args:
            text: Text to wrap
            max_width: Maximum width in pixels
            draw: ImageDraw object for measuring
            font: Font to use for measuring
            
        Returns:
            List of text lines
        """
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            try:
                # Use draw.textbbox for accurate measurement
                bbox = draw.textbbox((0, 0), test_line, font=font)
                width = bbox[2] - bbox[0]
            except:
                # Fallback
                width = len(test_line) * 10
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Single word too long, add anyway
                    lines.append(word)
                    current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines if lines else [text]

    def next_item(self):
        """Move selection to next book (with wrap-around)"""
        if len(self.books) == 0:
            return
        
        self.current_index = (self.current_index + 1) % len(self.books)
        self.current_page = self.current_index // self.items_per_page

    def prev_item(self):
        """Move selection to previous book (with wrap-around)"""
        if len(self.books) == 0:
            return
        
        self.current_index = (self.current_index - 1 + len(self.books)) % len(self.books)
        self.current_page = self.current_index // self.items_per_page

    def get_selected_book(self) -> Optional[Dict[str, str]]:
        """
        Get currently selected book

        Returns:
            Book dictionary or None if no books
        """
        if 0 <= self.current_index < len(self.books):
            return self.books[self.current_index]
        return None

    def _draw_battery_icon(self, draw: ImageDraw.Draw, x: int, y: int, percentage: int, is_charging: bool = False):
        """
        Draw battery icon with percentage and charging indicator

        Args:
            draw: ImageDraw object
            x: X position (top-right corner)
            y: Y position
            percentage: Battery percentage (0-100)
            is_charging: Whether battery is currently charging
        """
        # Battery dimensions
        battery_width = 30
        battery_height = 14
        terminal_width = 2
        terminal_height = 6

        # Clear area before drawing to prevent ghosting/overlap
        # Calculate area needed for "100%" text
        try:
            bbox = draw.textbbox((0, 0), "100%", font=self.font)
            max_text_width = bbox[2] - bbox[0]
            max_text_height = bbox[3] - bbox[1]
        except:
            max_text_width = 40
            max_text_height = 20

        # Define clear area (text + battery + terminal)
        clear_x = x - battery_width - max_text_width - 10
        clear_width = max_text_width + battery_width + terminal_width + 15
        clear_height = max(battery_height, max_text_height) + 4
        
        draw.rectangle(
            [(clear_x, y - 2), (clear_x + clear_width, y + clear_height)],
            fill=1,  # White
            outline=None
        )

        # Draw battery outline
        battery_x = x - battery_width
        draw.rectangle(
            [(battery_x, y), (battery_x + battery_width, y + battery_height)],
            outline=0,
            width=1
        )

        # Draw battery terminal (positive end)
        terminal_x = battery_x + battery_width
        terminal_y = y + (battery_height - terminal_height) // 2
        draw.rectangle(
            [(terminal_x, terminal_y), (terminal_x + terminal_width, terminal_y + terminal_height)],
            fill=0
        )

        # Draw battery fill based on percentage
        fill_width = int((battery_width - 4) * (percentage / 100))
        if fill_width > 0:
            draw.rectangle(
                [(battery_x + 2, y + 2), (battery_x + 2 + fill_width, y + battery_height - 2)],
                fill=0
            )

        # Draw charging indicator (lightning bolt) if charging
        if is_charging:
            # Lightning bolt as a filled polygon (more visible)
            bolt_center_x = battery_x + battery_width // 2
            bolt_center_y = y + battery_height // 2
            # Larger, more visible lightning bolt shape
            bolt_points = [
                (bolt_center_x + 1, bolt_center_y - 5),    # Top tip
                (bolt_center_x - 1, bolt_center_y - 1),     # Upper left
                (bolt_center_x + 2, bolt_center_y - 1),     # Upper right
                (bolt_center_x - 1, bolt_center_y + 5),     # Bottom tip
                (bolt_center_x + 1, bolt_center_y + 1),     # Lower right
                (bolt_center_x - 2, bolt_center_y + 1),     # Lower left
            ]
            # Draw as white (inverted) if battery is very full, black otherwise
            bolt_color = 1 if fill_width > battery_width - 6 else 0
            draw.polygon(bolt_points, fill=bolt_color)

        # Draw percentage text
        percentage_text = f"{percentage}%"
        try:
            bbox = draw.textbbox((0, 0), percentage_text, font=self.font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(percentage_text) * 8

        text_x = battery_x - text_width - 5
        draw.text((text_x, y), percentage_text, font=self.font, fill=0)

    def render(self) -> Image.Image:
        """
        Render library screen to PIL Image

        Returns:
            PIL Image (1-bit, for e-ink display)
        """
        # Create white background
        image = Image.new('1', (self.width, self.height), 1)
        draw = ImageDraw.Draw(image)

        # Draw WiFi status indicator (top left) - only show when ON
        wifi_on = get_wifi_status()
        if wifi_on:
            wifi_icon_x = 10
            wifi_icon_y = 8
            # Draw simple WiFi icon (arcs)
            draw.arc([wifi_icon_x, wifi_icon_y, wifi_icon_x+16, wifi_icon_y+16], 180, 360, fill=0, width=2)
            draw.arc([wifi_icon_x+3, wifi_icon_y+8, wifi_icon_x+13, wifi_icon_y+16], 180, 360, fill=0, width=2)
            draw.arc([wifi_icon_x+6, wifi_icon_y+14, wifi_icon_x+10, wifi_icon_y+16], 180, 360, fill=0, width=2)
            draw.text((wifi_icon_x + 20, wifi_icon_y), "WiFi", font=self.font, fill=0)

        # Draw IP address and port at top center
        ip_address = get_ip_address()
        ip_text = f"{ip_address}:{self.web_port}"
        try:
            # Get text bounding box for centering
            bbox = draw.textbbox((0, 0), ip_text, font=self.font)
            ip_width = bbox[2] - bbox[0]
            ip_x = (self.width - ip_width) // 2
        except:
            ip_x = self.width // 2 - 80
        draw.text((ip_x, 5), ip_text, font=self.font, fill=0)

        # Draw battery status in top-right corner
        if self.battery_monitor:
            battery_percentage = self.battery_monitor.get_percentage()
            is_charging = self.battery_monitor.is_charging()
            self._draw_battery_icon(draw, self.width - 10, 5, battery_percentage, is_charging)

        # Draw title
        draw.text((40, 30), "Library", font=self.title_font, fill=0)
        draw.line([(40, 65), (self.width - 40, 65)], fill=0, width=2)

        if not self.books:
            # No books available
            draw.text((40, 100), "No EPUB files found in books directory", font=self.font, fill=0)
            draw.text((40, 140), "Add .epub files to:", font=self.font, fill=0)
            draw.text((40, 170), "/home/pi/PiBook/books/", font=self.font, fill=0)
            return image

        # Calculate visible range
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.books))

        # Draw book list with covers
        y = 85
        line_height = 160  # Increased for larger covers (100x150) + 4 lines of text

        for i in range(start_idx, end_idx):
            book = self.books[i]
            is_selected = (i == self.current_index)

            # Get or create cover
            cover = self.cover_extractor.get_cover(book['path'], self.cover_size)
            if not cover:
                cover = self.cover_extractor.create_fallback_cover(self.cover_size)
            
            # Draw cover
            cover_x = 40
            cover_y = y
            image.paste(cover, (cover_x, cover_y))
            
            # Draw border around cover
            draw.rectangle(
                [(cover_x, cover_y), (cover_x + self.cover_size[0], cover_y + self.cover_size[1])],
                outline=0,
                width=1
            )

            # Draw selection box around entire item
            if is_selected:
                draw.rectangle(
                    [(30, y - 5), (self.width - 30, y + line_height - 10)],
                    outline=0,
                    width=2
                )

            # Draw book title with wrapping
            title = book['title']
            text_x = cover_x + self.cover_size[0] + 15
            text_y = y + 5
            max_text_width = self.width - text_x - 40
            
            # Wrap text to max 4 lines using draw object
            lines = self._wrap_text(title, max_text_width, draw, self.font)
            if len(lines) > 4:
                # Truncate to 4 lines with ellipsis
                lines = lines[:4]
                if len(lines[3]) > 3:
                    lines[3] = lines[3][:-3] + "..."
            
            # Draw wrapped lines
            for line in lines:
                draw.text((text_x, text_y), line, font=self.font, fill=0)
                text_y += 22  # Line spacing
            
            y += line_height

        # Draw footer with page info
        if len(self.books) > 0:
            footer_text = f"Book {self.current_index + 1} of {len(self.books)}"
            draw.text((40, self.height - 40), footer_text, font=self.font, fill=0)

        # Draw sleep status in bottom-right corner
        sleep_text = "Sleep: ON" if self.sleep_enabled else "Sleep: OFF"
        try:
            bbox = draw.textbbox((0, 0), sleep_text, font=self.font)
            sleep_width = bbox[2] - bbox[0]
            sleep_x = self.width - sleep_width - 40
        except:
            sleep_x = self.width - 140
        draw.text((sleep_x, self.height - 40), sleep_text, font=self.font, fill=0)

        return image


class ReaderScreen:
    """
    Book reading screen
    Uses EPUBRenderer (PyMuPDF) to display pages
    """

    def __init__(self, width: int = 800, height: int = 480, zoom_factor: float = 1.0, dpi: int = 150, cache_size: int = 5, show_page_numbers: bool = True, battery_monitor=None):
        """
        Initialize reader screen

        Args:
            width: Screen width
            height: Screen height
            zoom_factor: Zoom multiplier for content
            dpi: Rendering DPI for quality
            cache_size: Number of pages to cache
            show_page_numbers: Whether to show page numbers
            battery_monitor: Optional BatteryMonitor instance
        """
        self.logger = logging.getLogger(__name__)
        self.width = width
        self.height = height
        self.zoom_factor = zoom_factor
        self.dpi = dpi
        self.show_page_numbers = show_page_numbers

        self.current_page = 0
        self.renderer = None
        self.page_cache = None
        self.epub_path = None
        self.current_book_path = None  # Track current book for progress saving
        self.renderer_type = None
        self.battery_monitor = battery_monitor

        # Helper for page caching
        from src.reader.page_cache import PageCache
        self.PageCache = PageCache
        self.cache_size = cache_size

    def load_epub(self, epub_path: str, zoom_factor: float = None, dpi: int = None):
        """
        Load an EPUB file

        Args:
            epub_path: Path to EPUB file
            zoom_factor: Optional zoom override (uses self.zoom_factor if not provided)
            dpi: Optional DPI override (uses self.dpi if not provided)
        """
        try:
            # Close previous book if open
            if self.renderer:
                self.renderer.close()

            # Use provided settings or defaults
            if zoom_factor is not None:
                self.zoom_factor = zoom_factor
            if dpi is not None:
                self.dpi = dpi

            # Initialize PillowTextRenderer
            from src.reader.pillow_text_renderer import PillowTextRenderer
            self.renderer = PillowTextRenderer(
                epub_path,
                width=self.width,
                height=self.height,
                zoom_factor=self.zoom_factor,
                dpi=self.dpi
            )
            self.renderer_type = 'pillow'
            self.logger.info(f"Using PillowTextRenderer for: {epub_path}")

            self.epub_path = epub_path
            self.current_book_path = os.path.abspath(epub_path)  # Store absolute path for progress tracking

            self.page_cache = self.PageCache(self.cache_size)
            self.current_page = 0

            # Pre-fill cache for first few pages
            if self.page_cache:
                self.page_cache.reset()
                self._update_cache(0)  # Cache surrounding pages

            self.logger.info(f"Loaded EPUB: {epub_path} ({self.renderer.get_page_count()} pages, renderer={self.renderer_type}, zoom={self.zoom_factor}, dpi={self.dpi})")

        except Exception as e:
            self.logger.error(f"Failed to load EPUB: {e}")
            raise

    def next_page(self) -> bool:
        """
        Navigate to next page

        Returns:
            True if navigation occurred, False if on last page
        """
        if not self.renderer:
            return False

        if self.current_page < self.renderer.get_page_count() - 1:
            self.current_page += 1
            self.logger.debug(f"Next page: {self.current_page}")
            return True

        self.logger.debug("Already on last page")
        return False

    def prev_page(self) -> bool:
        """
        Navigate to previous page

        Returns:
            True if navigation occurred, False if on first page
        """
        if not self.renderer:
            return False

        if self.current_page > 0:
            self.current_page -= 1
            self.logger.debug(f"Previous page: {self.current_page + 1}/{self.renderer.get_total_pages()}")
            return True
        return False

    def go_to_page(self, page_number: int):
        """
        Jump to specific page number

        Args:
            page_number: Page number to jump to (0-indexed)
        """
        if not self.renderer:
            return

        total_pages = self.renderer.get_page_count()
        if 0 <= page_number < total_pages:
            self.current_page = page_number
            self.logger.info(f"Jumped to page {page_number + 1}/{total_pages}")

    def cache_page(self, page_number: int):
        """
        Pre-cache a specific page

        Args:
            page_number: Page number to cache (0-indexed)
        """
        if not self.renderer:
            return

        total_pages = self.renderer.get_page_count()
        if 0 <= page_number < total_pages:
            # Render and cache the page
            img = self.renderer.render_page(page_number, show_page_number=self.show_page_numbers)
            self.page_cache.put(page_number, img)
            self.logger.debug(f"Cached page {page_number + 1}/{total_pages}")

    def show_loading_progress(self, percentage: int, message: str = "Loading..."):
        """
        Display loading progress bar on screen

        Args:
            percentage: Progress percentage (0-100)
            message: Loading message to display

        Returns:
            PIL Image with progress bar
        """
        image = Image.new('1', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # Load font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Draw title
        try:
            bbox = draw.textbbox((0, 0), message, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (self.width - text_width) // 2
        except:
            text_x = self.width // 2 - 50

        draw.text((text_x, self.height // 2 - 60), message, font=font, fill=0)

        # Draw progress bar
        bar_width = 400
        bar_height = 30
        bar_x = (self.width - bar_width) // 2
        bar_y = self.height // 2

        # Outline
        draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
                       outline=0, width=2)

        # Fill based on percentage
        fill_width = int((bar_width - 4) * (percentage / 100))
        if fill_width > 0:
            draw.rectangle([bar_x + 2, bar_y + 2,
                           bar_x + 2 + fill_width, bar_y + bar_height - 2],
                           fill=0)

        # Percentage text
        pct_text = f"{percentage}%"
        try:
            bbox = draw.textbbox((0, 0), pct_text, font=small_font)
            pct_width = bbox[2] - bbox[0]
            pct_x = (self.width - pct_width) // 2
        except:
            pct_x = self.width // 2 - 20

        draw.text((pct_x, bar_y + bar_height + 20), pct_text, font=small_font, fill=0)

        return image
    def _draw_battery_icon(self, draw: ImageDraw.Draw, x: int, y: int, percentage: int, is_charging: bool = False):
        """
        Draw battery icon with percentage and charging indicator

        Args:
            draw: ImageDraw object
            x: X position (top-right corner)
            y: Y position
            percentage: Battery percentage (0-100)
            is_charging: Whether battery is currently charging
        """
        # Battery dimensions
        battery_width = 30
        battery_height = 14
        terminal_width = 2
        terminal_height = 6

        # Clear area before drawing to prevent ghosting/overlap
        # Use default font as used in this method
        try:
            # We need to load the default font here for measurement
            # (It is also loaded later for drawing, which is fine)
            font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), "100%", font=font)
            max_text_width = bbox[2] - bbox[0]
            max_text_height = bbox[3] - bbox[1]
        except:
            max_text_width = 40
            max_text_height = 20

        # Define clear area (text + battery + terminal)
        clear_x = x - battery_width - max_text_width - 10
        clear_width = max_text_width + battery_width + terminal_width + 15
        clear_height = max(battery_height, max_text_height) + 4
        
        draw.rectangle(
            [(clear_x, y - 2), (clear_x + clear_width, y + clear_height)],
            fill=1,  # White
            outline=None
        )

        # Draw battery outline
        battery_x = x - battery_width
        draw.rectangle(
            [(battery_x, y), (battery_x + battery_width, y + battery_height)],
            outline=0,
            width=1
        )

        # Draw battery terminal (positive end)
        terminal_x = battery_x + battery_width
        terminal_y = y + (battery_height - terminal_height) // 2
        draw.rectangle(
            [(terminal_x, terminal_y), (terminal_x + terminal_width, terminal_y + terminal_height)],
            fill=0
        )

        # Draw battery fill based on percentage
        fill_width = int((battery_width - 4) * (percentage / 100))
        if fill_width > 0:
            draw.rectangle(
                [(battery_x + 2, y + 2), (battery_x + 2 + fill_width, y + battery_height - 2)],
                fill=0
            )

        # Draw charging indicator (lightning bolt) if charging
        if is_charging:
            # Lightning bolt as a filled polygon (more visible)
            bolt_center_x = battery_x + battery_width // 2
            bolt_center_y = y + battery_height // 2
            # Larger, more visible lightning bolt shape
            bolt_points = [
                (bolt_center_x + 1, bolt_center_y - 5),    # Top tip
                (bolt_center_x - 1, bolt_center_y - 1),     # Upper left
                (bolt_center_x + 2, bolt_center_y - 1),     # Upper right
                (bolt_center_x - 1, bolt_center_y + 5),     # Bottom tip
                (bolt_center_x + 1, bolt_center_y + 1),     # Lower right
                (bolt_center_x - 2, bolt_center_y + 1),     # Lower left
            ]
            # Draw as white (inverted) if battery is very full, black otherwise
            bolt_color = 1 if fill_width > battery_width - 6 else 0
            draw.polygon(bolt_points, fill=bolt_color)

        # Draw percentage text
        percentage_text = f"{percentage}%"
        # Use default font for battery percentage
        font = ImageFont.load_default()
        try:
            bbox = draw.textbbox((0, 0), percentage_text, font=font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(percentage_text) * 8

        text_x = battery_x - text_width - 5
        draw.text((text_x, y), percentage_text, font=font, fill=0)

    def get_current_image(self) -> Image.Image:
        """
        Get current page as PIL Image (with caching)

        Returns:
            PIL Image (1-bit, for e-ink display)
        """
        if not self.renderer:
            # Return blank page if no book loaded
            return Image.new('1', (self.width, self.height), 1)

        # Check cache first
        cached = self.page_cache.get(self.current_page)
        if cached:
            return cached

        # Render and cache
        img = self.renderer.render_page(self.current_page, show_page_number=self.show_page_numbers)
        self.page_cache.put(self.current_page, img)

        # Add battery overlay if monitor available
        if self.battery_monitor:
            # Create a copy to avoid modifying cached image
            img = img.copy()
            draw = ImageDraw.Draw(img)
            battery_percentage = self.battery_monitor.get_percentage()
            is_charging = self.battery_monitor.is_charging()
            self._draw_battery_icon(draw, self.width - 10, 5, battery_percentage, is_charging)

        return img

    def get_page_info(self) -> Dict[str, any]:
        """
        Get information about current page

        Returns:
            Dictionary with page number, total pages, etc.
        """
        if not self.renderer:
            return {'current': 0, 'total': 0}

        return {
            'current': self.current_page + 1,  # 1-indexed for display
            'total': self.renderer.get_page_count(),
            'cache_stats': self.page_cache.get_stats() if self.page_cache else {}
        }

    def close(self):
        """Close current book and clean up"""
        if self.renderer:
            self.renderer.close()
            self.renderer = None

        if self.page_cache:
            self.page_cache.clear()
            self.page_cache = None

        self.logger.info("Reader closed")


class ToDoScreen:
    """
    To Do list screen for managing tasks
    """

    def __init__(self, width: int = 800, height: int = 480, font_size: int = 18, battery_monitor=None):
        """
        Initialize To Do screen

        Args:
            width: Screen width
            height: Screen height
            font_size: Base font size
            battery_monitor: Optional BatteryMonitor instance
        """
        self.width = width
        self.height = height
        self.font_size = font_size
        self.battery_monitor = battery_monitor
        self.logger = logging.getLogger(__name__)

        # Load fonts
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", font_size)
            self.title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 28)
            self.item_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 16)
        except:
            self.font = ImageFont.load_default()
            self.title_font = ImageFont.load_default()
            self.item_font = ImageFont.load_default()

        # To do items: list of dicts with 'text' and 'completed' keys
        self.todos: List[Dict[str, Any]] = []
        self.current_index = 0  # Currently selected item
        self.items_per_page = 15  # Number of items visible per page
        self.current_page = 0

        # Load todos from file
        self.todos_file = "data/todos.json"
        self._load_todos()

    def _load_todos(self):
        """Load todos from JSON file"""
        import os
        import json

        if os.path.exists(self.todos_file):
            try:
                with open(self.todos_file, 'r') as f:
                    self.todos = json.load(f)
                self.logger.info(f"Loaded {len(self.todos)} todos from {self.todos_file}")
            except Exception as e:
                self.logger.error(f"Failed to load todos: {e}")
                self.todos = []
        else:
            self.logger.info("No todos file found, starting with empty list")
            self.todos = []

    def _save_todos(self):
        """Save todos to JSON file"""
        import os
        import json

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.todos_file), exist_ok=True)

        try:
            with open(self.todos_file, 'w') as f:
                json.dump(self.todos, f, indent=2)
            self.logger.info(f"Saved {len(self.todos)} todos to {self.todos_file}")
        except Exception as e:
            self.logger.error(f"Failed to save todos: {e}")

    def add_todo(self, text: str):
        """Add a new todo item"""
        self.todos.append({
            'text': text,
            'completed': False
        })
        self._save_todos()
        self.logger.info(f"Added todo: {text}")

    def toggle_todo(self):
        """Toggle completion status of current todo"""
        if 0 <= self.current_index < len(self.todos):
            self.todos[self.current_index]['completed'] = not self.todos[self.current_index]['completed']
            self._save_todos()
            status = "completed" if self.todos[self.current_index]['completed'] else "uncompleted"
            self.logger.info(f"Marked todo as {status}: {self.todos[self.current_index]['text']}")

    def delete_todo(self):
        """Delete current todo item"""
        if 0 <= self.current_index < len(self.todos):
            deleted = self.todos.pop(self.current_index)
            self._save_todos()
            # Adjust current index if needed
            if self.current_index >= len(self.todos) and len(self.todos) > 0:
                self.current_index = len(self.todos) - 1
            self.logger.info(f"Deleted todo: {deleted['text']}")

    def next_item(self):
        """Move to next todo item"""
        if len(self.todos) > 0:
            self.current_index = (self.current_index + 1) % len(self.todos)
            # Update page if needed
            self.current_page = self.current_index // self.items_per_page

    def prev_item(self):
        """Move to previous todo item"""
        if len(self.todos) > 0:
            self.current_index = (self.current_index - 1) % len(self.todos)
            # Update page if needed
            self.current_page = self.current_index // self.items_per_page

    def render(self) -> Image.Image:
        """
        Render the To Do screen

        Returns:
            PIL Image of the screen
        """
        # Create blank image (white background)
        image = Image.new('RGB', (self.width, self.height), 'white')
        draw = ImageDraw.Draw(image)

        y_offset = 10

        # Draw title
        title = "To Do List"
        title_bbox = draw.textbbox((0, 0), title, font=self.title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.width - title_width) // 2
        draw.text((title_x, y_offset), title, fill='black', font=self.title_font)
        y_offset += 40

        # Draw battery status if available
        if self.battery_monitor:
            try:
                battery_pct = self.battery_monitor.get_battery_percentage()
                charging = self.battery_monitor.is_charging()

                battery_text = f"{battery_pct}%"
                if charging:
                    battery_text += " ⚡"

                battery_bbox = draw.textbbox((0, 0), battery_text, font=self.item_font)
                battery_width = battery_bbox[2] - battery_bbox[0]
                draw.text((self.width - battery_width - 10, 10), battery_text, fill='black', font=self.item_font)
            except Exception as e:
                self.logger.warning(f"Failed to get battery status: {e}")

        # Draw separator line
        draw.line([(10, y_offset), (self.width - 10, y_offset)], fill='black', width=2)
        y_offset += 10

        # If no todos, show message
        if len(self.todos) == 0:
            msg = "No tasks yet"
            msg_bbox = draw.textbbox((0, 0), msg, font=self.font)
            msg_width = msg_bbox[2] - msg_bbox[0]
            draw.text(((self.width - msg_width) // 2, self.height // 2), msg, fill='gray', font=self.font)
        else:
            # Draw todo items
            line_height = 24
            start_idx = self.current_page * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.todos))

            for i in range(start_idx, end_idx):
                todo = self.todos[i]

                # Highlight current selection
                if i == self.current_index:
                    # Draw selection background
                    draw.rectangle(
                        [(10, y_offset - 2), (self.width - 10, y_offset + line_height - 2)],
                        fill='lightgray'
                    )

                # Draw checkbox
                checkbox_x = 20
                checkbox_y = y_offset
                checkbox_size = 16
                draw.rectangle(
                    [(checkbox_x, checkbox_y), (checkbox_x + checkbox_size, checkbox_y + checkbox_size)],
                    outline='black',
                    width=2
                )

                # Draw checkmark if completed
                if todo['completed']:
                    draw.text((checkbox_x + 2, checkbox_y - 2), '✓', fill='black', font=self.font)

                # Draw todo text
                text_x = checkbox_x + checkbox_size + 10
                text_color = 'gray' if todo['completed'] else 'black'

                # Truncate text if too long
                max_width = self.width - text_x - 20
                text = todo['text']
                text_bbox = draw.textbbox((0, 0), text, font=self.item_font)
                text_width = text_bbox[2] - text_bbox[0]

                while text_width > max_width and len(text) > 0:
                    text = text[:-1]
                    text_bbox = draw.textbbox((0, 0), text + "...", font=self.item_font)
                    text_width = text_bbox[2] - text_bbox[0]

                if len(text) < len(todo['text']):
                    text += "..."

                draw.text((text_x, checkbox_y), text, fill=text_color, font=self.item_font)

                y_offset += line_height

            # Draw page indicator if multiple pages
            total_pages = (len(self.todos) + self.items_per_page - 1) // self.items_per_page
            if total_pages > 1:
                page_info = f"Page {self.current_page + 1}/{total_pages}"
                page_bbox = draw.textbbox((0, 0), page_info, font=self.item_font)
                page_width = page_bbox[2] - page_bbox[0]
                draw.text(
                    ((self.width - page_width) // 2, self.height - 30),
                    page_info,
                    fill='black',
                    font=self.item_font
                )

        # Draw help text at bottom
        help_text = "Next: Navigate | Hold: Toggle | Menu: Home"
        help_bbox = draw.textbbox((0, 0), help_text, font=self.item_font)
        help_width = help_bbox[2] - help_bbox[0]
        draw.text(
            ((self.width - help_width) // 2, self.height - 10),
            help_text,
            fill='gray',
            font=self.item_font
        )

        return image
