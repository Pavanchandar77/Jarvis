import sys
import os
from PIL import Image

png_path = r"C:\Users\pavan\spark\static\green_logo.png"
ico_path = r"C:\Users\pavan\spark\static\icon.ico"

if os.path.exists(png_path):
    try:
        img = Image.open(png_path)
        # Convert and save as ICO with standard sizes (16, 32, 48, 64, 128, 256)
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(ico_path, format="ICO", sizes=sizes)
        print("Successfully converted PNG to high-quality ICO and replaced static/icon.ico")
    except Exception as e:
        print("Error converting image:", e)
else:
    print("PNG logo file not found at static/green_logo.png")
