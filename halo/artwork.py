"""Data-free sprites. Shared geometry supplies every instrument anchor."""
import math
from functools import lru_cache
from .tuning import rgb
from PIL import Image, ImageDraw, ImageChops
from . import layout as geo, material as mat

S = mat.S
RPM_WARNING_START = 0.83
RPM_WARNING_COLOUR = (255, 36, 52)

def rpm_warning_weight(fraction):
    weight = max(0.0, min(1.0, (fraction - RPM_WARNING_START) /
                           (1.0 - RPM_WARNING_START)))
    return weight * weight * (3.0 - 2.0 * weight)


def canvas(top_padding=0):
    return Image.new("RGBA", (geo.WIDTH * S,
                               round((geo.HEIGHT + top_padding) * S)))

def shoulder_glass():
    """Soft frost concentrated behind the inner wing instruments."""
    reach = 430
    top = geo.WHITE_ARC_TOP
    image = Image.new('RGBA',(geo.WIDTH*S,math.ceil((geo.wing_backing_bounds(geo.CX+reach)[1]+2-top)*S)))
    pixels = image.load()
    for xx in range(round((geo.CX-reach)*S),round((geo.CX+reach)*S)):
        dx = abs((xx+.5)/S-geo.CX)
        curve = math.hypot(dx,95.)-95.
        # Blend the dial surround into the actual wing backing at each root.
        wing = mat._smooth((dx-65.)/110.)
        wing_top, wing_bottom = geo.wing_backing_bounds(geo.CX+dx)
        upper = (1.-wing)*(-30. + .62*curve) + wing*wing_top
        lower = (1.-wing)*(202. + .18*curve) + wing*wing_bottom
        end = 1.-mat._smooth((dx-220.)/(reach-220.))
        # Keep the soft surround near the dial, then let cockpit detail show
        # through where the separate instrument face overlaps this artwork.
        face = mat._smooth((dx-95.)/95.)
        density = (.48+.52*wing)*(1.-.82*face)*end
        for yy in range(math.floor((upper-top)*S),math.ceil((lower-top)*S)):
            y = top+(yy+.5)/S
            rim = mat._smooth((math.hypot(dx,y-geo.CY)-89.)/6.)
            edge = mat._smooth((y-upper)/33.)*mat._smooth((lower-y)/31.)
            # A pale reflected strip blends into a denser blue-grey body.
            reflection = math.exp(-((y-upper-24.)/20.)**2)
            lower_light = math.exp(-((lower-y-27.)/22.)**2)
            light = reflection + .38*lower_light
            alpha = round(192*edge*density*rim)
            pixels[xx,yy] = (round(42+95*light),round(55+94*light),
                             round(82+83*light),alpha)
    return image


def white_arc():
    """Neutral shoulder line, sampled by perpendicular distance at 3x resolution."""
    half_span = 440
    rise = .69
    bend = 110.
    height = math.ceil(rise*(math.hypot(half_span,bend)-bend)) + 12
    alpha = Image.new('L',(geo.WIDTH*S,height*S))
    pixels = alpha.load()
    for xx in range(round((geo.CX-half_span)*S),round((geo.CX+half_span)*S)):
        dx = (xx+.5)/S - geo.CX
        radius = math.hypot(dx,bend)
        y = (geo.WHITE_ARC_CROWN-geo.WHITE_ARC_TOP + rise*(radius-bend))*S
        normal = math.hypot(1.,rise*dx/radius)
        fade = max(0.,(abs(dx)-55)/(half_span-55))
        opacity = 205*(1-fade*fade*(3-2*fade))**2
        for yy in range(math.floor(y)-3,math.ceil(y)+3):
            coverage = max(0.,min(1., .5+.46*S-abs(yy+.5-y)/normal))
            pixels[xx,yy] = round(opacity*coverage)
    alpha = mat._box_filter_alpha_3x3(alpha)
    # Transparent black lets BC7 encode empty blocks with exactly zero alpha.
    neutral = alpha.point(lambda a: 248 if a else 0)
    result = Image.merge('RGBA',(neutral,neutral,neutral,alpha))
    return result


def label(image, spec, value, y_offset=0.0, **options):
    if value != 'GEARS' and geo.STYLE['text_colour'] != '#ffffff':
        options['color'] = rgb(geo.STYLE['text_colour']) + (255,)
    mat.text(image, spec.x, spec.y + y_offset, value, spec.size,
             rotation=spec.rotation, **options)

def draw_base_static(rpm_width, race_variant=None):
    race_variant = (mat.DEFAULT_RACE_EDGE_VARIANT if race_variant is None
                    else race_variant)
    if race_variant not in mat.RACE_EDGE_VARIANTS:
        raise ValueError("Unknown race-edge variant " + str(race_variant))
    style = mat.RACE_EDGE_VARIANTS[race_variant]
    image = mat.glass_wings(race_variant)
    image.alpha_composite(mat.pedal_backing())
    image.alpha_composite(mat.pedal_accents())
    top_padding = geo.ARTWORK_TOP_PADDING
    expanded = canvas(top_padding)
    expanded.alpha_composite(image, (0, round(top_padding * S)))
    image = expanded
    disc = canvas(top_padding)
    pixels = disc.load()
    radius = 89.0
    for yy in range(round((geo.CY + top_padding - radius) * S),
                     round((geo.CY + top_padding + radius) * S) + 1):
        for xx in range(round((geo.CX - radius) * S), round((geo.CX + radius) * S) + 1):
            dx = ((xx + .5) / S - geo.CX) / radius
            dy = ((yy + .5) / S - top_padding - geo.CY) / radius
            distance = math.hypot(dx, dy)
            coverage = max(0., min(1., .5 + (1. - distance) * radius * S))
            if coverage == 0:
                continue
            highlight = math.exp(-((dy + .6) / .3) ** 2) * max(0, 1 - distance ** 2)
            pixels[xx, yy] = (round(7 + 18 * highlight),
                              round(29 + 30 * highlight),
                              round(40 + 37 * highlight), round((195 + 24 * min(distance, 1.)) * coverage))
    image.alpha_composite(disc)
    if style['circle_glow_alpha']:
        image = mat.circle_glow(
            image, (geo.CX, geo.CY + top_padding), radius,
            mat.CYAN + (style['circle_glow_alpha'],), 3.0,
            style['circle_glow_sigma'],
            layers=style.get('circle_glow_layers', 1),
        )
    image = mat.circle_stroke(
        image, (geo.CX, geo.CY + top_padding), radius,
        mat.CYAN + (125,), 3.0, 4.5)
    image = mat.circle_stroke(
        image, (geo.CX, geo.CY + top_padding), radius,
        (150, 210, 238, 170), .8, 1.0,
        prefilter_core=True,
    )
    # The reference face uses short peripheral graduations around the speed stack.
    ticks = canvas(top_padding)
    draw = ImageDraw.Draw(ticks)
    for r in (61.,65.,82.):
        box = ((geo.CX-r)*S,(geo.CY+top_padding-r)*S,
               (geo.CX+r)*S,(geo.CY+top_padding+r)*S)
        draw.arc(box, -71, 71, fill=(151,180,197,60), width=S)
        draw.arc(box, 109, 251, fill=(151,180,197,60), width=S)
    for degree in range(-145, 146, 4):
        angle = math.radians(degree)
        if abs(degree) < 18:
            continue
        points = [((geo.CX+r*math.sin(angle))*S,
                   (geo.CY+top_padding-r*math.cos(angle))*S) for r in (72.,80.)]
        draw.line(points, fill=(151,180,197,83), width=2*S)
    image.alpha_composite(ticks)
    image.alpha_composite(_idle_slats_layer(), (0, round(top_padding * S)))
    rpm_points = [(x, y + top_padding) for x, y in geo.rpm_points()]
    return mat.rounded_stroke(image, rpm_points, mat.WHITE + (30,), rpm_width)


def _idle_slats_layer():
    """Rasterize both ten-slat banks into one filtered 3x alpha mask."""
    mask = Image.new('L', (geo.WIDTH * S, geo.HEIGHT * S))
    draw = ImageDraw.Draw(mask)
    for side in (-1, 1):
        for index in range(10):
            draw.polygon([(round(x * S), round(y * S))
                          for x, y in geo.slat_points(side, index)], fill=255)
    mask = mat._box_filter_alpha_3x3(mask)
    alpha = mask.point(lambda value: round(value * 55 / 255.))
    layer = Image.new('RGBA', mask.size, (126, 176, 187, 0))
    layer.putalpha(alpha)
    return layer


@lru_cache(maxsize=8)
def base_static(rpm_width, wing_extension=None, wing_content_follow=None,
                render_scale=None, race_variant=None):
    from pathlib import Path
    from .asset_cache import cached_layer
    from tools.build_inputs import artwork_source_fingerprint
    if wing_extension is None:
        wing_extension=geo.STYLE['wing_extension']
    if wing_content_follow is None:
        wing_content_follow=geo.STYLE['wing_content_follow']
    if render_scale is None:
        render_scale=S
    if race_variant is None:
        race_variant=mat.DEFAULT_RACE_EDGE_VARIANT
    root=Path(__file__).resolve().parents[1]
    return cached_layer(root,'base-backing',
        {'source':artwork_source_fingerprint(),'rpm_width':rpm_width,
         'wing_extension':wing_extension,
         'wing_content_follow':wing_content_follow,
         'render_scale':render_scale,'race_edge_variant':race_variant},
        lambda:draw_base_static(rpm_width,race_variant))


def base(race_variant=None):
    image=base_static(geo.RPM_BAR_WIDTH,geo.STYLE['wing_extension'],
                      geo.STYLE['wing_content_follow'],S,race_variant).copy()
    label(image,geo.gears_caption(),'GEARS',weight=geo.GEARS_FONT_WEIGHT,glow=True,
          y_offset=geo.ARTWORK_TOP_PADDING,
          color=rgb(geo.STYLE['gears_colour'])+(255,),
          glow_color=(221,242,253),outline=.45)
    return image


def texture_base(race_variant=None):
    """Include the full outside-edge tails in the texture used by the game."""
    return mat.wing_texture_frame(base(race_variant), geo.WING_TEXTURE_PADDING)


def rpm_fill():
    points = geo.rpm_points()
    image = mat.rounded_stroke(canvas(), points, (221, 242, 253, 242), geo.RPM_BAR_WIDTH, 2.5)
    first, last = points[0][0], points[-1][0]
    gradient = Image.new("L", (image.width, 1))
    gradient.putdata([
        round(255 * rpm_warning_weight((x / S - first) / (last - first)))
        for x in range(image.width)
    ])
    gradient = gradient.resize(image.size, Image.Resampling.NEAREST)
    warning = Image.new("RGBA", image.size, RPM_WARNING_COLOUR + (0,))
    warning.putalpha(ImageChops.multiply(image.getchannel("A"), gradient))
    image.alpha_composite(warning)
    return image

def finish(image, resolution=1, resample=Image.Resampling.LANCZOS):
    return image.resize((round(image.width * resolution / S),
                         round(image.height * resolution / S)), resample)
