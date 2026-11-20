"""Render 1080p comparisons for DRS, race glow and pedal-mask refinement."""
from pathlib import Path
import json
import math
import sys

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import artwork as art, feature_assets, layout as geo
from halo import material as mat, preview_instruments as hud

OUT = ROOT / 'build/tuning/visual-refinement'
SCREEN = (1920, 1080)
PREVIEW_SCALE = .86
GLOW_VARIANTS = ('B+', 'B+3', 'B+4')
PEDAL_VARIANT = 'B+4'
_OVERLAYS = {}


def bright_scene():
    capture = Image.open(ROOT / 'design/reference/visibility-gameplay.png').convert('RGB')
    # This central crop has bright scenery and no existing HUD beneath the
    # candidate, so translucent faces can be compared without double drawing.
    return ImageOps.fit(capture.crop((575, 0, 1410, 680)), SCREEN,
                        method=Image.Resampling.LANCZOS)


def dark_scene():
    image = Image.new('RGB', SCREEN)
    pixels = image.load()
    first, last = (13, 25, 35), (33, 50, 62)
    for y in range(image.height):
        t = y / (image.height - 1)
        colour = tuple(round(a + (b - a) * t) for a, b in zip(first, last))
        for x in range(image.width):
            pixels[x, y] = colour
    return image


def add_hud(background, state, variant, label):
    image = background.convert('RGBA')
    key = (variant, state)
    overlay = _OVERLAYS.get(key)
    if overlay is None:
        overlay = hud.render(state, race_variant=variant)
        size = (round(overlay.width * PREVIEW_SCALE),
                round(overlay.height * PREVIEW_SCALE))
        overlay = overlay.resize(size, Image.Resampling.LANCZOS)
        _OVERLAYS[key] = overlay
    size = overlay.size
    position = ((SCREEN[0] - size[0]) // 2, 0)
    image.alpha_composite(overlay, position)
    image = image.convert('RGB')
    draw = ImageDraw.Draw(image)
    draw.text((24, 1038), label, font=mat.typeface(23, 600),
              fill=(236, 248, 253), stroke_width=2, stroke_fill=(10, 20, 28))
    return image


def pedal_profile(side, index=4):
    """Measure 10–90% edge width in art space for idle and active masks."""
    sign = -1 if side == 'brake' else 1
    points = geo.slat_points(sign, index)
    a, b = points[0], points[1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = (dx * dx + dy * dy) ** .5
    nx, ny = -dy / length, dx / length
    centre = (sum(point[0] for point in points) / 4,
              sum(point[1] for point in points) / 4)
    middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if (centre[0] - middle[0]) * nx + (centre[1] - middle[1]) * ny < 0:
        nx, ny = -nx, -ny

    idle = art._idle_slats_layer().getchannel('A')
    active, offset = hud.pedal_surface(side)
    active = active.getchannel('A')
    runtime = feature_assets.pedal_mask(sign).getchannel('A')
    span = geo.PEDAL_MASK_SPAN
    idle_left = round((geo.CX - span / 2) * art.S)
    idle_top = round((geo.CY - span / 2) * art.S)
    idle_uv = idle.crop((idle_left, idle_top,
                         idle_left + round(span * art.S),
                         idle_top + round(span * art.S)))
    idle_uv = idle_uv.resize(runtime.size, Image.Resampling.LANCZOS).point(
        lambda value: round(value * 255 / 55.)
    )

    def sample(image, x, y):
        return image.getpixel((round(x), round(y)))

    def bilinear(image, x, y):
        x0, y0 = math.floor(x), math.floor(y)
        fx, fy = x - x0, y - y0
        value = 0.
        for oy, wy in ((0, 1 - fy), (1, fy)):
            for ox, wx in ((0, 1 - fx), (1, fx)):
                px, py = x0 + ox, y0 + oy
                if 0 <= px < image.width and 0 <= py < image.height:
                    value += image.getpixel((px, py)) * wx * wy
        return value

    distances = [index / 6 for index in range(-12, 13)]
    profiles = {'idle_art': [], 'preview_active_art': [],
                'idle_uv': [], 'runtime_mask': []}
    for distance in distances:
        x, y = middle[0] + nx * distance, middle[1] + ny * distance
        art_x, art_y = round(x * art.S), round(y * art.S)
        profiles['idle_art'].append(sample(idle, art_x, art_y) / 55.)
        profiles['preview_active_art'].append(sample(
            active, art_x - offset[0], art_y - offset[1]
        ) / 255.)
        profiles['idle_uv'].append(bilinear(
            idle_uv, (.5 + (x - geo.CX) / span) * runtime.width - .5,
            (.5 + (y - geo.CY) / span) * runtime.height - .5
        ) / 255.)
        uv_x = (.5 + (x - geo.CX) / span) * runtime.width - .5
        uv_y = (.5 + (y - geo.CY) / span) * runtime.height - .5
        profiles['runtime_mask'].append(bilinear(runtime, uv_x, uv_y) / 255.)

    def transition_width(values):
        crossing = []
        for index, (first, second) in enumerate(zip(values, values[1:])):
            if first <= .1 < second or first < .9 <= second:
                threshold = .1 if first <= .1 < second else .9
                fraction = (threshold - first) / (second - first)
                crossing.append((distances[index] + fraction / 6, threshold))
        if len(crossing) < 2:
            return None
        return round(crossing[-1][0] - crossing[0][0], 3)

    return {
        'sample_edge': f'{side} slat {index + 1}',
        '10_to_90_width_art_px': {
            name: transition_width(values) for name, values in profiles.items()
        },
        'profiles_at_1_6_art_px_steps': {
            name: [round(value, 3) for value in values]
            for name, values in profiles.items()
        },
    }


def make_detail_sheet(frames):
    sheet = Image.new('RGB', (1920, 1080), (19, 32, 42))
    draw = ImageDraw.Draw(sheet)
    # Two top tip crops, then idle / partial / full pedal banks. The source
    # samples are enlarged with nearest-neighbour so alpha coverage stays visible.
    panels = [
        ('DRS left face tip · full open', frames['drs'].crop((360, 100, 520, 410))),
        ('DRS right face tip · full open', frames['drs'].crop((1400, 100, 1560, 410))),
    ]
    for title, phase in (('Idle slats', 'idle'), ('Partial pedals · 50%', 'partial'),
                         ('Full pedals', 'full')):
        image = frames[phase]
        brake = image.crop((790, 25, 900, 205))
        throttle = image.crop((1020, 25, 1130, 205))
        combined = Image.new('RGB', (260, 180), (19, 32, 42))
        combined.paste(brake, (0, 0))
        combined.paste(throttle, (150, 0))
        panels.append((title + ' · brake / throttle', combined))

    cell_w, cell_h = 640, 540
    positions = ((0, 0), (640, 0), (1280, 0), (0, 540), (640, 540))
    for (title, crop), (x, y) in zip(panels, positions):
        draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1),
                       fill=(24, 39, 49), outline=(65, 93, 108))
        draw.text((x + 12, y + 10), title, font=mat.typeface(19, 600),
                  fill=(236, 248, 253))
        scale = min((cell_w - 24) / crop.width, (cell_h - 54) / crop.height)
        zoom = crop.resize((round(crop.width * scale), round(crop.height * scale)),
                           Image.Resampling.NEAREST)
        sheet.paste(zoom, (x + (cell_w - zoom.width) // 2,
                           y + 42 + (cell_h - 48 - zoom.height) // 2))
    return sheet


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bright, dark = bright_scene(), dark_scene()
    sample = hud.State(speed=250, rpm=11585, gear=6, throttle=0., brake=0.,
                       charge=.75, drs='hidden',
                       sector_times=('23.456', '24.567', '25.678'),
                       sector_colours=('white', 'yellow', 'green'))
    glow = Image.new('RGB', (SCREEN[0] * 3, SCREEN[1] * 2), (19, 32, 42))
    for row, (backdrop, name) in enumerate(((bright, 'bright scenery'),
                                             (dark, 'dark field'))):
        for column, variant in enumerate(GLOW_VARIANTS):
            frame = add_hud(backdrop, sample, variant,
                            f'{variant} · {mat.RACE_EDGE_VARIANTS[variant]["circle_glow_layers"]} glow layers · {name}')
            frame.save(OUT / f'glow-{variant.lower().replace("+", "p")}-{name.split()[0]}-1920x1080.png')
            glow.paste(frame, (column * SCREEN[0], row * SCREEN[1]))
    glow.save(OUT / 'glow-candidates-1920x1080.png')

    states = {
        'drs': hud.State(speed=250, rpm=11585, gear=6, throttle=0., brake=0.,
                         charge=.75, drs='open', sector_times=sample.sector_times,
                         sector_colours=sample.sector_colours),
        'idle': sample,
        'partial': hud.State(speed=250, rpm=11585, gear=6, throttle=.5, brake=.5,
                             charge=.75, drs='hidden', sector_times=sample.sector_times,
                             sector_colours=sample.sector_colours),
        'full': hud.State(speed=250, rpm=11585, gear=6, throttle=1., brake=1.,
                          charge=.75, drs='hidden', sector_times=sample.sector_times,
                          sector_colours=sample.sector_colours),
    }
    labels = {'drs': 'Fully open DRS · face-tip fade', 'idle': 'Idle brake + throttle',
              'partial': 'Partial brake + throttle · 50%',
              'full': 'Full brake + throttle'}
    state_sheet = Image.new('RGB', (SCREEN[0] * 4, SCREEN[1]), (19, 32, 42))
    frames = {}
    for column, name in enumerate(('drs', 'idle', 'partial', 'full')):
        frame = add_hud(bright, states[name], PEDAL_VARIANT,
                        f'{PEDAL_VARIANT} · {labels[name]}')
        frames[name] = frame
        frame.save(OUT / f'state-{name}-1920x1080.png')
        state_sheet.paste(frame, (column * SCREEN[0], 0))
    state_sheet.save(OUT / 'drs-and-pedals-1920x1080.png')
    make_detail_sheet(frames).save(OUT / 'drs-tip-and-pedal-details.png')

    metrics = {
        'screen_resolution': list(SCREEN),
        'hud_preview_scale': PREVIEW_SCALE,
        'glow_effective_alpha': {
            variant: {
                key: round(255 * (1 - (1 - style[alpha_key] / 255.) ** style[key]))
                for key, alpha_key in (
                    ('edge_glow_layers', 'edge_glow_alpha'),
                    ('outline_glow_layers', 'outline_glow_alpha'),
                    ('circle_glow_layers', 'circle_glow_alpha'),
                )
            }
            for variant, style in ((name, mat.RACE_EDGE_VARIANTS[name])
                                   for name in GLOW_VARIANTS)
        },
        'pedal_profiles': [pedal_profile('brake'), pedal_profile('throttle')],
        'selected_glow_default': mat.DEFAULT_RACE_EDGE_VARIANT,
    }
    (OUT / 'offline-measurements.json').write_text(
        json.dumps(metrics, indent=2) + '\n', encoding='utf-8'
    )
    print('Wrote 1920x1080 baseline/3/4-layer glow and DRS/pedal comparisons.')
    print('Measurements:', json.dumps(metrics['pedal_profiles'], separators=(',', ':')))


if __name__ == '__main__':
    main()
