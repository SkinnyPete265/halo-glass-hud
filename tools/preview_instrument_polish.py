"""Compare the DRS, RPM and gear refinements against the saved source checkpoint."""
from pathlib import Path
import sys
from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import artwork as art, layout as geo, material as mat, feature_assets
from halo import preview_instruments as hud


def verify():
    assert abs(geo.GEAR_NUMBER_SIZE / (17. * .97) - 1.02) < 1e-9
    assert abs(geo.GEAR_SELECTED_SIZE / (27. * .97) - 1.05) < 1e-9
    for selected in range(1, 9):
        boxes = []
        for gear in range(1, 9):
            sprite, position = hud.gear_surface(gear, gear == selected)
            alpha = sprite.getchannel('A').point(lambda value: 255 if value >= 128 else 0)
            box = alpha.getbbox()
            boxes.append((position[0] + box[0], position[0] + box[2]))
        assert min(second[0] - first[1] for first, second in zip(boxes, boxes[1:])) > 4 * mat.S

    surface = art.rpm_fill()
    finished = art.finish(surface)
    left, top, right, bottom = finished.getbbox()
    right += (4 - (right - left) % 4) % 4
    width = right - left + 2 / .30
    mask = feature_assets.fill_edge_mask(width, 1.0, width=2048)
    alphas = [mask.getpixel((x, 0))[3] for x in range(mask.width)]
    assert alphas[0] == 255 and alphas[-1] == 0
    assert all(first >= second for first, second in zip(alphas, alphas[1:]))
    assert sum(0 < value < 255 for value in alphas) >= 5
    pixels = surface.getchannel('A')
    pixels_left, _, pixels_right, _ = pixels.getbbox()
    for fraction in (0., .25, .5, .83, .98, 1.):
        feather = 1.0 * mat.S
        edge = pixels_left + (pixels_right - pixels_left) * fraction + feather * (2 * fraction - 1)
        row = Image.new('L', (surface.width, 1))
        coverage = [hud.clamp((edge - x - .5) / feather) for x in range(row.width)]
        row.putdata([round(255 * value * value * (3 - 2 * value)) for value in coverage])
        filled = ImageChops.multiply(pixels, row.resize(pixels.size))
        if fraction == 0.:
            assert filled.getbbox() is None
        elif fraction == 1.:
            assert ImageChops.difference(pixels, filled).getbbox() is None
    assert art.RPM_WARNING_START == .83
    print('Verified gear size increases and all eight neighbour clearances, RPM mask coverage and unchanged red threshold.')


def main():
    verify()
    before = Image.open(ROOT/'design/instrument-polish-before.png').convert('RGBA')
    state = hud.State(speed=279, rpm=11249, gear=7, throttle=.7, brake=0., charge=.75,
                      drs='open', sector_times=('29.531', '19.094', '33.366'),
                      sector_colours=('yellow', 'yellow', 'purple'))
    after = hud.render(state)
    after.save(ROOT/'design/instrument-polish-transparent.png')
    capture = Image.open(ROOT/'design/reference/visibility-gameplay.png').convert('RGBA').crop((350, 180, 1550, 620))
    full = Image.alpha_composite(capture, after).convert('RGB')
    full.save(ROOT/'design/instrument-polish-gameplay.png')
    comparison = Image.new('RGB', (1240, 1010), (24, 39, 49))
    draw = ImageDraw.Draw(comparison)
    for y, title, image in ((50, 'Before', before), (540, 'Adjusted DRS, RPM and gears', after)):
        comparison.paste(Image.alpha_composite(capture, image).convert('RGB'), (20, y))
        draw.text((20, y-34), title, font=mat.typeface(23, 550), fill=mat.WHITE)
    draw.text((20, 985), 'Offline artwork preview. Native text rendering needs in-game confirmation.',
              font=mat.typeface(16, 500), fill=(175, 201, 217))
    comparison.save(ROOT/'design/instrument-polish-comparison.png')

    detail = Image.new('RGB', (1180, 652), (24, 39, 49))
    draw = ImageDraw.Draw(detail)
    dark = Image.new('RGBA', before.size, (25, 40, 51, 255))
    for x, title, image in ((18, 'Before', before), (606, 'Adjusted', after)):
        on_dark = Image.alpha_composite(dark, image)
        wing = on_dark.crop((760, 72, 1050, 320)).resize((550, 470), Image.Resampling.LANCZOS)
        drs = Image.alpha_composite(capture, image).crop((520, 194, 644, 230)).resize((372, 108), Image.Resampling.LANCZOS)
        detail.paste(wing.convert('RGB'), (x, 44))
        detail.paste(drs.convert('RGB'), (x, 524))
        draw.text((x, 10), title, font=mat.typeface(22, 550), fill=mat.WHITE)
    detail.save(ROOT/'design/instrument-polish-detail.png')
    print('Saved full gameplay and before/after detail previews.')


if __name__ == '__main__':
    main()
