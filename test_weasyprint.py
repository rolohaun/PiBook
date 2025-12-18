"""
Test the WeasyPrint EPUB renderer
"""
import sys
sys.path.insert(0, 'src')

from reader.weasyprint_renderer import WeasyPrintRenderer

# Test with Mistborn EPUB
epub_path = "Brandon Sanderson - [Mistborn 01] - The Final Empire.epub"

print(f"Testing WeasyPrint renderer with: {epub_path}")
print("-" * 50)

try:
    # Create renderer (portrait mode: 480x800)
    renderer = WeasyPrintRenderer(epub_path, width=480, height=800)
    
    print(f"Loaded: {renderer.page_count} chapters/pages")
    print(f"Metadata: {renderer.get_metadata()}")
    
    # Render a few pages
    for page_num in [0, 5, 10]:
        if page_num < renderer.page_count:
            print(f"\nRendering page {page_num + 1}...")
            img = renderer.render_page(page_num)
            
            # Save to artifacts folder for viewing
            output_path = f"C:\\Users\\Ron\\.gemini\\antigravity\\brain\\e2103530-66ef-4dd0-a3e7-09ab0637ca45\\weasyprint_page_{page_num + 1}.png"
            img.save(output_path)
            print(f"Saved: {output_path}")
    
    renderer.close()
    print("\n" + "=" * 50)
    print("Test complete! Check the artifacts folder for rendered pages.")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
