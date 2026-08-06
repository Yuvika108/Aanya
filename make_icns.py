from PIL import Image, ImageDraw

def make_app_icon():
    # 1024x1024 is the standard high-res size for macOS
    size = (1024, 1024)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background - Rounded Rectangle (macOS style), or we can just draw a circle
    cx, cy = 512, 512
    r = 460
    
    # Let's make it a nice dark background with a sky-blue spark/orb
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#0f172a") # Dark Slate
    
    # Outer ring
    draw.ellipse([cx - r + 30, cy - r + 30, cx + r - 30, cy + r - 30], outline="#38bdf8", width=20)
    
    # Inner orb
    r_inner = 200
    draw.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill="#06b6d4") # Cyan
    
    # Pulse rings
    draw.ellipse([cx - r_inner - 80, cy - r_inner - 80, cx + r_inner + 80, cy + r_inner + 80], outline="#38bdf8", width=12)

    # Save as ICNS
    # Pillow supports saving as .icns
    try:
        img.save("aanya.icns", format="ICNS")
        print("Successfully generated aanya.icns")
    except Exception as e:
        print(f"Error: {e}")
        # fallback to saving PNG and we'll convert it using sips/iconutil
        img.save("aanya.png")
        print("Saved aanya.png instead.")

if __name__ == "__main__":
    make_app_icon()
