"""Preview the caption inset and RPM readout spacing over gameplay scenery."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import preview_instruments as hud, layout


def composite(background, foreground):
    result = background.convert('RGBA').copy()
    result.alpha_composite(foreground)
    return result.convert('RGB')


def main():
    capture = Image.open(ROOT / 'design/reference/visibility-gameplay.png').convert('RGB')
    scenery = capture.crop((350, 180, 1550, 620))
    state = hud.State(speed=206, rpm=10096, gear=5, throttle=.6, brake=.5,
                      charge=.75, drs='hidden')
    revised = hud.render(state)
    revised.save(ROOT / 'design/wing-spacing-transparent.png')
    foreground = composite(scenery, revised)
    foreground.save(ROOT / 'design/wing-spacing-gameplay.png')

    before = Image.open(ROOT / 'design/wing-spacing-before.png').convert('RGBA')
    comparison = Image.new('RGB', (1248, 606), (21, 34, 44))
    draw = ImageDraw.Draw(comparison)
    font = ImageFont.truetype(str(ROOT / layout.FONT_PATH), 23)
    for x, title, artwork in ((24, 'Previous spacing', before),
                              (630, 'Revised spacing', revised)):
        draw.text((x, 15), title, font=font, fill=(236, 248, 253))
        detail = composite(scenery, artwork).crop((735, 45, 1065, 325))
        comparison.paste(detail.resize((594, 504), Image.Resampling.LANCZOS), (x, 55))
    draw.text((24, 575), 'Simulated values. Native RPM font is approximated.',
              font=ImageFont.truetype(str(ROOT / layout.FONT_PATH), 17),
              fill=(175, 201, 217))
    comparison.save(ROOT / 'design/wing-spacing-comparison.png')
    print('Rendered the revised HUD and an enlarged wing-spacing comparison.')


if __name__ == '__main__':
    main()
