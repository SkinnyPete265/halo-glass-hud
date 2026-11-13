"""Show the approved battery colour bands with reversible simulated charge."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import preview_instruments as hud, artwork as art, layout as geo

def font(size):
    face = ImageFont.truetype(str(ROOT / geo.FONT_PATH), size)
    face.set_variation_by_axes([550, 100])
    return face

def icon(charge):
    image = art.canvas()
    hud.draw_battery(image, charge)
    cx, cy = hud.BATTERY_CENTRE
    return image.crop((round((cx - 32) * hud.S), round((cy - 13) * hud.S),
                       round((cx + 35) * hud.S), round((cy + 13) * hud.S)))

def main():
    charges = (.75, .35, .30, .125, .10, .08)
    sheet = Image.new("RGB", (1110, 172), (31, 47, 57))
    draw = ImageDraw.Draw(sheet)
    draw.text((22, 10), "Battery warning colours", font=font(23),
              fill=(225, 239, 247))
    for index, charge in enumerate(charges):
        tile = icon(charge).resize((161, 62), Image.Resampling.LANCZOS)
        x = 12 + index * 184
        sheet.paste(tile, (x, 54), tile)
        draw.text((x + 80, 126), f"{charge * 100:g}%", font=font(19),
                  anchor="mm", fill=(220, 235, 244))
    sheet.save(ROOT / "design/battery-colour-bands-preview.png")

    frames = []
    # Smoothly drain through the thresholds, then refill through the same curve.
    descending = [.40 - .34 * index / 40 for index in range(41)]
    ascending = list(reversed(descending))[1:]
    for index, charge in enumerate(descending + ascending):
        frame = Image.new("RGB", (440, 174), (31, 47, 57))
        draw = ImageDraw.Draw(frame)
        direction = "Discharging" if index < len(descending) else "Recharging"
        draw.text((220, 12), direction, anchor="mt", font=font(22),
                  fill=(225, 239, 247))
        tile = icon(charge)
        frame.paste(tile, ((440 - tile.width) // 2, 53), tile)
        draw.text((220, 149), f"{charge * 100:.1f}%", anchor="mm",
                  font=font(20), fill=(220, 235, 244))
        frames.append(frame)
    frames[0].save(ROOT / "design/battery-colour-transition-preview.gif",
                   save_all=True, append_images=frames[1:],
                   duration=60, loop=0, disposal=2, optimize=False)
    print("Rendered battery bands and discharge/recharge motion preview.")

if __name__ == "__main__":
    main()
