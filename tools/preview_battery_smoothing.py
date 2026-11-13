"""Simulate the v0.9 battery retarget curve for historical comparison."""
from pathlib import Path
import math
import sys
from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import feature_assets, layout as geo, material as mat, preview_instruments as hud


def target(time):
    time = min(time, 4.)
    charge = .8 - .375 * time if time < 2. else .05 + .375 * (time - 2.)
    return round(charge / .05) * .05


def main():
    scale = mat.S
    left = round((geo.CX - 36) * scale)
    top = round((geo.BATTERY_CENTRE[1] - 19) * scale)
    box = (left, top, left + 72 * scale, top + 38 * scale)
    layers = {name: image.crop(box) for name, image in feature_assets.battery_layers().items()}

    def icon(charge, soft):
        image = layers['housing'].copy()
        colour = Image.new('RGBA', image.size, hud.battery_colour(charge) + (255,))
        image.alpha_composite(ImageChops.multiply(layers['frame'], colour))
        fill = ImageChops.multiply(layers['fill'], colour)
        start = (geo.CX - geo.BATTERY_WIDTH / 2 + 3) * scale - left
        width = (geo.BATTERY_WIDTH - 6) * scale
        feather = .3 * scale
        edge = start + width * charge + (feather * (2 * charge - 1) if soft else 0.)
        mask = Image.new('L', (fill.width, 1))
        coverage = [hud.clamp((edge - x - .5) / feather) if soft else float(x < int(edge))
                    for x in range(fill.width)]
        mask.putdata([round(255 * value * value * (3 - 2 * value)) for value in coverage])
        fill.putalpha(ImageChops.multiply(fill.getchannel('A'), mask.resize(fill.size)))
        image.alpha_composite(fill)
        image.alpha_composite(layers['bolt'])
        return image.resize((324, 171), Image.Resampling.LANCZOS)

    start_time, start, destination, next_tick = 0., target(0.), target(0.), 0.

    def value_at(time):
        progress = hud.clamp((time - start_time) / .15)
        return start + (destination - start) * (1 - (1 - progress) ** 2)

    frames = []
    for index in range(135):
        time = index / 30.
        while next_tick <= time + 1e-9:
            start = value_at(next_tick)
            start_time = next_tick
            destination = target(next_tick)
            next_tick += .05
        shown = value_at(time)
        assert min(start, destination) - 1e-8 <= shown <= max(start, destination) + 1e-8
        panel = Image.new('RGB', (720, 310), (24, 39, 49))
        draw = ImageDraw.Draw(panel)
        for x, title, charge, soft in ((18, 'Current stepped fill', target(time), False),
                                      (378, 'Native smoothing candidate', shown, True)):
            draw.text((x, 18), title, font=mat.typeface(19, 550), fill=(236, 248, 253))
            rendered = icon(charge, soft)
            panel.paste(rendered, (x, 65), rendered.getchannel('A'))
        caption = 'Depleting' if time < 2. else 'Recharging'
        draw.text((18, 251), caption, font=mat.typeface(19, 550), fill=(211, 232, 243))
        draw.text((18, 282), 'Accelerated simulation. Native in-game verification is pending.',
                  font=mat.typeface(16, 500), fill=(175, 201, 217))
        frames.append(panel)
    samples = Image.new('RGB', (720, 310 * 9))
    for index, frame in enumerate(frames[::15]):
        samples.paste(frame, (0, index * 310))
    palette = samples.quantize(colors=253)
    colours = palette.getpalette()
    for index, colour in enumerate((hud.BATTERY_BLUE, hud.BATTERY_YELLOW, hud.BATTERY_RED), start=253):
        colours[index*3:index*3+3] = colour
    palette.putpalette(colours)
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    indexed[0].save(ROOT/'design/battery-smoothing-preview.gif', save_all=True,
                    append_images=indexed[1:], duration=[33, 33, 34] * 45,
                    loop=0, disposal=1, optimize=True)
    print('Saved the drain/recharge simulation and checked that interpolation never overshoots its target.')


if __name__ == '__main__':
    main()
