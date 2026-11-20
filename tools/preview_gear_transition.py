"""Preview the restored legacy fade and verify native gear visibility gates."""
from dataclasses import replace
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import artwork as art, layout as geo, preview_instruments as hud


def main():
    state = hud.State(speed=250, rpm=11585, gear=3, throttle=1., charge=.75, drs='hidden')
    base = hud.static_base().copy()
    overlay = art.canvas()
    hud.draw_pedals(overlay, state)
    hud.draw_pedal_labels(overlay)
    hud.draw_battery(overlay, state.charge)
    art.label(overlay, geo.SPEED, str(state.speed), weight=650)
    hud.draw_rpm(overlay, state)
    base.alpha_composite(overlay, (0, round(geo.ARTWORK_TOP_PADDING * art.S)))
    crop = (745, 42, 1060, 350)
    font = ImageFont.truetype(str(ROOT / geo.FONT_PATH), 20)
    sequence = [(0., 3), (.45, 4), (.90, 5), (1.35, 6), (1.80, 7),
                (2.25, 8), (2.70, 7), (2.80, 6), (2.90, 5), (3.00, 4)]
    frames = []
    for index in range(102):
        time = index / 30.
        changed, gear = next(event for event in reversed(sequence) if time >= event[0])
        image = base.copy()
        gear_layer = art.canvas()
        hud.draw_gears(gear_layer, replace(state, gear=gear, gear_age=time - changed))
        image.alpha_composite(gear_layer, (0, round(geo.ARTWORK_TOP_PADDING * art.S)))
        shifted_crop = (crop[0], crop[1] + geo.ARTWORK_TOP_PADDING,
                        crop[2], crop[3] + geo.ARTWORK_TOP_PADDING)
        image = art.finish(image).crop(shifted_crop).resize((630, 616), Image.Resampling.LANCZOS)
        panel = Image.new('RGBA', (662, 700), (24, 39, 49, 255))
        panel.alpha_composite(image, (16, 50))
        draw = ImageDraw.Draw(panel)
        draw.text((16, 12), 'Gear changes - original 0.15 s fade', font=font, fill=(236, 248, 253))
        draw.text((16, 672), 'Simulated preview at normal speed', font=font, fill=(175, 201, 217))
        frames.append(panel.convert('RGB'))
    durations = [40 if index % 3 == 1 else 30 for index in range(len(frames))]
    durations[-1] = 600
    frames[0].save(ROOT / 'design/gear-transition-preview.gif', save_all=True,
                   append_images=frames[1:], duration=durations, loop=0,
                   disposal=2, optimize=False)

    sheet = Image.new('RGB', (1100, 470), (24, 39, 49))
    draw = ImageDraw.Draw(sheet)
    for index, elapsed in enumerate((0., .05, .15)):
        image = base.copy()
        gear_layer = art.canvas()
        hud.draw_gears(gear_layer, replace(state, gear=4, gear_age=elapsed))
        image.alpha_composite(gear_layer, (0, round(geo.ARTWORK_TOP_PADDING * art.S)))
        image = art.finish(image).crop((802, 70 + geo.ARTWORK_TOP_PADDING,
                                        940, 235 + geo.ARTWORK_TOP_PADDING))
        image = image.resize((331, 396), Image.Resampling.LANCZOS)
        panel = Image.new('RGBA', image.size, (24, 39, 49, 255))
        panel.alpha_composite(image)
        x = 24 + 361 * index
        sheet.paste(panel.convert('RGB'), (x, 54))
        draw.text((x, 18), f'{elapsed * 1000:.0f} ms', font=font, fill=(236, 248, 253))
    sheet.save(ROOT / 'design/gear-transition-stages.png')
    print('Rendered normal-speed gear-change motion and fade stages.')


if __name__ == '__main__':
    main()
