"""Render glass-contrast comparisons over HUD-free gameplay and light/dark fields."""
import importlib
from pathlib import Path
import sys
import types
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import preview_instruments as hud, material, layout


def font(size):
    return ImageFont.truetype(str(ROOT / layout.FONT_PATH), size)


def composite(background, foreground):
    result = background.convert('RGBA').copy()
    result.alpha_composite(foreground)
    return result.convert('RGB')


def previous_material(state):
    package = types.ModuleType('visibility_baseline')
    package.__path__ = [str(ROOT / 'build/source-checkpoints/v0.2.0-visibility/halo'),
                        str(ROOT / 'halo')]
    sys.modules[package.__name__] = package
    previous = importlib.import_module(package.__name__ + '.preview_instruments')
    previous_material = importlib.import_module(package.__name__ + '.material')
    previous_material.FONT = str(ROOT / layout.FONT_PATH)
    return previous.render(state)


def main():
    capture = Image.open(ROOT / 'design/reference/visibility-gameplay.png').convert('RGB')
    # This patch ends above the existing game's HUD. No old graphics sit under
    # the candidate, and the new artwork retains its native 1200x440 aspect.
    scenery = capture.crop((350, 180, 1550, 620))
    state = hud.State(speed=206, rpm=10096, gear=5, throttle=.6, brake=.5,
                      charge=.75, drs='hidden')
    current = previous_material(state)
    revised = hud.render(state)
    revised.save(ROOT / 'design/visibility-revised-transparent.png')
    composite(scenery, revised).save(ROOT / 'design/visibility-gameplay-preview.png')

    sheet = Image.new('RGB', (1248, 1018), (21, 34, 44))
    draw = ImageDraw.Draw(sheet)
    for y, caption, artwork in (
            (58, 'Earlier glass tint', current),
            (548, 'Reinforced glass and revised GEARS caption', revised)):
        draw.text((24, y - 36), caption, font=font(24), fill=(236, 248, 253))
        sheet.paste(composite(scenery, artwork), (24, y))
    draw.text((24, 994), 'Offline composites with simulated values. Native speed font is approximated.',
              font=font(17), fill=(175, 201, 217))
    sheet.save(ROOT / 'design/visibility-comparison.png')

    backgrounds = (
        ('Bright sky', ImageOps.fit(capture.crop((550, 0, 1410, 170)),
                                   (1200, 440), Image.Resampling.LANCZOS)),
        ('Pale surface', Image.new('RGB', (1200, 440), (231, 235, 238))),
        ('Dark cockpit', ImageOps.fit(capture.crop((820, 855, 1080, 920)),
                                     (1200, 440), Image.Resampling.LANCZOS)),
    )
    checks = Image.new('RGB', (1248, 1510), (21, 34, 44))
    draw = ImageDraw.Draw(checks)
    for index, (caption, backdrop) in enumerate(backgrounds):
        y = 54 + index * 480
        draw.text((24, y - 34), caption, font=font(24), fill=(236, 248, 253))
        checks.paste(composite(backdrop, revised), (24, y))
    draw.text((24, 1483), 'Contrast previews over gameplay crops and a pale test surface.',
              font=font(17), fill=(175, 201, 217))
    checks.save(ROOT / 'design/visibility-background-checks.png')

    # An enlarged crop makes the caption, text edge and target speed anchor
    # reviewable without changing their real output size in the full previews.
    detail = composite(scenery, revised).crop((478, 15, 1040, 320))
    detail.resize((1124, 610), Image.Resampling.LANCZOS).save(
        ROOT / 'design/visibility-instrument-detail.png')
    print('Rendered gameplay comparison, contrast checks and instrument detail.')


if __name__ == '__main__':
    main()
