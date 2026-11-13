"""Compare current and restored HUD sizes using the supplied screenshot as scale reference."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CURRENT_HUD_SCALE = 0.30
RESTORED_HUD_SCALE = 0.53625
# The screenshot's hub is approximately 96 pixels across at 1920 x 1080.
CURRENT_SCREEN_PIXELS_PER_ART_PIXEL = 0.54

def main():
    image = Image.open(ROOT / "design/core-preview-transparent.png").convert("RGBA")
    ratio = RESTORED_HUD_SCALE / CURRENT_HUD_SCALE
    factors = [CURRENT_SCREEN_PIXELS_PER_ART_PIXEL,
               CURRENT_SCREEN_PIXELS_PER_ART_PIXEL * ratio]
    labels = ["Current v2 size", "Previous effective scale restored (+79%)"]
    font = ImageFont.truetype(str(ROOT / "assets/fonts/Saira/Saira.ttf"), 25)
    font.set_variation_by_axes([550, 100])
    heights = [round(image.height * factor) for factor in factors]
    canvas = Image.new("RGBA", (1280, sum(heights) + 170), (31, 47, 57, 255))
    draw = ImageDraw.Draw(canvas)
    y = 18
    for label, factor, height in zip(labels, factors, heights):
        draw.text((30, y), label, font=font, fill=(225, 239, 247, 255))
        y += 40
        resized = image.resize((round(image.width * factor), height),
                               Image.Resampling.LANCZOS)
        # Keep the speed-circle centre on the same horizontal anchor in both rows.
        x = round(canvas.width / 2 - 582 * factor)
        canvas.alpha_composite(resized, (x, y))
        y += height + 16
    note = ImageFont.truetype(str(ROOT / "assets/fonts/Saira/Saira.ttf"), 17)
    draw.text((30, canvas.height - 30),
              "Offline size comparison. Screen scale is estimated from your screenshot. Native text font differs.",
              font=note, fill=(170, 196, 211, 255))
    canvas.convert("RGB").save(ROOT / "design/scale-restoration-preview.png")

if __name__ == "__main__":
    main()
