#!/usr/bin/env python3
"""
Test script to verify icon loading for MainMenuScreen
"""

import os
import sys
from PIL import Image

# Simulate the path calculation from src/ui/screens.py
print("Testing icon loading path calculation...")
print()

# Simulate __file__ being src/ui/screens.py
screens_py_path = os.path.join(os.getcwd(), 'src', 'ui', 'screens.py')
print(f"Simulated __file__: {screens_py_path}")
print()

# Calculate project root (3 levels up from src/ui/screens.py)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(screens_py_path))))
print(f"Project root: {project_root}")
print()

# Calculate assets directory
assets_dir = os.path.join(project_root, 'assets', 'icons')
print(f"Assets directory: {assets_dir}")
print(f"Assets directory exists: {os.path.exists(assets_dir)}")
print()

# Check for icon files
icon_files = ['ereader.png', 'ip_scanner.png', 'todo.png']
for icon_file in icon_files:
    icon_path = os.path.join(assets_dir, icon_file)
    exists = os.path.exists(icon_path)
    print(f"{icon_file}: {exists}")
    
    if exists:
        try:
            img = Image.open(icon_path)
            print(f"  - Size: {img.size}")
            print(f"  - Mode: {img.mode}")
            
            # Test conversion to 1-bit
            if img.mode != '1':
                img_gray = img.convert('L')
                img_1bit = img_gray.point(lambda x: 0 if x < 128 else 255, '1')
                print(f"  - Converted to 1-bit successfully")
                print(f"  - Final mode: {img_1bit.mode}")
        except Exception as e:
            print(f"  - ERROR loading: {e}")
    print()
