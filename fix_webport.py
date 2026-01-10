#!/usr/bin/env python3
# Add web_port before LibraryScreen

lines = []
with open('src/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Insert web_port definition before LibraryScreen (line 106)
new_lines = []
for i, line in enumerate(lines):
    # Before LibraryScreen initialization, add web_port
    if i == 105 and 'self.library_screen = LibraryScreen' in line:
        new_lines.append('\r\n')
        new_lines.append('        # HDMI is disabled via /boot/config.txt (dtoverlay=vc4-kms-v3d,nohdmi)\r\n')
        new_lines.append('        self.logger.info("HDMI disabled via boot config")\r\n')
        new_lines.append('\r\n')
        new_lines.append('        # Initialize screens\r\n')
        new_lines.append('        web_port = self.config.get(\'web.port\', 5000)\r\n')
    new_lines.append(line)

with open('src/main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Added web_port and HDMI comment")
