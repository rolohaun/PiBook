"""
Klipper Screen

E-ink display screen for discovering and monitoring Klipper/MainsailOS 3D printers.
"""

import logging
import socket
import subprocess
import urllib.request
import json
from typing import List, Dict, Optional
from PIL import Image, ImageDraw, ImageFont


class KlipperScreen:
    """
    Klipper screen - discovers and monitors 3D printers running Klipper/MainsailOS
    """

    def __init__(self, width: int = 800, height: int = 480, font_size: int = 18, battery_monitor=None):
        """
        Initialize Klipper screen

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
            self.large_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except:
            self.font = ImageFont.load_default()
            self.title_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()
            self.large_font = ImageFont.load_default()

        # Scan state
        self.printers: List[Dict] = []
        self.scanning = False
        self.scan_progress = 0
        self.current_index = 0  # Currently selected printer
        self.items_per_page = 3  # Printers per page (more info per printer)

    def start_scan(self):
        """Start scanning for Klipper printers in background"""
        import threading
        if not self.scanning:
            self.scanning = True
            self.scan_progress = 0
            self.printers = []
            thread = threading.Thread(target=self._scan_for_printers, daemon=True)
            thread.start()

    def _check_port(self, ip: str, port: int, timeout: float = 1) -> bool:
        """Check if a port is open on the given IP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False

    def _get_local_ip(self) -> str:
        """Get the Pi's local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "No Network"

    def _scan_for_printers(self):
        """Scan the local network for Klipper printers"""
        try:
            local_ip = self._get_local_ip()
            if local_ip == "No Network":
                self.scanning = False
                return

            # Extract network prefix
            ip_parts = local_ip.split('.')
            network_prefix = '.'.join(ip_parts[:3])

            self.logger.info(f"Scanning for Klipper printers on {network_prefix}.0/24")
            self.scan_progress = 5

            # Scan all IPs for port 7125 (Moonraker API)
            import concurrent.futures

            def check_klipper(ip):
                # Check for Moonraker API port
                if self._check_port(ip, 7125, timeout=0.5):
                    return ip
                return None

            found_ips = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                futures = {}
                for i in range(1, 255):
                    ip = f"{network_prefix}.{i}"
                    futures[executor.submit(check_klipper, ip)] = ip

                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    completed += 1
                    self.scan_progress = 5 + int((completed / 254) * 70)
                    ip = future.result()
                    if ip:
                        found_ips.append(ip)
                        self.logger.info(f"Found Klipper at {ip}")

            # Get detailed info for each printer
            self.scan_progress = 80
            for i, ip in enumerate(found_ips):
                printer_info = self._get_printer_info(ip)
                if printer_info:
                    self.printers.append(printer_info)
                self.scan_progress = 80 + int(((i + 1) / len(found_ips)) * 20) if found_ips else 100

            self.logger.info(f"Found {len(self.printers)} Klipper printers")

        except Exception as e:
            self.logger.error(f"Klipper scan failed: {e}", exc_info=True)
        finally:
            self.scanning = False
            self.scan_progress = 100

    def _get_hostname(self, ip: str) -> str:
        """Get hostname for an IP using avahi-resolve"""
        try:
            result = subprocess.run(
                ['avahi-resolve', '-a', ip],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split('\t')
                if len(parts) >= 2:
                    return parts[1].strip()
        except:
            pass
        return ""

    def _get_printer_info(self, ip: str) -> Optional[Dict]:
        """Get detailed printer info from Moonraker API"""
        try:
            base_url = f"http://{ip}:7125"
            hostname = self._get_hostname(ip)

            printer_info = {
                'ip': ip,
                'hostname': hostname or ip,
                'state': 'unknown',
                'klipper_version': None,
                'extruder_temp': None,
                'extruder_target': None,
                'bed_temp': None,
                'bed_target': None,
                'progress': None,
                'filename': None
            }

            # Get server info
            try:
                req = urllib.request.Request(f"{base_url}/server/info", method='GET')
                with urllib.request.urlopen(req, timeout=3) as response:
                    data = json.loads(response.read().decode())
                    if 'result' in data:
                        printer_info['klipper_version'] = data['result'].get('klippy_state', 'unknown')
            except Exception as e:
                self.logger.debug(f"Failed to get server info from {ip}: {e}")

            # Get printer state
            try:
                req = urllib.request.Request(f"{base_url}/printer/info", method='GET')
                with urllib.request.urlopen(req, timeout=3) as response:
                    data = json.loads(response.read().decode())
                    if 'result' in data:
                        printer_info['state'] = data['result'].get('state', 'unknown')
            except Exception as e:
                self.logger.debug(f"Failed to get printer info from {ip}: {e}")

            # Get temperature and print status
            try:
                req = urllib.request.Request(
                    f"{base_url}/printer/objects/query?extruder&heater_bed&print_stats&virtual_sdcard",
                    method='GET'
                )
                with urllib.request.urlopen(req, timeout=3) as response:
                    data = json.loads(response.read().decode())
                    if 'result' in data and 'status' in data['result']:
                        status = data['result']['status']

                        if 'extruder' in status:
                            printer_info['extruder_temp'] = status['extruder'].get('temperature', 0)
                            printer_info['extruder_target'] = status['extruder'].get('target', 0)

                        if 'heater_bed' in status:
                            printer_info['bed_temp'] = status['heater_bed'].get('temperature', 0)
                            printer_info['bed_target'] = status['heater_bed'].get('target', 0)

                        if 'print_stats' in status:
                            print_stats = status['print_stats']
                            state = print_stats.get('state', '')
                            if state == 'printing':
                                printer_info['state'] = 'printing'
                                printer_info['filename'] = print_stats.get('filename', '')
                            elif state == 'complete':
                                printer_info['state'] = 'complete'
                            elif state == 'standby':
                                printer_info['state'] = 'ready'
                            elif state == 'paused':
                                printer_info['state'] = 'paused'

                        if 'virtual_sdcard' in status:
                            printer_info['progress'] = status['virtual_sdcard'].get('progress', 0)

            except Exception as e:
                self.logger.debug(f"Failed to get temperature data from {ip}: {e}")

            return printer_info

        except Exception as e:
            self.logger.error(f"Failed to get Klipper info from {ip}: {e}")
            return None

    def refresh_printer(self, index: int):
        """Refresh info for a specific printer"""
        if 0 <= index < len(self.printers):
            ip = self.printers[index]['ip']
            new_info = self._get_printer_info(ip)
            if new_info:
                self.printers[index] = new_info

    def next_item(self):
        """Move to next printer"""
        if len(self.printers) > 0:
            self.current_index = (self.current_index + 1) % len(self.printers)

    def prev_item(self):
        """Move to previous printer"""
        if len(self.printers) > 0:
            self.current_index = (self.current_index - 1) % len(self.printers)

    def next_page(self):
        """Move to next page of printers"""
        if len(self.printers) > self.items_per_page:
            total_pages = (len(self.printers) + self.items_per_page - 1) // self.items_per_page
            current_page = self.current_index // self.items_per_page
            next_page = (current_page + 1) % total_pages
            self.current_index = next_page * self.items_per_page

    def prev_page(self):
        """Move to previous page of printers"""
        if len(self.printers) > self.items_per_page:
            total_pages = (len(self.printers) + self.items_per_page - 1) // self.items_per_page
            current_page = self.current_index // self.items_per_page
            prev_page = (current_page - 1) % total_pages
            self.current_index = prev_page * self.items_per_page

    def get_selected_printer(self) -> Optional[Dict]:
        """Get currently selected printer"""
        if 0 <= self.current_index < len(self.printers):
            return self.printers[self.current_index]
        return None

    def _draw_battery_icon(self, draw: ImageDraw.Draw, x: int, y: int, percentage: int, is_charging: bool = False):
        """Draw battery icon with percentage"""
        battery_width = 25
        battery_height = 12
        battery_x = x - battery_width - 5
        battery_y = y

        draw.rectangle(
            [(battery_x, battery_y), (battery_x + battery_width, battery_y + battery_height)],
            outline=0,
            width=2
        )

        terminal_width = 2
        terminal_height = 6
        terminal_x = battery_x + battery_width
        terminal_y = battery_y + (battery_height - terminal_height) // 2
        draw.rectangle(
            [(terminal_x, terminal_y), (terminal_x + terminal_width, terminal_y + terminal_height)],
            fill=0
        )

        if percentage > 0:
            fill_width = int((battery_width - 4) * (percentage / 100))
            draw.rectangle(
                [(battery_x + 2, battery_y + 2),
                 (battery_x + 2 + fill_width, battery_y + battery_height - 2)],
                fill=0
            )

        if is_charging:
            bolt_center_x = battery_x + battery_width // 2
            bolt_center_y = battery_y + battery_height // 2
            bolt_points = [
                (bolt_center_x + 2, bolt_center_y - 6),
                (bolt_center_x - 2, bolt_center_y - 1),
                (bolt_center_x + 3, bolt_center_y - 1),
                (bolt_center_x - 2, bolt_center_y + 6),
                (bolt_center_x + 2, bolt_center_y + 1),
                (bolt_center_x - 3, bolt_center_y + 1),
            ]
            draw.polygon(bolt_points, fill=1, outline=0)

        percentage_text = f"{percentage}%"
        try:
            bbox = draw.textbbox((0, 0), percentage_text, font=self.font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(percentage_text) * 8

        text_x = battery_x - text_width - 5
        draw.text((text_x, y), percentage_text, font=self.font, fill=0)

    def render(self) -> Image.Image:
        """Render the Klipper screen"""
        image = Image.new('1', (self.width, self.height), 1)  # 1-bit, white background
        draw = ImageDraw.Draw(image)

        # Draw title
        title = "Klipper Printers"
        title_bbox = draw.textbbox((0, 0), title, font=self.title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((self.width - title_width) // 2, 10), title, font=self.title_font, fill=0)

        # Draw battery status
        if self.battery_monitor:
            try:
                battery_pct = self.battery_monitor.get_percentage()
                charging = self.battery_monitor.is_charging()
                self._draw_battery_icon(draw, self.width - 10, 10, battery_pct, charging)
            except Exception as e:
                self.logger.warning(f"Failed to get battery status: {e}")

        y_offset = 50

        # Scanning state with progress bar
        if self.scanning:
            status_text = f"Scanning for printers... {self.scan_progress}%"
            draw.text((10, y_offset), status_text, font=self.font, fill=0)

            # Draw progress bar
            bar_width = self.width - 40
            bar_height = 20
            bar_x = 20
            bar_y = y_offset + 30

            draw.rectangle(
                [(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)],
                outline=0,
                width=2
            )

            fill_width = int(bar_width * (self.scan_progress / 100))
            if fill_width > 0:
                draw.rectangle(
                    [(bar_x + 2, bar_y + 2), (bar_x + fill_width - 2, bar_y + bar_height - 2)],
                    fill=0
                )

            # Show found count
            found_text = f"Found {len(self.printers)} printer(s) so far..."
            draw.text((10, bar_y + 35), found_text, font=self.small_font, fill=0)

        elif len(self.printers) == 0:
            # No printers found
            message = "No Klipper printers found."
            msg_bbox = draw.textbbox((0, 0), message, font=self.font)
            msg_width = msg_bbox[2] - msg_bbox[0]
            draw.text(((self.width - msg_width) // 2, self.height // 2 - 20), message, font=self.font, fill=0)

            hint = "Press button to scan network."
            hint_bbox = draw.textbbox((0, 0), hint, font=self.small_font)
            hint_width = hint_bbox[2] - hint_bbox[0]
            draw.text(((self.width - hint_width) // 2, self.height // 2 + 10), hint, font=self.small_font, fill=0)

        else:
            # Display printers
            found_text = f"Found {len(self.printers)} printer(s):"
            draw.text((10, y_offset), found_text, font=self.font, fill=0)
            y_offset += 35

            # Calculate pagination
            current_page = self.current_index // self.items_per_page
            start_idx = current_page * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.printers))

            # Draw printer cards
            card_height = 120
            for i in range(start_idx, end_idx):
                printer = self.printers[i]
                is_selected = (i == self.current_index)

                # Draw selection indicator
                if is_selected:
                    draw.rectangle(
                        [(5, y_offset - 5), (self.width - 5, y_offset + card_height)],
                        outline=0,
                        width=3
                    )

                # Printer name/hostname
                name = printer['hostname'] or printer['ip']
                draw.text((15, y_offset), name, font=self.large_font, fill=0)

                # State badge
                state = printer['state']
                state_x = self.width - 100
                draw.text((state_x, y_offset), f"[{state}]", font=self.small_font, fill=0)

                # IP address
                draw.text((15, y_offset + 25), f"IP: {printer['ip']}", font=self.small_font, fill=0)

                # Temperatures
                if printer['extruder_temp'] is not None:
                    temp_text = f"Extruder: {printer['extruder_temp']:.1f}C / {printer['extruder_target']:.1f}C"
                    draw.text((15, y_offset + 45), temp_text, font=self.small_font, fill=0)

                if printer['bed_temp'] is not None:
                    bed_text = f"Bed: {printer['bed_temp']:.1f}C / {printer['bed_target']:.1f}C"
                    draw.text((15, y_offset + 65), bed_text, font=self.small_font, fill=0)

                # Print progress if printing
                if state == 'printing' and printer['progress'] is not None:
                    progress_pct = printer['progress'] * 100
                    progress_text = f"Progress: {progress_pct:.1f}%"
                    draw.text((15, y_offset + 85), progress_text, font=self.small_font, fill=0)

                    # Small progress bar
                    prog_bar_x = 150
                    prog_bar_width = 200
                    prog_bar_height = 12
                    draw.rectangle(
                        [(prog_bar_x, y_offset + 87), (prog_bar_x + prog_bar_width, y_offset + 87 + prog_bar_height)],
                        outline=0,
                        width=1
                    )
                    fill_w = int(prog_bar_width * printer['progress'])
                    if fill_w > 0:
                        draw.rectangle(
                            [(prog_bar_x + 1, y_offset + 88), (prog_bar_x + fill_w - 1, y_offset + 87 + prog_bar_height - 1)],
                            fill=0
                        )

                    if printer['filename']:
                        draw.text((prog_bar_x + prog_bar_width + 10, y_offset + 85),
                                  printer['filename'][:20], font=self.small_font, fill=0)

                y_offset += card_height + 10

            # Page indicator
            total_pages = (len(self.printers) + self.items_per_page - 1) // self.items_per_page
            if total_pages > 1:
                page_text = f"Page {current_page + 1}/{total_pages}"
                page_bbox = draw.textbbox((0, 0), page_text, font=self.small_font)
                page_width = page_bbox[2] - page_bbox[0]
                draw.text(((self.width - page_width) // 2, self.height - 50), page_text, font=self.small_font, fill=0)

        # Draw instructions
        instruction = "NEXT: Navigate | HOLD: Scan/Refresh | GPIO5: Menu"
        try:
            instr_bbox = draw.textbbox((0, 0), instruction, font=self.small_font)
            instr_width = instr_bbox[2] - instr_bbox[0]
        except:
            instr_width = len(instruction) * 7

        instr_x = (self.width - instr_width) // 2
        draw.text((instr_x, self.height - 25), instruction, font=self.small_font, fill=0)

        return image
