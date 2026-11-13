"""Compare the approved DRS rails with upper rails and a clearer opening."""
from pathlib import Path
import math
import sys
from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import artwork as art, layout as geo, material as mat
from halo import preview_instruments as hud, feature_assets, drs_motion, sectors

FPS = 24


def ease_out(value):
    value = hud.clamp(value)
    return 1. - (1. - value) ** 2


def overlay(rails, highlight, elapsed, duration, flow_delay, active_end=1.6, rail_start=geo.DRS_RAIL_START):
    image = art.canvas()
    if elapsed < 0. or elapsed >= active_end + geo.DRS_CLOSE_DURATION:
        hud.draw_drs(image, hud.State(drs='ready'))
        return art.finish(image)
    closing = elapsed >= active_end
    reveal = (1. - hud.clamp((elapsed - active_end) / geo.DRS_CLOSE_DURATION) ** 2
              if closing else ease_out(elapsed / duration))
    pulse = 1. if closing else .87 + .13 * math.cos(math.pi * max(0., elapsed - duration) / .6)
    limit = rail_start - geo.CX + (drs_motion.OUTER_X - rail_start) * reveal
    row = Image.new('L', (rails.width, 1))
    coverage = [hud.clamp((limit + 2. - abs(x / art.S - geo.CX)) / 4.) for x in range(rails.width)]
    row.putdata([round(255 * value * pulse * reveal) for value in coverage])
    layer = rails.copy()
    layer.putalpha(ImageChops.multiply(layer.getchannel('A'), row.resize(layer.size)))
    image.alpha_composite(layer)
    label = feature_assets.drs_label().copy()
    label.putalpha(label.getchannel('A').point(lambda value: round(value * pulse * reveal)))
    image.alpha_composite(label)
    if not closing and elapsed >= flow_delay:
        phase = ((elapsed - flow_delay) % drs_motion.PERIOD) / drs_motion.PERIOD
        start = rail_start - geo.CX - drs_motion.END_MARGIN - drs_motion.WINDOW_WIDTH / 2
        end = drs_motion.OUTER_X - geo.CX + drs_motion.END_MARGIN + drs_motion.WINDOW_WIDTH / 2
        centre = start + (end - start) * phase
        row.putdata([round(255 * drs_motion.mask_weight(
            .5 + (abs(x / art.S - geo.CX) - centre) / drs_motion.WINDOW_WIDTH) * pulse * reveal)
            for x in range(highlight.width)])
        layer = highlight.copy()
        layer.putalpha(ImageChops.multiply(layer.getchannel('A'), row.resize(layer.size)))
        image.alpha_composite(layer)
    return art.finish(image)


def main():
    old_rails = Image.open(ROOT/'design/drs-alignment-before-rails.png').convert('RGBA')
    old_highlight = Image.open(ROOT/'design/drs-alignment-before-highlight.png').convert('RGBA')
    rails, highlight = feature_assets.drs_rails(), drs_motion.surface()
    assert geo.DRS_RAIL_START == geo.WING_FACE_START + geo.WING_CORNER_RADIUS
    for side in (-1, 1):
        for edge in geo.DRS_RAIL_EDGES:
            for x,y in geo.drs_rail_points(edge)[::30]:
                screen_x = round((geo.CX + side * (x - geo.CX)) * art.S)
                assert rails.getpixel((screen_x, round(y * art.S)))[3] > 200
                upper,lower=geo.wing_face_bounds(x)
                half_width=2.1/math.cos(math.radians(geo.angle(x)))
                assert y+half_width<upper if edge=='top' else y-half_width>lower
    for layer in (rails,highlight):
        alpha=layer.getchannel('A')
        assert alpha.crop((round(geo.CX*art.S),0,round(geo.WING_FACE_START*art.S),alpha.height)).getbbox() is None
    state = hud.State(speed=279, rpm=11249, gear=7, throttle=1., brake=0., charge=.75, drs='hidden',
                      sector_times=('29.531', '19.094', '--.---'),
                      sector_colours=('yellow', 'yellow', 'white'))
    background = Image.open(ROOT/'design/reference/visibility-gameplay.png').convert('RGBA').crop((350,180,1550,620))
    base = Image.alpha_composite(background, hud.render(state))
    frames = []
    for index in range(118):
        time = index / FPS
        elapsed = time % 2.45 - .35
        current = Image.alpha_composite(base, overlay(old_rails, old_highlight, elapsed,
                                                     geo.DRS_OPEN_DURATION,geo.DRS_OPEN_DURATION,rail_start=745.))
        candidate = Image.alpha_composite(base, overlay(rails, highlight, elapsed,
                                                       geo.DRS_OPEN_DURATION, geo.DRS_OPEN_DURATION))
        panel = Image.new('RGB', (1000, 824), (24, 39, 49))
        draw = ImageDraw.Draw(panel)
        for top, title, image in ((42, 'Previous rail alignment', current), (428, 'Aligned starts · exterior rails · rounded tips', candidate)):
            panel.paste(image.resize((960,352), Image.Resampling.LANCZOS).convert('RGB'), (20, top))
            draw.text((20, top-34), title, font=mat.typeface(22,550), fill=(236,248,253))
        draw.text((20,798), 'Simulated 0.30 s extension, then travelling highlights. In-game verification pending.',
                  font=mat.typeface(16,500), fill=(175,201,217))
        frames.append(panel)
    samples = Image.new('RGB', (500, 412*10))
    for index, frame in enumerate(frames[::12]):
        samples.paste(frame.resize((500,412)), (0, index*412))
    palette = samples.quantize(colors=249)
    colours = palette.getpalette()
    exact = [colour[:3] for colour in sectors.COLOURS.values()] + [(67,249,160), (144,255,199), (230,255,242)]
    for index, colour in enumerate(exact, start=249):
        colours[index*3:index*3+3] = colour
    palette.putpalette(colours)
    indexed = [frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
    durations = [round((index+1)*100/FPS)*10-round(index*100/FPS)*10 for index in range(len(frames))]
    indexed[0].save(ROOT/'design/drs-top-bottom-preview.gif', save_all=True,
                    append_images=indexed[1:], duration=durations, loop=0, disposal=1, optimize=True)
    fully_open = Image.alpha_composite(base, overlay(rails, highlight, .9,
                                                    geo.DRS_OPEN_DURATION, geo.DRS_OPEN_DURATION))
    fully_open.convert('RGB').save(ROOT/'design/drs-top-bottom-open.png')
    stages = Image.new('RGB',(1200,390),(24,39,49))
    draw = ImageDraw.Draw(stages)
    for index, elapsed in enumerate((.05,.12,.20,.30)):
        image = Image.alpha_composite(base,overlay(rails,highlight,elapsed,
                                                   geo.DRS_OPEN_DURATION,geo.DRS_OPEN_DURATION))
        image = image.crop((735,0,1045,355)).resize((294,337),Image.Resampling.LANCZOS)
        stages.paste(image.convert('RGB'),(index*300+3,45))
        draw.text((index*300+12,12), f'{elapsed:.2f} s',font=mat.typeface(20,550),fill=(236,248,253))
    stages.save(ROOT/'design/drs-opening-extension-stages.png')
    print('Verified four rail paths and rendered opening, active and closing comparisons.')


if __name__ == '__main__':
    main()
