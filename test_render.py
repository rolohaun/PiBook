"""
Test script to render EPUB exactly as the Pi would display it
Simulates full rendering pipeline
"""
import sys
sys.path.insert(0, 'src')

import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageDraw, ImageFont

# Open the EPUB
epub_path = "Brandon Sanderson - [Mistborn 01] - The Final Empire.epub"
doc = fitz.open(epub_path)

print(f"EPUB has {len(doc)} pages")

# Target dimensions - PORTRAIT mode (the display is rotated 90 degrees)
# Display is 800x480 hardware, but shown as 480x800 in portrait
display_width = 480
display_height = 800
rotation = 90

# Test page 11 (prologue) - 0-indexed is 10
page_num = 10
page = doc[page_num]

# Get page dimensions
page_rect = page.rect
print(f"EPUB page size: {page_rect.width} x {page_rect.height}")

# Calculate zoom for target size (leaving room for page number)
usable_height = display_height - 25
zoom_x = display_width / page_rect.width
zoom_y = usable_height / page_rect.height
zoom = min(zoom_x, zoom_y)
print(f"Zoom factor: {zoom:.3f}")

# Disable anti-aliasing for crisp text
fitz.TOOLS.set_aa_level(0)

# Render with matrix
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat, alpha=False)
print(f"Rendered at {pix.width}x{pix.height}")

# Convert to PIL
img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

# Convert to grayscale
gray = img.convert('L')

# Boost contrast
from PIL import ImageEnhance
enhancer = ImageEnhance.Contrast(gray)
gray = enhancer.enhance(1.2)

# Convert to 1-bit WITHOUT dithering
bw = gray.convert('1', dither=Image.Dither.NONE)

# Create final background at display size
background = Image.new('1', (display_width, display_height), 1)  # 1 = white

# Center the content
x_offset = (display_width - bw.width) // 2
y_offset = (usable_height - bw.height) // 2
background.paste(bw, (x_offset, y_offset))

# Add page number
draw = ImageDraw.Draw(background)
try:
    font = ImageFont.truetype("arial.ttf", 14)
except:
    font = ImageFont.load_default()

page_text = f"Page {page_num + 1} of {len(doc)}"
try:
    bbox_text = draw.textbbox((0, 0), page_text, font=font)
    text_width = bbox_text[2] - bbox_text[0]
    text_x = (display_width - text_width) // 2
except:
    text_x = display_width // 2 - 50

draw.text((text_x, display_height - 22), page_text, fill=0, font=font)

# Save the portrait image
background.save("C:\\Users\\Ron\\.gemini\\antigravity\\brain\\e2103530-66ef-4dd0-a3e7-09ab0637ca45\\final_render_portrait.png")
print(f"Saved portrait image: {display_width}x{display_height}")

# Now rotate 90 degrees for hardware display (NEAREST resampling)
rotated = background.rotate(-rotation, expand=True, resample=Image.Resampling.NEAREST)
rotated.save("C:\\Users\\Ron\\.gemini\\antigravity\\brain\\e2103530-66ef-4dd0-a3e7-09ab0637ca45\\final_render_rotated.png")
print(f"Saved rotated image for hardware: {rotated.width}x{rotated.height}")

# Also save the RGB version for comparison
img.save("C:\\Users\\Ron\\.gemini\\antigravity\\brain\\e2103530-66ef-4dd0-a3e7-09ab0637ca45\\source_rgb.png")
print("Saved source RGB image")

print("\nDone! Check the artifacts folder for:")
print("- source_rgb.png (what PyMuPDF renders)")
print("- final_render_portrait.png (480x800, what should go to display)")
print("- final_render_rotated.png (800x480, after rotation for hardware)")

doc.close()
