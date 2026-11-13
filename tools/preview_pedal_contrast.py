"""Compare pedal-bank contrast over bright and dark surfaces."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import artwork as art, layout as geo, material as mat, preview_instruments as hud


def background(upper, lower):
    image = Image.new('RGBA', (geo.WIDTH, geo.HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(geo.HEIGHT):
        mix = y / (geo.HEIGHT - 1)
        colour = tuple(round(a + (b - a) * mix) for a, b in zip(upper, lower))
        draw.line((0, y, geo.WIDTH, y), fill=colour + (255,))
    return image


def main():
    before = Image.open(ROOT / 'design/pedal-contrast-before-transparent.png').convert('RGBA')
    state = hud.State(speed=206, rpm=11000, gear=6, throttle=.35, brake=.35, drs='hidden')
    after = hud.render(state)
    after.save(ROOT / 'design/pedal-contrast-transparent.png')
    for side in (-1, 1):
        points = geo.slat_points(side, 8)
        x = round(sum(x for x, y in points) / 4)
        y = round(sum(y for x, y in points) / 4)
        assert after.getpixel((x, y))[3] >= 200
    backing = mat.pedal_backing()
    for side in (-1, 1):
        for index in range(10):
            for x, y in geo.slat_points(side, index):
                assert backing.getpixel((round(x * mat.S), round(y * mat.S)))[3] >= 200
    assert backing.getpixel((round(geo.CX * mat.S), round(geo.CY * mat.S)))[3] == 0
    sheet = Image.new('RGB', (1320, 720), (24, 39, 49))
    draw = ImageDraw.Draw(sheet)
    cases = (
        ('Bright sky', (164, 208, 239), (219, 237, 249)),
        ('Pale surfaces', (242, 242, 234), (219, 222, 216)),
        ('Dark scenery', (39, 52, 61), (22, 32, 40)),
    )
    for index, (title, upper, lower) in enumerate(cases):
        left = index * 440 + 5
        scenery = background(upper, lower)
        draw.text((left + 10, 12), title, font=mat.typeface(23, 600), fill=(236, 248, 253))
        for top, caption, layer in ((66, 'Current', before), (398, 'Stronger smoked backing', after)):
            draw.text((left + 10, top - 27), caption, font=mat.typeface(18, 500), fill=(188, 213, 228))
            image = Image.alpha_composite(scenery, layer).crop((390, 0, 780, 244))
            image = image.resize((430, 269), Image.Resampling.LANCZOS)
            sheet.paste(image.convert('RGB'), (left, top))
    draw.text((15, 690), 'Both inputs at 35%. Offline contrast preview.',
              font=mat.typeface(18, 500), fill=(175, 201, 217))
    sheet.save(ROOT / 'design/pedal-contrast-preview.png')
    print('Verified backing coverage and saved design/pedal-contrast-preview.png')


if __name__ == '__main__':
    main()
