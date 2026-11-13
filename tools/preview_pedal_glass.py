"""Preview a separate curved smoked-glass accent beside each pedal bank."""
import math
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import artwork as art, layout as geo
from halo.material import pedal_accents as accents


def main():
    base = Image.open(ROOT / 'design/gear-row-centering-transparent.png').convert('RGBA')
    layer = art.finish(accents())
    layer.save(ROOT / 'design/pedal-glass-accent-layer.png')
    candidate = Image.alpha_composite(base, layer)
    candidate.save(ROOT / 'design/pedal-glass-concept-transparent.png')
    capture = Image.open(ROOT / 'design/reference/visibility-gameplay.png').convert('RGB')
    scenery = capture.crop((350, 180, 1550, 620)).convert('RGBA')
    scene = Image.alpha_composite(scenery, candidate)
    scene.convert('RGB').save(ROOT / 'design/pedal-glass-gameplay-preview.png')

    sheet = Image.new('RGB', (792, 982), (21, 34, 44))
    draw = ImageDraw.Draw(sheet)
    heading = ImageFont.truetype(str(ROOT / geo.FONT_PATH), 23)
    for y, caption, artwork in ((56, 'Current center section', base),
                                (518, 'Curved glass accents with a faint etched texture', candidate)):
        draw.text((24, y - 34), caption, font=heading, fill=(236, 248, 253))
        panel = Image.alpha_composite(scenery, artwork)
        detail = panel.crop((396, 0, 768, 210)).resize((744, 420), Image.Resampling.LANCZOS)
        sheet.paste(detail.convert('RGB'), (24, y))
    draw.text((24, 954), 'Design preview over gameplay. Simulated HUD values.',
              font=ImageFont.truetype(str(ROOT / geo.FONT_PATH), 17), fill=(175, 201, 217))
    sheet.save(ROOT / 'design/pedal-glass-accent-preview.png')
    print('Rendered an isolated glass-accent proposal over the approved HUD layout.')


if __name__ == '__main__':
    main()
