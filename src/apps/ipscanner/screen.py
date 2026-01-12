"""
IP Scanner Screen

E-ink display screen for scanning and displaying network devices.
"""

import logging
import socket
import subprocess
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont


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
            self._ping_sweep(network_prefix)

        except Exception as e:
            self.logger.error(f"Network scan failed: {e}", exc_info=True)
        finally:
            self.scanning = False
            self.scan_progress = 100

    def _parse_arp_scan_output(self, output: str):
        """Parse arp-scan output"""
        for line in output.split('\n'):
            # Skip header and footer lines
            if '\t' not in line or line.startswith('Interface:') or line.startswith('Starting'):
                continue

            parts = line.split('\t')
            if len(parts) >= 2:
                ip = parts[0].strip()
                mac = parts[1].strip()
                # Get manufacturer from third column if available
                manufacturer = parts[2].strip() if len(parts) >= 3 else "Unknown"

                # Skip invalid IPs
                if not ip or ip == "0.0.0.0":
                    continue

                self.devices.append({
                    'ip': ip,
                    'mac': mac,
                    'name': manufacturer
                })

        self.logger.info(f"Found {len(self.devices)} devices via arp-scan")

    def _parse_nmap_output(self, output: str):
        """Parse nmap output"""
        current_ip = None
        for line in output.split('\n'):
            if 'Nmap scan report for' in line:
                # Extract IP address
                parts = line.split()
                if len(parts) >= 5:
                    current_ip = parts[-1].strip('()')
            elif 'MAC Address:' in line and current_ip:
                # Extract MAC and manufacturer
                parts = line.split('MAC Address:')[1].strip().split('(')
                mac = parts[0].strip()
                manufacturer = parts[1].strip(')') if len(parts) > 1 else "Unknown"

                self.devices.append({
                    'ip': current_ip,
                    'mac': mac,
                    'name': manufacturer
                })
                current_ip = None

        self.logger.info(f"Found {len(self.devices)} devices via nmap")

    def _ping_sweep(self, network_prefix: str):
        """Ping sweep fallback method"""
        import concurrent.futures

        def ping_host(ip):
            try:
                result = subprocess.run(
                    ['ping', '-c', '1', '-W', '1', ip],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    return ip
            except:
                pass
            return None

        # Ping all IPs in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for i in range(1, 255):
                ip = f"{network_prefix}.{i}"
                futures.append(executor.submit(ping_host, ip))
                self.scan_progress = 20 + int((i / 254) * 80)

            for future in concurrent.futures.as_completed(futures):
                ip = future.result()
                if ip:
                    self.devices.append({
                        'ip': ip,
                        'mac': 'Unknown',
                        'name': 'Unknown'
                    })

        self.logger.info(f"Found {len(self.devices)} devices via ping sweep")

    def next_page(self):
        """Move to next page"""
        total_pages = (len(self.devices) + self.items_per_page - 1) // self.items_per_page
        if self.current_page < total_pages - 1:
            self.current_page += 1

    def prev_page(self):
        """Move to previous page"""
        if self.current_page > 0:
            self.current_page -= 1

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
            bolt_center_x = battery_x + battery_width // 2
            bolt_center_y = battery_y + battery_height // 2
            # Larger, more visible lightning bolt
            bolt_points = [
                (bolt_center_x + 2, bolt_center_y - 6),    # Top tip
                (bolt_center_x - 2, bolt_center_y - 1),    # Upper left
                (bolt_center_x + 3, bolt_center_y - 1),    # Upper right
                (bolt_center_x - 2, bolt_center_y + 6),    # Bottom tip
                (bolt_center_x + 2, bolt_center_y + 1),    # Lower right
                (bolt_center_x - 3, bolt_center_y + 1),    # Lower left
            ]
            # Draw white bolt with black outline for visibility
            draw.polygon(bolt_points, fill=1, outline=0)

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
        """
        Render the IP scanner screen

        Returns:
            PIL Image of the screen
        """
        # Create image
        image = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # Draw title
        title = "Network Scanner"
        title_bbox = draw.textbbox((0, 0), title, font=self.title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((self.width - title_width) // 2, 10), title, font=self.title_font, fill=0)

        # Draw battery status if available
        if self.battery_monitor:
            try:
                battery_pct = self.battery_monitor.get_percentage()
                charging = self.battery_monitor.is_charging()
                self._draw_battery_icon(draw, self.width - 10, 10, battery_pct, charging)
            except Exception as e:
                self.logger.warning(f"Failed to get battery status: {e}")

        # Draw local IP
        local_ip = get_ip_address()
        ip_text = f"Your IP: {local_ip}"
        draw.text((10, 45), ip_text, font=self.font, fill=0)

        # Draw scan status or results
        y_offset = 75

        if self.scanning:
            # Show scanning progress
            status_text = f"Scanning... {self.scan_progress}%"
            draw.text((10, y_offset), status_text, font=self.font, fill=0)

            # Draw progress bar
            bar_width = self.width - 40
            bar_height = 20
            bar_x = 20
            bar_y = y_offset + 30

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

        elif len(self.devices) == 0:
            # No devices found
            message = "No devices found. Press SELECT to scan."
            msg_bbox = draw.textbbox((0, 0), message, font=self.font)
            msg_width = msg_bbox[2] - msg_bbox[0]
            draw.text(((self.width - msg_width) // 2, self.height // 2), message, font=self.font, fill=0)

        else:
            # Display devices
            devices_text = f"Found {len(self.devices)} device(s):"
            draw.text((10, y_offset), devices_text, font=self.font, fill=0)
            y_offset += 30

            # Calculate pagination
            start_idx = self.current_page * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.devices))

            # Draw device list
            for i in range(start_idx, end_idx):
                device = self.devices[i]
                device_text = f"{device['ip']}"
                if device['name'] != 'Unknown':
                    device_text += f" - {device['name']}"

                draw.text((20, y_offset), device_text, font=self.small_font, fill=0)
                y_offset += 22

            # Draw page indicator if multiple pages
            total_pages = (len(self.devices) + self.items_per_page - 1) // self.items_per_page
            if total_pages > 1:
                page_text = f"Page {self.current_page + 1}/{total_pages}"
                page_bbox = draw.textbbox((0, 0), page_text, font=self.small_font)
                page_width = page_bbox[2] - page_bbox[0]
                draw.text(((self.width - page_width) // 2, self.height - 50), page_text, font=self.small_font, fill=0)

        # Draw instructions
        instruction = "SELECT: Scan | NEXT/PREV: Page | HOLD GPIO5: Menu"
        try:
            instr_bbox = draw.textbbox((0, 0), instruction, font=self.small_font)
            instr_width = instr_bbox[2] - instr_bbox[0]
        except:
            instr_width = len(instruction) * 7

        instr_x = (self.width - instr_width) // 2
        draw.text((instr_x, self.height - 30), instruction, font=self.small_font, fill=0)

        return image
