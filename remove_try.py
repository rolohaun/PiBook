#!/usr/bin/env python3
# Manually fix the try statement - line by line approach

lines = []
with open('src/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 106 has "try:" which needs to be removed
# Replace lines 105-106 with just the HDMI comment
if len(lines) > 106:
    # Remove line 106 (the try statement)
    del lines[105]  # This was line 106 (0-indexed is 105)

with open('src/main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Removed try statement from line 106")
