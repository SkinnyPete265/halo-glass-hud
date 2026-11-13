"""Offline rendering of shared Halo instruments with simulated live inputs."""
from dataclasses import dataclass
from functools import lru_cache
import math
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from . import artwork as art, layout as geo, material as mat, sectors, feature_assets, instruments, rpm_mask
# Keep these shared definitions importable by existing preview recipes.
from .instruments import (BATTERY_BLUE, BATTERY_RED, BATTERY_YELLOW,
                          BATTERY_COLOUR_KEYS, battery_colour, rpm_labels)

S = art.S
BATTERY_CENTRE = geo.BATTERY_CENTRE
BATTERY_WIDTH, BATTERY_HEIGHT = geo.BATTERY_WIDTH, geo.BATTERY_HEIGHT
DRS_CENTRE = geo.DRS_CENTRE
PEDAL_COLOURS = {"brake": (248, 112, 120), "throttle": (67, 230, 154)}

@dataclass(frozen=True)
class State:
    speed: int = 250
    rpm: int = 11585
    gear: int = 6
    throttle: float = 1.0
    brake: float = 0.0
    charge: float = 0.75
    drs: str = "distance"
    drs_distance: int = 100
    gear_age: float = geo.GEAR_FADE_DURATION
    sector_times: tuple = ('--.---', '--.---', '--.---')
    sector_colours: tuple = ('white', 'white', 'white')

def clamp(value):
    return max(0.0, min(1.0, value))



@lru_cache(maxsize=1)
def static_base():
    return art.base()

@lru_cache(maxsize=2)
def pedal_surface(side):
    sign = -1 if side == "brake" else 1
    points = [p for index in range(10) for p in geo.slat_points(sign, index)]
    left = math.floor(min(x for x, y in points) * S)
    top = math.floor(min(y for x, y in points) * S)
    right = math.ceil(max(x for x, y in points) * S) + 1
    bottom = math.ceil(max(y for x, y in points) * S) + 1
    mask = Image.new("L", (right - left, bottom - top))
    draw = ImageDraw.Draw(mask)
    for index in range(10):
        draw.polygon([(round(x * S) - left, round(y * S) - top)
                      for x, y in geo.slat_points(sign, index)], fill=255)
    colour = PEDAL_COLOURS[side]
    amplitude = tuple(min(c * .16, (255 - c) * .80) for c in colour)
    texture = Image.new("RGBA", mask.size)
    pixels = []
    for y in range(texture.height):
        v = (y + .5) / texture.height
        for x in range(texture.width):
            u = (x + .5) / texture.width
            sheen = .30 * math.cos(2 * math.pi * (u - .15))
            sheen += .70 * math.cos(2 * math.pi * (v - .35))
            pixels.append(tuple(round(c + a * sheen)
                                for c, a in zip(colour, amplitude)) + (255,))
    texture.putdata(pixels)
    texture.putalpha(mask)
    return texture, (left, top)

def draw_pedals(image, state):
    for side, fraction in (("brake", state.brake), ("throttle", state.throttle)):
        source, position = pedal_surface(side)
        fill = source.copy()
        cutoff = round(fill.height * (1.0 - clamp(fraction)))
        alpha = fill.getchannel("A")
        alpha.paste(0, (0, 0, fill.width, cutoff))
        fill.putalpha(alpha)
        image.alpha_composite(fill, position)

def draw_battery(image, charge):
    from PIL import ImageChops
    from .feature_assets import battery_layers
    layers = battery_layers()
    colour = Image.new("RGBA",image.size,battery_colour(charge)+(255,))
    image.alpha_composite(layers["housing"])
    image.alpha_composite(ImageChops.multiply(layers["frame"],colour))
    fill = ImageChops.multiply(layers["fill"],colour)
    feather = geo.BATTERY_FILL_FEATHER
    edge = geo.battery_fill_edge(charge)
    row = Image.new("L", (fill.width, 1))
    coverage = [1. if (x+.5)/S < edge else 0. for x in range(fill.width)]
    row.putdata([round(255 * value * value * (3 - 2 * value)) for value in coverage])
    mask = row.resize(fill.size, Image.Resampling.NEAREST)
    if charge == 0.:
        mask.paste(0, (0, 0, mask.width, mask.height))
    elif charge == 1.:
        mask.paste(255, (0, 0, mask.width, mask.height))
    fill.putalpha(ImageChops.multiply(fill.getchannel("A"), mask))
    image.alpha_composite(fill)
    image.alpha_composite(layers["bolt"])


def draw_pedal_labels(image):
    for side, caption in ((-1, "BRAKE"), (1, "THROTTLE")):
        art.label(image, geo.pedal_label(side), caption, color=mat.UNIT_TEXT,
                  glow=True, glow_color=mat.UNIT_GLOW)


def gear_opacity(elapsed):
    # generic_fade_on is the game's 0.15-second ease_out curve, steepness 2.
    progress = clamp(elapsed / geo.GEAR_FADE_DURATION)
    return geo.GEAR_FADE_START + (1. - geo.GEAR_FADE_START) * (1. - (1. - progress) ** 2)


@lru_cache(maxsize=16)
def gear_surface(gear, selected):
    image = instruments.gear_artwork(gear, selected)
    box = image.getbbox()
    return image.crop(box), box[:2]

def draw_gears(image, state):
    for gear in range(1, 9):
        selected = gear == state.gear
        sprite, position = gear_surface(gear, selected)
        if selected:
            sprite = sprite.copy()
            alpha = gear_opacity(state.gear_age)
            sprite.putalpha(sprite.getchannel('A').point(lambda a: round(a * alpha)))
        image.alpha_composite(sprite, position)
    if state.gear in (-1, 0):
        art.label(image, geo.SPECIAL_GEAR, "R" if state.gear == -1 else "N")



@lru_cache(maxsize=1)
def rpm_surface():
    return art.rpm_fill()

def draw_rpm(image, state):
    # This RPM scale is a simulation. Runtime uses the game's 'revs' fraction.
    fraction = clamp(state.rpm / 13000)
    if fraction > 0:
        fill = rpm_mask.clip(rpm_surface(),fraction,S)
        image.alpha_composite(fill)
    number_at, unit_at = rpm_labels(state.rpm)
    for radius, alpha in geo.RPM_NUMBER_GLOW_RINGS:
        for index in range(geo.RPM_NUMBER_GLOW_SAMPLES):
            angle = index * math.tau / geo.RPM_NUMBER_GLOW_SAMPLES
            glow = geo.Text(number_at.x + radius * math.cos(angle),
                            number_at.y + radius * math.sin(angle),
                            number_at.size, number_at.rotation)
            art.label(image, glow, str(state.rpm), color=mat.RPM_NUMBER_GLOW + (alpha,))
    art.label(image, number_at, str(state.rpm))
    for radius, alpha in geo.RPM_LABEL_GLOW_RINGS:
        for index in range(geo.RPM_LABEL_GLOW_SAMPLES):
            angle = index * math.tau / geo.RPM_LABEL_GLOW_SAMPLES
            glow = geo.Text(unit_at.x + radius * math.cos(angle),
                            unit_at.y + radius * math.sin(angle),
                            unit_at.size, unit_at.rotation)
            art.label(image, glow, "RPM", color=mat.UNIT_GLOW + (alpha,))
    art.label(image, unit_at, "RPM", color=mat.UNIT_TEXT)
    return image

@lru_cache(maxsize=1)
def drs_rails():
    from .feature_assets import drs_rails as rails
    return rails()


def draw_drs(image, state, pulse=1.0, reveal=1.0):
    cx, cy = DRS_CENTRE
    if state.drs == "open":
        opened = drs_rails().copy()
        # Both rails expand away from the hub, keeping their curved paths fixed.
        alpha = opened.getchannel("A")
        if reveal < 1.0:
            mask = Image.new("L", image.size)
            draw = ImageDraw.Draw(mask)
            span = (geo.DRS_RAIL_END - geo.DRS_RAIL_START) * clamp(reveal)
            for side in (-1, 1):
                inner = geo.CX + side * (geo.DRS_RAIL_START - geo.CX)
                outer = inner + side * span
                edge = inner - side * 24
                draw.rectangle((round(min(edge, outer) * S), 0,
                                round(max(edge, outer) * S), image.height),
                               fill=255)
            mask = mask.filter(ImageFilter.GaussianBlur(2.0 * S))
            alpha = ImageChops.multiply(alpha, mask)
        opened.putalpha(alpha.point(
            lambda a: round(a * clamp(reveal) * pulse)))
        text_layer = feature_assets.drs_label().copy()
        text_layer.putalpha(text_layer.getchannel("A").point(
            lambda a: round(a * clamp(reveal) * pulse)))
        opened.alpha_composite(text_layer)
        image.alpha_composite(opened)
    elif state.drs == "distance":
        feature_assets.drs_text(image,(cx,cy),f"DRS {state.drs_distance}M")
    elif state.drs == "ready":
        label_width = mat.typeface(round(geo.DRS_STATUS_TEXT_SIZE * S), 700).getlength("DRS") / S
        total = 16 + 8 + label_width
        left = cx - total / 2
        gx = left + 8
        draw = ImageDraw.Draw(image)
        draw.ellipse(((gx - 7) * S, (cy - 7) * S,
                      (gx + 7) * S, (cy + 7) * S),
                     outline=geo.DRS_PROMPT_COLOUR, width=max(1,round(.8 * S)))
        triangle = [(gx, cy - 4), (gx + 4, cy + 3), (gx - 4, cy + 3),
                    (gx, cy - 4)]
        draw.line([(round(x * S), round(y * S)) for x, y in triangle],
                  fill=geo.DRS_PROMPT_COLOUR, width=max(1, round(.8 * S)))
        feature_assets.drs_text(image,(left + 24 + label_width / 2,cy),"DRS")
    elif state.drs != "hidden":
        raise ValueError(f"Unknown DRS preview state {state.drs}")

def render(state, pulse=1.0, reveal=1.0):
    image = static_base().copy()
    sectors.draw(image, state.sector_times, state.sector_colours)
    draw_pedals(image, state)
    draw_pedal_labels(image)
    draw_battery(image, clamp(state.charge))
    draw_gears(image, state)
    art.label(image, geo.SPEED, str(state.speed), weight=650)
    image = draw_rpm(image, state)
    draw_drs(image, state, pulse, reveal)
    return art.finish(image)
