"""Approved glass material functions, ported into the shared v2 layout."""
import math
from array import array
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from .layout import (
    WIDTH, HEIGHT, CX, CY, RADIUS, angle, arc_length, slat_points, point,
    WING_FACE_TOP, WING_FACE_BOTTOM, PEDAL_INNER_RADIUS, PEDAL_OUTER_RADIUS,
    WING_FACE_START, WING_FACE_END, WING_EFFECT_END, WING_CORNER_RADIUS,
)
from . import layout as geo

S = 3
FONT = str(Path(__file__).resolve().parents[1] / "assets/fonts/Saira/Saira.ttf")


def sync_layout():
    """Refresh copied geometry constants after tuning values change in-process."""
    global WIDTH, HEIGHT, CX, CY, RADIUS, WING_FACE_TOP
    global WING_FACE_BOTTOM, PEDAL_INNER_RADIUS, PEDAL_OUTER_RADIUS
    global WING_FACE_START, WING_FACE_END, WING_EFFECT_END, WING_CORNER_RADIUS
    WIDTH, HEIGHT = geo.WIDTH, geo.HEIGHT
    CX, CY, RADIUS = geo.CX, geo.CY, geo.RADIUS
    WING_FACE_TOP, WING_FACE_BOTTOM = geo.WING_FACE_TOP, geo.WING_FACE_BOTTOM
    PEDAL_INNER_RADIUS, PEDAL_OUTER_RADIUS = geo.PEDAL_INNER_RADIUS, geo.PEDAL_OUTER_RADIUS
    WING_FACE_START, WING_FACE_END = geo.WING_FACE_START, geo.WING_FACE_END
    WING_EFFECT_END, WING_CORNER_RADIUS = geo.WING_EFFECT_END, geo.WING_CORNER_RADIUS
CYAN = (76, 159, 203)
WHITE = (236, 248, 253)
ICE_CORE = (179, 216, 244)
WING_EXTENSION_CORE_ALPHA = 176
DEFAULT_RACE_EDGE_VARIANT = "B+4"
RACE_EDGE_VARIANTS = {
    "current": {
        "outline_width": .8, "outline_alpha": 168,
        "reflection_alpha": 35., "reflection_sigma": .55,
        "tail_alpha": 176., "tail_radius": 1.5, "tail_sigma": .7,
        "edge_glow_alpha": 0., "edge_glow_sigma": 3.0,
        "edge_glow_layers": 1,
        "outline_glow_alpha": 0, "outline_glow_sigma": 3.5,
        "outline_glow_layers": 1,
        "circle_glow_alpha": 0, "circle_glow_sigma": 6.0,
        "circle_glow_layers": 1,
    },
    "A": {
        "outline_width": 1.1, "outline_alpha": 122,
        "reflection_alpha": 26., "reflection_sigma": .78,
        "tail_alpha": 136., "tail_radius": 2.25, "tail_sigma": .9,
        "edge_glow_alpha": 0., "edge_glow_sigma": 3.0,
        "edge_glow_layers": 1,
        "outline_glow_alpha": 0, "outline_glow_sigma": 3.5,
        "outline_glow_layers": 1,
        "circle_glow_alpha": 0, "circle_glow_sigma": 6.0,
        "circle_glow_layers": 1,
    },
    "B": {
        "outline_width": 1.1, "outline_alpha": 122,
        "reflection_alpha": 26., "reflection_sigma": .78,
        "tail_alpha": 136., "tail_radius": 2.25, "tail_sigma": .9,
        "edge_glow_alpha": 18., "edge_glow_sigma": 3.2,
        "edge_glow_layers": 1,
        "outline_glow_alpha": 48, "outline_glow_sigma": 3.5,
        "outline_glow_layers": 1,
        "circle_glow_alpha": 36, "circle_glow_sigma": 6.0,
        "circle_glow_layers": 1,
    },
}
RACE_EDGE_VARIANTS["B+"] = {
    **RACE_EDGE_VARIANTS["B"],
    "edge_glow_layers": 2,
    "outline_glow_layers": 2,
    "circle_glow_layers": 2,
}
for _layers in (3, 4):
    RACE_EDGE_VARIANTS[f"B+{_layers}"] = {
        **RACE_EDGE_VARIANTS["B+"],
        "edge_glow_layers": _layers,
        "outline_glow_layers": _layers,
        "circle_glow_layers": _layers,
    }
FILTERED_RACE_EDGE_VARIANTS = frozenset(("B", "B+", "B+3", "B+4"))
ICE_GLOW = (55, 132, 194)
UNIT_TEXT = (211, 232, 243, 245)
UNIT_GLOW = (179, 216, 244)
RPM_NUMBER_GLOW = (101, 181, 222)
GEAR_IDLE_CORE = (239, 248, 253)
GEAR_SELECTED_CORE = (215, 235, 249)
ROOT_SHADE_FRACTION = .20
ROOT_SHADE_ALPHA = 88.
WING_SMOKE_ALPHA = 15.
FACET_ALPHA = 120.
WING_TIP_FADE_WIDTH = 32.0


@lru_cache(maxsize=96)
def typeface(size,weight=600):
    font=ImageFont.truetype(FONT,size)
    font.set_variation_by_axes([weight,100])
    return font

def stroke(image,points,color,width=1.,glow=0.):
    layer=Image.new('RGBA',image.size);draw=ImageDraw.Draw(layer)
    draw.line([(round(x*S),round(y*S)) for x,y in points],fill=color,width=max(1,round(width*S)),joint='curve')
    if glow:
        light=layer.filter(ImageFilter.GaussianBlur(glow*S))
        image=Image.alpha_composite(image,light)
    return Image.alpha_composite(image,layer)


def _compose_stroke_mask(image, mask, offset, color, glow, prefilter_core=False):
    """Keep glow on the authored mask and optionally prefilter only the core."""
    original = Image.new('RGBA', mask.size, color[:3] + (0,))
    original.putalpha(mask)
    result = image.copy()
    if glow:
        result.alpha_composite(
            original.filter(ImageFilter.GaussianBlur(glow * S)), offset
        )
    if prefilter_core:
        core = Image.new('RGBA', mask.size, color[:3] + (0,))
        core.putalpha(_box_filter_alpha_3x3(mask))
    else:
        core = original
    result.alpha_composite(core, offset)
    return result


def circle_stroke(image, centre, radius, color, width, glow,
                  prefilter_core=False):
    """Use subpixel distance coverage for a continuous circular rim."""
    margin = radius + width / 2 + glow * 4 + 1
    left = math.floor((centre[0] - margin) * S)
    top = math.floor((centre[1] - margin) * S)
    right = math.ceil((centre[0] + margin) * S)
    bottom = math.ceil((centre[1] + margin) * S)
    mask = Image.new('L', (right - left, bottom - top))
    pixels = mask.load()
    for yy in range(mask.height):
        dy = (top + yy + .5) / S - centre[1]
        for xx in range(mask.width):
            dx = (left + xx + .5) / S - centre[0]
            distance = abs(math.hypot(dx, dy) - radius)
            coverage = max(0., min(1., .5 + (width / 2 - distance) * S))
            pixels[xx, yy] = round(color[3] * coverage)
    # The local bounds include several blank texels around the stroke; the
    # 3x3 filter therefore has its full one-texel neighbourhood at the core.
    return _compose_stroke_mask(
        image, mask, (left, top), color, glow, prefilter_core
    )


def circle_glow(image, centre, radius, color, width, blur, layers=1):
    """Add only the soft halo of a ring, leaving its crisp core independent."""
    margin = radius + width / 2 + blur * 4 + 1
    left = math.floor((centre[0] - margin) * S)
    top = math.floor((centre[1] - margin) * S)
    right = math.ceil((centre[0] + margin) * S)
    bottom = math.ceil((centre[1] + margin) * S)
    mask = Image.new('L', (right - left, bottom - top))
    pixels = mask.load()
    for yy in range(mask.height):
        dy = (top + yy + .5) / S - centre[1]
        for xx in range(mask.width):
            dx = (left + xx + .5) / S - centre[0]
            distance = abs(math.hypot(dx, dy) - radius)
            coverage = max(0., min(1., .5 + (width / 2 - distance) * S))
            pixels[xx, yy] = round(color[3] * coverage)
    halo = Image.new('RGBA', mask.size, color[:3] + (0,))
    halo_alpha = mask.filter(ImageFilter.GaussianBlur(blur * S))
    halo.putalpha(_repeat_alpha_layers(halo_alpha, layers))
    image.alpha_composite(halo, (left, top))
    return image


def arc_stroke(image, centre, radius, start_angle, end_angle, color, width, glow,
               prefilter_core=False):
    """Rasterize a finite circular arc from pixel-centre distance coverage."""
    sweep = end_angle - start_angle
    if sweep >= 360.:
        return circle_stroke(
            image, centre, radius, color, width, glow, prefilter_core
        )
    margin = radius + width / 2 + glow * 4 + 1
    left = math.floor((centre[0] - margin) * S)
    top = math.floor((centre[1] - margin) * S)
    right = math.ceil((centre[0] + margin) * S)
    bottom = math.ceil((centre[1] + margin) * S)
    mask = Image.new('L', (right - left, bottom - top))
    pixels = mask.load()
    start = math.radians(start_angle)
    end = math.radians(end_angle)
    start_x = centre[0] + radius * math.cos(start)
    start_y = centre[1] + radius * math.sin(start)
    end_x = centre[0] + radius * math.cos(end)
    end_y = centre[1] + radius * math.sin(end)
    start_turn = start_angle % 360.
    for yy in range(mask.height):
        y = (top + yy + .5) / S
        dy = y - centre[1]
        for xx in range(mask.width):
            x = (left + xx + .5) / S
            dx = x - centre[0]
            distance_from_centre = math.hypot(dx, dy)
            turn = math.degrees(math.atan2(dy, dx)) % 360.
            along = (turn - start_turn) % 360.
            if along <= sweep:
                distance = abs(distance_from_centre - radius)
            else:
                distance = min(math.hypot(x - start_x, y - start_y),
                               math.hypot(x - end_x, y - end_y))
            coverage = max(0., min(1., .5 + (width / 2 - distance) * S))
            pixels[xx, yy] = round(color[3] * coverage)
    return _compose_stroke_mask(
        image, mask, (left, top), color, glow, prefilter_core
    )


def text(image,x,y,value,size,color=WHITE+(255,),rotation=0.,width_scale=1.,
         glow=False,weight=600,outline=0.,glow_color=ICE_GLOW,
         outline_color=(4,17,27,210)):
    style = geo.STYLE
    size *= style['text_size'] / 100.0
    outline *= style['text_outline']
    glow_scale = style['text_glow']
    glow_strength = style['text_glow_strength'] / 100.0
    sprite=Image.new('RGBA',(450,150));draw=ImageDraw.Draw(sprite)
    draw.text((225,75),value,font=typeface(round(size*S),weight),anchor='mm',
              fill=color,stroke_width=round(outline*S),stroke_fill=outline_color)
    if width_scale!=1.:
        sprite=sprite.resize((round(sprite.width*width_scale),sprite.height),Image.Resampling.LANCZOS)
    sprite=sprite.rotate(-rotation,resample=Image.Resampling.BICUBIC,expand=True)
    if glow:
        alpha=sprite.getchannel('A')
        for radius,opacity in ((2.2,.22),(.65,.48)):
            halo=Image.new('RGBA',sprite.size,glow_color+(0,))
            blur = radius * glow_scale
            halo.putalpha(alpha.filter(ImageFilter.GaussianBlur(blur*S)).point(lambda a:round(a*opacity*glow_strength)))
            image.alpha_composite(halo,(round(x*S-sprite.width/2),round(y*S-sprite.height/2)))
    image.alpha_composite(sprite,(round(x*S-sprite.width/2),round(y*S-sprite.height/2)))


def wing_texture_frame(image, padding=None, top_padding=None):
    """Pad a HUD texture and append the approved outside wing-edge tails."""
    from . import layout as geo

    padding = geo.WING_TEXTURE_PADDING if padding is None else padding
    if top_padding is None:
        top_padding = max(0., image.height / S - HEIGHT)
    frame_width = WIDTH + 2 * padding
    frame_height = HEIGHT + top_padding
    frame = Image.new('RGBA', (frame_width * S, round(frame_height * S)))
    frame.alpha_composite(image, (padding * S, 0))
    edge_tail = wing_edge_effects(
        padding=padding,
        draw_from=geo.WING_TEXTURE_NATIVE_END_DISTANCE,
        draw_to=geo.WING_TEXTURE_END - CX,
        context_split=geo.WING_TEXTURE_NATIVE_END_DISTANCE,
        top_padding=top_padding,
    )
    frame.alpha_composite(edge_tail)
    return frame


def rounded_stroke(image, points, colour, width=1., glow=0.):
    """Antialiased line and round caps share one continuous coverage mask."""
    padding = math.ceil((width / 2 + glow * 3 + 2) * S)
    left = math.floor(min(x for x, y in points) * S) - padding
    top = math.floor(min(y for x, y in points) * S) - padding
    right = math.ceil(max(x for x, y in points) * S) + padding + 1
    bottom = math.ceil(max(y for x, y in points) * S) + padding + 1
    factor = 2
    mask = Image.new('L', ((right-left)*factor, (bottom-top)*factor))
    draw = ImageDraw.Draw(mask)
    path = [((x*S-left)*factor, (y*S-top)*factor) for x,y in points]
    radius = width*S*factor/2
    draw.line(path,fill=255,width=round(width*S*factor),joint='curve')
    for x,y in (path[0],path[-1]):
        draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=255)
    mask = mask.resize((right-left,bottom-top),Image.Resampling.LANCZOS)
    mask = mask.point(lambda value: round(value*colour[3]/255))
    layer = Image.new('RGBA',mask.size,colour[:3]+(0,))
    layer.putalpha(mask)
    if glow:
        image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(glow*S)),(left,top))
    image.alpha_composite(layer,(left,top))
    return image


def _samples(start, stop, max_step=.5):
    count = max(1, math.ceil(abs(stop - start) / max_step))
    return [start + (stop - start) * index / count
            for index in range(count + 1)]


_COVERAGE_4X4 = (.125, .375, .625, .875)


def _subpixel_band_coverage(xx, yy, bounds_at, x_direction=1):
    """Average a curved band's coverage over one 3x texture pixel."""
    covered = 0
    for offset_x in _COVERAGE_4X4:
        x = (xx + x_direction * offset_x) / S
        upper, lower = bounds_at(x)
        for offset_y in _COVERAGE_4X4:
            y = (yy + offset_y) / S
            covered += upper <= y <= lower
    return covered / 16.


def _subpixel_boundary_span(xx, bounds_at, x_direction=1):
    """Return the rows touched by the top and bottom of a curved band."""
    edge_samples = [bounds_at((xx + x_direction * offset_x) / S)
                    for offset_x in _COVERAGE_4X4]
    top_min = min(upper for upper, _ in edge_samples) * S
    top_max = max(upper for upper, _ in edge_samples) * S
    bottom_min = min(lower for _, lower in edge_samples) * S
    bottom_max = max(lower for _, lower in edge_samples) * S
    first = math.floor(top_min) - 1
    last = math.ceil(bottom_max) + 1
    return first, last, top_min, top_max, bottom_min, bottom_max


def _is_boundary_row(yy, top_min, top_max, bottom_min, bottom_max):
    return ((yy <= top_max and yy + 1 >= top_min)
            or (yy <= bottom_max and yy + 1 >= bottom_min))


def _band_row_coverage(xx, yy, bounds_at, top_min, top_max,
                       bottom_min, bottom_max, x_direction=1):
    """Classify padded band rows, sampling only rows that touch a boundary."""
    if _is_boundary_row(yy, top_min, top_max, bottom_min, bottom_max):
        return _subpixel_band_coverage(xx, yy, bounds_at, x_direction)
    if yy >= top_max and yy + 1 <= bottom_min:
        return 1.
    return 0.


def _outline_run_coverage(size, runs, width):
    """Return distance-rasterized coverage blended into legacy corner joins."""
    image_width, image_height = size
    pixel_count = image_width * image_height
    sample_bits = array('H', [0]) * pixel_count
    blend_weights = bytearray(pixel_count)
    offsets = _COVERAGE_4X4
    radius = width / 2.
    blend_length = 4.0
    pixel_margin = math.sqrt(2.) * .5 / S
    expanded_radius = radius + pixel_margin

    for points, corner_at_end in runs:
        lengths = [0.]
        for first, second in zip(points, points[1:]):
            lengths.append(lengths[-1] + math.hypot(
                second[0] - first[0], second[1] - first[1]
            ))
        total_length = lengths[-1]

        for segment_index, (first, second) in enumerate(zip(points, points[1:])):
            ax, ay = first
            bx, by = second
            vx, vy = bx - ax, by - ay
            length_squared = vx * vx + vy * vy
            if length_squared <= 1e-12:
                continue
            segment_length = math.sqrt(length_squared)
            left = max(0, math.floor((min(ax, bx) - expanded_radius) * S) - 1)
            right = min(image_width - 1,
                        math.ceil((max(ax, bx) + expanded_radius) * S) + 1)
            top = max(0, math.floor((min(ay, by) - expanded_radius) * S) - 1)
            bottom = min(image_height - 1,
                         math.ceil((max(ay, by) + expanded_radius) * S) + 1)

            for py in range(top, bottom + 1):
                centre_y = (py + .5) / S
                for px in range(left, right + 1):
                    centre_x = (px + .5) / S
                    centre_t = max(0., min(1., (
                        (centre_x - ax) * vx + (centre_y - ay) * vy
                    ) / length_squared))
                    centre_dx = centre_x - (ax + centre_t * vx)
                    centre_dy = centre_y - (ay + centre_t * vy)
                    if centre_dx * centre_dx + centre_dy * centre_dy > expanded_radius ** 2:
                        continue

                    along = lengths[segment_index] + centre_t * segment_length
                    distance_from_corner = (total_length - along
                                             if corner_at_end else along)
                    join_weight = _smooth(distance_from_corner / blend_length)
                    flat_index = py * image_width + px
                    weight = round(join_weight * 255)
                    if weight > blend_weights[flat_index]:
                        blend_weights[flat_index] = weight

                    bits = sample_bits[flat_index]
                    for sample_y, offset_y in enumerate(offsets):
                        sample_py = (py + offset_y) / S
                        for sample_x, offset_x in enumerate(offsets):
                            bit = 1 << (sample_y * 4 + sample_x)
                            if bits & bit:
                                continue
                            sample_px = (px + offset_x) / S
                            t = max(0., min(1., (
                                (sample_px - ax) * vx + (sample_py - ay) * vy
                            ) / length_squared))
                            dx = sample_px - (ax + t * vx)
                            dy = sample_py - (ay + t * vy)
                            if dx * dx + dy * dy <= radius * radius:
                                bits |= bit
                    sample_bits[flat_index] = bits

    coverage = bytearray(pixel_count)
    for index, bits in enumerate(sample_bits):
        if bits:
            coverage[index] = round(255 * bits.bit_count() / 16.)
    return Image.frombytes('L', size, bytes(coverage)), Image.frombytes(
        'L', size, bytes(blend_weights)
    )


def _box_filter_alpha_3x3(mask):
    """Apply one normalized 3x3 box pass to a grayscale alpha mask."""
    if mask.mode != 'L':
        raise ValueError('The edge prefilter expects a grayscale alpha mask')
    return mask.filter(ImageFilter.Kernel(
        (3, 3), (1, 1, 1, 1, 1, 1, 1, 1, 1), scale=9
    ))


def _repeat_alpha_layers(mask, layers=1):
    """Composite identical same-colour glow layers using their exact alpha union."""
    if not isinstance(layers, int) or layers < 1:
        raise ValueError('Glow layer count must be a positive integer')
    if layers == 1:
        return mask
    values = mask.tobytes()
    for _ in range(layers - 1):
        values = bytes(
            255 - ((255 - value) * (255 - value) + 127) // 255
            for value in values
        )
    return Image.frombytes('L', mask.size, values)


def _wing_outline_coverage(image_size, path, long_runs, width):
    """Keep the legacy corner/core mask and replace only long-run coverage."""
    legacy = rounded_stroke(
        Image.new('RGBA', image_size), path, (255, 255, 255, 255), width, 0.
    ).getchannel('A')
    analytic, blend = _outline_run_coverage(image_size, long_runs, width)
    old_values = bytearray(legacy.tobytes())
    new_values = analytic.tobytes()
    blend_values = blend.tobytes()
    for index, weight in enumerate(blend_values):
        if weight:
            fraction = weight / 255.
            old_values[index] = round(
                old_values[index] * (1. - fraction)
                + new_values[index] * fraction
            )
    return Image.frombytes('L', image_size, bytes(old_values))


def _wing_outline_layer(image_size, coverage, colour, glow):
    mask = coverage.point(lambda value: round(value * colour[3] / 255.))
    stroke = Image.new('RGBA', image_size, colour[:3] + (0,))
    stroke.putalpha(mask)
    layer = Image.new('RGBA', image_size)
    if glow:
        layer.alpha_composite(stroke.filter(ImageFilter.GaussianBlur(glow * S)))
    layer.alpha_composite(stroke)
    return layer


def _wing_outline_candidate_stroke(image, path, long_runs, colour, width, glow,
                                   style, prefilter=False):
    """Blend a broader, lower-peak long run into the unchanged face contour."""
    legacy = rounded_stroke(
        Image.new('RGBA', image.size), path, (255, 255, 255, 255), width, 0.
    ).getchannel('A')
    long_coverage, blend = _outline_run_coverage(
        image.size, long_runs, style['outline_width']
    )
    filtered_long_coverage = (
        _box_filter_alpha_3x3(long_coverage) if prefilter else long_coverage
    )
    old_alpha = legacy.tobytes()
    long_alpha = long_coverage.tobytes()
    filtered_long_alpha = filtered_long_coverage.tobytes()
    blend_values = blend.tobytes()
    original_alpha = bytearray(len(old_alpha))
    alpha = bytearray(len(old_alpha))
    for index, weight in enumerate(blend_values):
        fraction = weight / 255.
        corner_alpha = old_alpha[index] * colour[3] / 255. * (1. - fraction)
        original_long_alpha = long_alpha[index] * style['outline_alpha'] / 255. * fraction
        original_alpha[index] = round(corner_alpha + original_long_alpha)
        filtered_long_alpha_value = (
            filtered_long_alpha[index] * style['outline_alpha'] / 255. * fraction
        )
        alpha[index] = round(corner_alpha + filtered_long_alpha_value)

    # Candidate B keeps its glow tied to the original, unfiltered masks. Only
    # the crisp long-run core receives the prefilter before it joins the legacy
    # corner and short slat-side contour.
    glow_core = Image.new('RGBA', image.size, colour[:3] + (0,))
    glow_core.putalpha(Image.frombytes('L', image.size, bytes(original_alpha)))
    core = Image.new('RGBA', image.size, colour[:3] + (0,))
    core.putalpha(Image.frombytes('L', image.size, bytes(alpha)))
    layer = Image.new('RGBA', image.size)
    if glow:
        layer.alpha_composite(glow_core.filter(ImageFilter.GaussianBlur(glow * S)))
    soft_alpha = style['outline_glow_alpha']
    if soft_alpha:
        run_alpha = bytearray(len(long_alpha))
        for index, value in enumerate(long_alpha):
            run_alpha[index] = round(value * blend_values[index] * soft_alpha / 65025.)
        soft = Image.new('RGBA', image.size, colour[:3] + (0,))
        soft_alpha_mask = Image.frombytes('L', image.size, bytes(run_alpha)).filter(
            ImageFilter.GaussianBlur(style['outline_glow_sigma'] * S)
        )
        soft.putalpha(_repeat_alpha_layers(
            soft_alpha_mask, style.get('outline_glow_layers', 1)
        ))
        layer.alpha_composite(soft)
    layer.alpha_composite(core)
    image.alpha_composite(layer)
    return image


def _wing_outline_stroke(image, path, long_runs, colour, width, glow,
                         variant='current'):
    if variant in ('A', 'B', 'B+', 'B+3', 'B+4'):
        return _wing_outline_candidate_stroke(
            image, path, long_runs, colour, width, glow,
            RACE_EDGE_VARIANTS[variant],
            prefilter=(variant in FILTERED_RACE_EDGE_VARIANTS)
        )
    coverage = _wing_outline_coverage(image.size, path, long_runs, width)
    layer = _wing_outline_layer(image.size, coverage, colour, glow)
    image.alpha_composite(layer)
    return image


def glass_wings(variant=None):
    variant = DEFAULT_RACE_EDGE_VARIANT if variant is None else variant
    if variant not in RACE_EDGE_VARIANTS:
        raise ValueError('Unknown race-edge variant ' + str(variant))
    image=Image.new('RGBA',(WIDTH*S,HEIGHT*S));pixels=image.load()
    # A tinted instrument face isolates the lettering from bright scenery.
    # The surrounding glass and outer ends retain their soft transparency.
    for xx in range(round((2*CX-WING_EFFECT_END)*S),round(WING_EFFECT_END*S)+1):
        x=xx/S;y0,y1=geo.wing_backing_bounds(x)
        bounds_at=geo.wing_backing_bounds
        first,last,top_min,top_max,bottom_min,bottom_max = _subpixel_boundary_span(xx,bounds_at)
        first=max(0,first);last=min(image.height-1,last)
        fade=min(1.,max(0.,min(x-75,WING_EFFECT_END-x)/48.))
        for yy in range(first,last+1):
            coverage = _band_row_coverage(
                xx, yy, bounds_at, top_min, top_max, bottom_min, bottom_max
            )
            if coverage <= 0.:
                continue
            t=(yy/S-y0)/(y1-y0)
            highlight=math.exp(-((t-.07)/.075)**2)
            reflection=math.exp(-((t-.33)/.12)**2)
            lower=math.exp(-((t-.90)/.12)**2)
            material_alpha=round((WING_SMOKE_ALPHA+17*highlight+5*reflection+6*lower)*fade)
            alpha=round(material_alpha*coverage)
            pixels[xx,yy]=(round(28+45*highlight),round(49+64*highlight),round(59+67*highlight),alpha)
    # Separate thin glass facets; matching mirrored base geometry.
    facet=Image.new('RGBA',image.size);facet_pixels=facet.load()
    for side in (-1,1):
        for xx in range(round(WING_FACE_START*S),round(WING_FACE_END*S)+1):
            x=xx/S;y0,y1=geo.wing_face_edges(x)
            bounds_at=geo.wing_face_edges
            x_direction = 1 if side > 0 else -1
            first,last,top_min,top_max,bottom_min,bottom_max = _subpixel_boundary_span(
                xx,bounds_at,x_direction
            )
            coverage_start = math.ceil(
                (WING_FACE_START + WING_CORNER_RADIUS) * S
                - (min(_COVERAGE_4X4) if x_direction > 0 else -max(_COVERAGE_4X4))
            )
            if xx >= coverage_start:
                first=max(0,first);last=min(image.height-1,last)
            else:
                first=round(y0*S);last=min(image.height-1,round(y1*S))
            fade=_smooth((WING_FACE_END-x)/WING_TIP_FADE_WIDTH)
            along=(arc_length(x)-arc_length(WING_FACE_START))/(arc_length(WING_EFFECT_END)-arc_length(WING_FACE_START))
            root=max(0.,1.-along/ROOT_SHADE_FRACTION)
            root=root*root*(3.-2.*root)
            for yy in range(first,last+1):
                if xx >= coverage_start:
                    coverage = _band_row_coverage(
                        xx, yy, bounds_at, top_min, top_max, bottom_min, bottom_max,
                        x_direction,
                    )
                    if coverage <= 0.:
                        continue
                else:
                    coverage=1.
                y=yy/S
                qx=max(WING_FACE_START+WING_CORNER_RADIUS-x,0.)
                qy=max(y0+WING_CORNER_RADIUS-y,0.,y-(y1-WING_CORNER_RADIUS))
                if qx and qy and qx*qx+qy*qy>WING_CORNER_RADIUS**2:continue
                screen_x=xx if side>0 else round(2*CX*S)-xx
                t=(y-y0)/(y1-y0)
                grain=(((xx*37+yy*73)^(xx*yy*11))&7)/7.-.5
                smoke=ROOT_SHADE_ALPHA*root*(.55+.45*math.sin(math.pi*t))
                base_alpha=FACET_ALPHA*fade
                alpha=round(base_alpha+(255-base_alpha)*smoke/255)
                alpha=round(alpha*coverage)
                rgb=tuple(round(base+(dark-base)*root*.65+grain*root*1.2)
                          for base,dark in ((7,3),(22,10),(29,22)))
                facet_pixels[screen_x,yy]=rgb+(alpha,)
    image=Image.alpha_composite(image,facet)
    # Broken highlights and open component contours carry the curvature.
    for side in (-1,1):
        # Rounded inner corner, open outer ends, stronger local edge next to
        # the information rather than outlining the entire backing.
        inner=WING_FACE_START;r=WING_CORNER_RADIUS;end=WING_FACE_END
        face_top,face_bottom=WING_FACE_TOP,WING_FACE_BOTTOM
        top_x = _samples(end, inner + r)
        top_run=[(x,geo.wing_face_edges(x)[0]) for x in top_x]
        path=list(top_run)
        path += [point(inner+r+r*math.cos(a),face_top+r+r*math.sin(a))
                 for a in (-math.pi/2-math.pi*i/64 for i in range(33))]
        path += [point(inner,face_bottom-r)]
        path += [point(inner+r+r*math.cos(a),face_bottom-r+r*math.sin(a))
                 for a in (math.pi-math.pi*i/64 for i in range(33))]
        bottom_x = _samples(inner + r, end)
        bottom_run=[(x,geo.wing_face_edges(x)[1]) for x in bottom_x]
        path += bottom_run[1:]
        if side<0:
            path=[(2*CX-x,y) for x,y in path]
            top_run=[(2*CX-x,y) for x,y in top_run]
            bottom_run=[(2*CX-x,y) for x,y in bottom_run]
        image=_wing_outline_stroke(
            image, path, ((top_run, True), (bottom_run, False)),
            CYAN+(168,), .8, 2.0, variant,
        )
    return Image.alpha_composite(wing_edge_effects(
        variant=variant,
        context_split=geo.WING_TEXTURE_NATIVE_END_DISTANCE,
    ), image)


def _smooth(value):
    value = max(0., min(1., value))
    return value * value * (3. - 2. * value)


def pedal_backing():
    """Smoked backing follows the slats' circular sides and angled end caps."""
    image = Image.new('RGBA', (WIDTH * S, HEIGHT * S))
    pixels = image.load()
    points = [point for index in range(10) for point in slat_points(1, index)]
    upper = slat_points(1, 9)
    lower = slat_points(1, 0)
    slope = (upper[1][1] - upper[0][1]) / (upper[1][0] - upper[0][0])
    normal = math.hypot(1., slope)
    top = (upper[0][1] - CY - slope * (upper[0][0] - CX)) / normal - 2.5
    bottom = (lower[3][1] - CY - slope * (lower[3][0] - CX)) / normal + 2.5
    inner, outer = PEDAL_INNER_RADIUS - 2.5, PEDAL_OUTER_RADIUS + 2.5
    left = math.floor((min(x for x, y in points) - 7.) * S)
    right = math.ceil((max(x for x, y in points) + 7.) * S)
    first = math.floor((min(y for x, y in points) - 7.) * S)
    last = math.ceil((max(y for x, y in points) + 7.) * S)
    corner = 3.0
    for yy in range(first, last + 1):
        y = yy / S
        for xx in range(left, right + 1):
            x = xx / S
            radius = math.hypot(x - CX, y - CY)
            depth = (y - CY - slope * (x - CX)) / normal
            edge = min(radius - inner, outer - radius, depth - top, bottom - depth)
            radial_corner = max(inner + corner - radius, radius - (outer - corner), 0.)
            cap_corner = max(top + corner - depth, depth - (bottom - corner), 0.)
            if radial_corner > 0. and cap_corner > 0.:
                edge = min(edge, corner - math.hypot(radial_corner, cap_corner))
            coverage = _smooth((edge + .5) / 1.5)
            if coverage == 0.:
                continue
            u = (radius - inner) / (outer - inner)
            v = (depth - top) / (bottom - top)
            sheen = math.exp(-((u - .18) / .25) ** 2) * (.55 + .45 * (1. - v))
            colour = (round(5. + 8. * sheen), round(18. + 20. * sheen),
                      round(27. + 26. * sheen), round((231. - 15. * sheen) * coverage))
            pixels[xx, yy] = colour
            pixels[round(2 * CX * S) - xx, yy] = colour
    return image


def pedal_accents():
    image = Image.new('RGBA', (WIDTH * S, HEIGHT * S))
    pixels = image.load()
    inner, outer = PEDAL_OUTER_RADIUS + 4., 159.
    edges = [slat_points(1, index)[corner]
             for index in range(10) for corner in (1, 2)]
    top = min(y for x, y in edges)
    bottom = max(y for x, y in edges)
    maximum_y = max(abs(top - CY), abs(bottom - CY))
    left = math.floor((CX + math.sqrt(inner ** 2 - maximum_y ** 2)) * S)
    right = math.ceil((CX + outer) * S)
    for yy in range(math.floor(top * S), math.ceil(bottom * S)):
        y = yy / S
        cap = _smooth((y - top) / 7.) * _smooth((bottom - y) / 7.)
        for xx in range(left, right + 1):
            x = xx / S
            radius = math.hypot(x - CX, y - CY)
            if not inner <= radius <= outer:
                continue
            u = (radius - inner) / (outer - inner)
            edge = _smooth(u / .16) * (1. - _smooth((u - .48) / .52))
            sheen = math.exp(-((u - .23) / .16) ** 2)
            sheen *= .65 + .35 * math.sin(math.pi * (y - top) / (bottom - top))
            phase = (y - top - .25 * (x - CX - inner)) / 7.
            etch = math.exp(-((phase - round(phase)) / .055) ** 2)
            glint = math.exp(-((u - .23) / .05) ** 2)
            alpha = round((120. + 26. * sheen + 12. * etch + 25. * glint) * cap * edge)
            colour = (round(7. + 18. * sheen + 14. * etch + 48. * glint),
                      round(29. + 30. * sheen + 19. * etch + 77. * glint),
                      round(42. + 37. * sheen + 22. * etch + 99. * glint), alpha)
            pixels[xx, yy] = colour
            pixels[round(2 * CX * S) - xx, yy] = colour
    return image



# Sample the authored normal profiles finely enough that the 4x4 texel
# integral is limited by its coverage samples, not by profile quantisation.
_EDGE_PROFILE_DENSITY = 128
_EDGE_SHADOW_REACH = 14.


def _wing_edge_profiles(style):
    radius = style['tail_radius']
    profiles = [bytearray() for _ in range(5)]
    for i in range(math.ceil((radius + _EDGE_SHADOW_REACH) * _EDGE_PROFILE_DENSITY)):
        d = (i + .5) / _EDGE_PROFILE_DENSITY - radius
        def gaussian(centre, sigma):
            return math.exp(-.5 * ((d - centre) / sigma) ** 2)
        values = (
            255 * gaussian(2., 3.4) if d >= 0 else 0,
            52 * gaussian(0., 2.2) if d >= 0 else 0,
            style['reflection_alpha'] * gaussian(0., style['reflection_sigma']) if d >= 0 else 0,
            style['tail_alpha'] * .72 * gaussian(0., style['tail_sigma']) if abs(d) < radius else 0,
            style['edge_glow_alpha'] * gaussian(0., style['edge_glow_sigma']) if d >= 0 else 0,
        )
        for profile, value in zip(profiles, values):
            profile.append(round(value))
    return [Image.frombytes('L', (1, len(profile)), bytes(profile)) for profile in profiles]


def _edge_column(masks, profiles, x, edge_y, slope, direction, radius, fade, shadow):
    # Distances are in artwork pixels along the normal. Project the support
    # onto the vertical scanline, including the half-texel at either end.
    normal = math.hypot(1., slope)
    inner = edge_y - direction * radius * normal
    outer = edge_y + direction * _EDGE_SHADOW_REACH * normal
    first = max(0, math.floor(min(inner, outer) * S - abs(slope) / 2))
    end = min(masks[0].height, math.ceil(max(inner, outer) * S + abs(slope) / 2))
    if end <= first:
        return
    rows = end - first
    # At each of 16 subpixel centres, look up the distance from the local
    # tangent. The box average also integrates the reflection's one-sided cut.
    factor = direction * _EDGE_PROFILE_DENSITY / normal
    origin = radius * _EDGE_PROFILE_DENSITY + factor * ((first + slope / 2) / S - edge_y)
    transform = (0., 0., .5, -slope * factor / (4*S), factor / (4*S), origin)
    for mask, profile, opacity in zip(masks, profiles, (fade*shadow/255, fade, fade, fade, fade)):
        samples = profile.transform((4, rows*4), Image.Transform.AFFINE, transform,
                                    Image.Resampling.NEAREST)
        column = samples.resize((1, rows), Image.Resampling.BOX)
        if opacity != 1.:
            column = Image.frombytes('L', column.size, bytes(round(a*opacity) for a in column.tobytes()))
        mask.paste(column, (x, first))


def wing_edge_effects(padding=0, draw_from=None, draw_to=None, variant=None,
                      context_split=None, top_padding=0):
    """Render the original exterior edge effects through the curved wing tips."""
    from . import layout as geo

    variant = DEFAULT_RACE_EDGE_VARIANT if variant is None else variant
    if variant not in RACE_EDGE_VARIANTS:
        raise ValueError('Unknown race-edge variant ' + str(variant))
    style = RACE_EDGE_VARIANTS[variant]
    size = ((WIDTH + 2 * padding) * S,
            round((HEIGHT + top_padding) * S))
    masks = [Image.new("L", size) for _ in range(5)]
    pixels = [mask.load() for mask in masks]
    texture_end = geo.WING_TEXTURE_END - CX
    start = geo.WING_FACE_START - CX
    draw_from = start if draw_from is None else max(start, draw_from)
    draw_to = geo.WING_TEXTURE_NATIVE_END_DISTANCE if draw_to is None else min(
        texture_end, draw_to
    )
    if draw_to <= draw_from:
        return Image.new("RGBA", size)

    # Candidate B filters reflection alpha with a 3x3 kernel. Each split pass
    # samples the adjacent output texel on the other side, then removes that
    # context column after filtering so the half-open owners never overlap.
    sample_from, sample_to = draw_from, draw_to
    if variant in FILTERED_RACE_EDGE_VARIANTS and context_split is not None:
        if draw_from == context_split:
            sample_from = max(start, draw_from - 1. / S)
        if draw_to == context_split:
            sample_to = min(texture_end, draw_to + 1. / S)

    # Preserve the original edge treatment up to its existing fade point.
    # Then carry its fade and both backing edges continuously beyond the wing.
    fade_start = WING_EFFECT_END - 42.
    extension_start = WING_EFFECT_END - CX
    tip_x = CX + extension_start
    tip_upper, tip_lower = geo.wing_backing_bounds(tip_x)
    tip_centre = (tip_upper + tip_lower) / 2
    tip_half_height = (tip_lower - tip_upper) / 2
    tip_curve_height = math.sqrt(max(1., RADIUS ** 2 - extension_start ** 2))
    extension_span = max(1., texture_end - extension_start)

    def bounds(distance):
        if distance <= extension_start:
            return geo.wing_backing_bounds(CX + distance)
        progress = _smooth((distance - extension_start) / extension_span)
        natural_height = math.sqrt(max(1., RADIUS ** 2 - distance ** 2)) / tip_curve_height
        half_height = tip_half_height * (1. + (natural_height - 1.) * progress)
        centre = tip_centre + geo.top(CX + distance) - geo.top(tip_x)
        return centre - half_height, centre + half_height

    profiles = _wing_edge_profiles(style)
    context_columns = set()
    for side in (-1, 1):
        if side > 0:
            first_x = padding + CX + sample_from
            last_x = padding + CX + sample_to
        else:
            first_x = padding + CX - sample_to
            last_x = padding + CX - sample_from
        first_pixel = max(0, math.ceil(first_x * S - .5))
        last_pixel = min(size[0] - 1, math.ceil(last_x * S - .5) - 1)
        for xx in range(first_pixel, last_pixel + 1):
            art_x = (xx + .5) / S - padding
            distance = side * (art_x - CX)
            if not sample_from <= distance < sample_to:
                continue
            owned_column = draw_from <= distance < draw_to
            if not owned_column:
                context_columns.add(xx)
            right_x = CX + distance
            if right_x <= fade_start:
                fade = _smooth((right_x - WING_FACE_START) / 24.)
            else:
                fade = (
                    _smooth((right_x - WING_FACE_START) / 24.)
                    * _smooth((CX + texture_end - right_x)
                              / (CX + texture_end - fade_start))
                )
            before = bounds(distance - .5 / S)
            after = bounds(distance + .5 / S)
            extension_strength = _smooth((distance - extension_start) / 10.)
            shadows = (36. + 36. * extension_strength, 44. + 40. * extension_strength)
            for y, lo, hi, direction, shadow in zip(bounds(distance), before, after, (-1, 1), shadows):
                slope = side * (hi - lo) * S
                _edge_column(masks, profiles, xx, y + top_padding, slope, direction,
                             style['tail_radius'], fade, shadow)

    if variant in FILTERED_RACE_EDGE_VARIANTS:
        # Filter before trimming so every owned boundary texel sees the same
        # reflection and fine-core samples as a single continuous render.
        masks[2] = _box_filter_alpha_3x3(masks[2])
        pixels[2] = masks[2].load()
        masks[3] = _box_filter_alpha_3x3(masks[3])
        pixels[3] = masks[3].load()

    # Context samples exist only to support the reflection filter. The kernel
    # can also write one pixel beyond its input context, so trim that halo too.
    # A neighbouring column owned by this pass stays intact; the other pass
    # supplies its own continuous-render value there.
    trim_columns = {
        context_x + offset
        for context_x in context_columns
        for offset in (-1, 0, 1)
    }
    for xx in trim_columns:
        if not 0 <= xx < size[0]:
            continue
        art_x = (xx + .5) / S - padding
        if any(draw_from <= side * (art_x - CX) < draw_to
               for side in (-1, 1)):
            continue
        for target in pixels:
            for yy in range(size[1]):
                target[xx, yy] = 0

    edge_glow_layers = style.get('edge_glow_layers', 1)
    if edge_glow_layers > 1:
        masks[4] = _repeat_alpha_layers(masks[4], edge_glow_layers)

    image = Image.new("RGBA", size)
    # Layer pale reflected light over the same cyan underlay as the outer ring.
    # The root and tip fades above control the entire run, including its core.
    ring_core = (150, 210, 238)
    colours = ((3, 12, 22), CYAN, ring_core, ring_core, CYAN)
    for colour, mask in zip(colours, masks):
        layer = Image.new("RGBA", image.size, colour + (0,))
        layer.putalpha(mask)
        image.alpha_composite(layer)
    return image
