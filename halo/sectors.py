"""Aligned sector readouts projected across the left glass wing."""
from dataclasses import dataclass
from functools import lru_cache
from PIL import Image, ImageDraw
import math
from . import layout as geo, material as mat
from .tuning import rgb

PREFIX = 'view_model_data.hud_halo_v2_sector_'
COLOURS = {
    'white': (244, 251, 255, 255),
    'yellow': (255, 224, 90, 255),
    'green': (100, 242, 156, 255),
    'purple': (207, 139, 255, 255),
}
LEFT = 137.
FONT_SIZE = 21.0 * 0.95
ROW_GAP = 27.
PROJECTION_DISTANCE = 480.
CROSS_DEPTH_SLOPE = .45
VERTICAL_SCALE = 1.30
DECIMAL_BASELINE_FRACTION = .40
PREFIX_ADVANCES = (11.3, 10.8, 5.0)
TIME_ADVANCES = (11.7, 11.7, 5.1, 11.7, 11.7, 11.7)
TIME_LEFT = LEFT + sum(PREFIX_ADVANCES) + 10.


@dataclass(frozen=True)
class Glyph:
    name: str
    anchor: geo.Text
    basis: tuple
    colour: tuple
    literal: str = ''
    binding: str = ''



@dataclass(frozen=True)
class TextEffect:
    x: float
    y: float
    colour: tuple
    opacity: float
    scale: float = 1.0
    layer_offset: int = -2


def effects(part, colour):
    glow_scale = geo.STYLE['text_glow']
    opacity = geo.STYLE['text_glow_strength'] / 100.0
    if part == 'prefix':
        # A 0.15-pixel spread and one alpha level give the requested tiny lift.
        size_ratio = FONT_SIZE / geo.UNIT_LABEL_SIZE
        return tuple(TextEffect((radius*size_ratio+.15)*glow_scale*math.cos(index*math.tau/geo.RPM_LABEL_GLOW_SAMPLES),
                                (radius*size_ratio+.15)*glow_scale*math.sin(index*math.tau/geo.RPM_LABEL_GLOW_SAMPLES),
                                mat.UNIT_GLOW, (alpha+1)/255.*opacity)
                     for radius,alpha in geo.RPM_LABEL_GLOW_RINGS
                     for index in range(geo.RPM_LABEL_GLOW_SAMPLES))
    tint = mat.UNIT_GLOW if colour == COLOURS['white'] else colour[:3]
    bloom = tuple(TextEffect(1.35*glow_scale*math.cos(index*math.tau/3-math.pi/2),
                            1.35*glow_scale*math.sin(index*math.tau/3-math.pi/2),tint,15/255.*opacity)
                  for index in range(3))
    return bloom + (TextEffect(0.,.35,(3,12,22),.40*opacity,1.0+(.04*geo.STYLE['text_outline']),-1),)


def surface_basis(x):
    """Project the local axes of the wing's cylindrical surface."""
    depth = geo.RADIUS - math.sqrt(geo.RADIUS ** 2 - (x - geo.CX) ** 2)
    distance = PROJECTION_DISTANCE + depth
    perspective = PROJECTION_DISTANCE / distance
    centre_y = geo.top(x) + geo.WING_CENTER_OFFSET
    tangent_y = math.tan(math.radians(geo.angle(x)))
    return (
        perspective,
        -(x - geo.CX) * CROSS_DEPTH_SLOPE / distance * VERTICAL_SCALE,
        perspective * tangent_y,
        (perspective - (centre_y - geo.CY) * CROSS_DEPTH_SLOPE / distance) * VERTICAL_SCALE,
    )


def decompose(basis):
    """Factor a surface tangent into rotation, scale, then rotation."""
    a, b, c, d = basis
    first, cross, last = a*a+c*c, a*b+c*d, b*b+d*d
    axis = .5 * math.atan2(2*cross, first-last)
    separation = math.hypot(first-last, 2*cross)
    scale_x = math.sqrt((first+last+separation)/2)
    scale_y = math.sqrt((first+last-separation)/2)
    outer = math.atan2(c*math.cos(axis)+d*math.sin(axis),
                       a*math.cos(axis)+b*math.sin(axis))
    return math.degrees(outer), scale_x, scale_y, -math.degrees(axis)


def glyph_basis(basis):
    """Keep glyphs rigid while retaining the surface's local orientation."""
    a, b, c, d = basis
    orientation = math.atan2(c - b, a + d)
    cosine, sine = math.cos(orientation), math.sin(orientation)
    return cosine, -sine, sine, cosine



def row_step():
    """One shared projected depth axis aligns the starts of all rows."""
    basis = surface_basis(geo.wing_content_x(LEFT + PREFIX_ADVANCES[0] / 2))
    length = math.hypot(basis[1], basis[3])
    return ROW_GAP * basis[1] / length, ROW_GAP * basis[3] / length


def anchor(row, part, index, decimal_fraction=None):
    advances = PREFIX_ADVANCES if part == 'prefix' else TIME_ADVANCES
    left = LEFT if part == 'prefix' else TIME_LEFT
    source_x = left + sum(advances[:index]) + advances[index] / 2
    rail_x = geo.wing_content_x(source_x)
    step_x, step_y = row_step()
    x = rail_x + (row - 1) * step_x
    basis = surface_basis(rail_x)
    y = geo.top(rail_x) + geo.WING_CENTER_OFFSET + (row - 1) * step_y
    if part == 'time' and index == 2:
        # Apply the decimal baseline offset in the projected surface direction.
        fraction = DECIMAL_BASELINE_FRACTION if decimal_fraction is None else decimal_fraction
        offset = FONT_SIZE * .672 * fraction
        x += basis[1] * offset
        y += basis[3] * offset
    # Every column shares the same slanted depth rail and row spacing.
    return geo.Text(x, y, FONT_SIZE * geo.STYLE['text_size'] / 100.0), basis


def glyphs():
    for row in range(3):
        sector = f's{row + 1}'
        for index, character in enumerate(sector.upper() + ':'):
            spec, basis = anchor(row, 'prefix', index)
            yield Glyph(f'sector_{sector}_prefix_c{index}', spec, basis,
                        _text_colour(COLOURS['white']), literal=character)
        for colour, tint in COLOURS.items():
            for index in range(len(TIME_ADVANCES)):
                spec, basis = anchor(row, 'time', index)
                name = f'{sector}_{colour}_c{index}'
                yield Glyph('sector_' + name, spec, basis, _text_colour(tint), binding=PREFIX + name)


def _text_colour(colour):
    if geo.STYLE['text_colour'] == '#ffffff':
        return colour
    return rgb(geo.STYLE['text_colour']) + (255,)


def elements():
    for glyph in glyphs():
        spec = glyph.anchor
        element = {
            'kind': 'text', 'id': glyph.name, 'style': 'OSD_24_bold',
            'align': 'centre', 'box': 15 * geo.HUD_SCALE / .30,
            'cap_height': round(spec.size * .672 * geo.HUD_SCALE * geo.STYLE['text_size'] / 100., 6),
            'at': geo.hud_point(spec.x, spec.y), 'rot': spec.rotation, 'layer': 26,
        }
        if glyph.binding:
            element['value'] = {'view_model': glyph.binding}
        else:
            element['literal'] = glyph.literal
        yield element


@lru_cache(maxsize=64)
def character_image(character):
    font = mat.typeface(round(FONT_SIZE * geo.STYLE['text_size'] / 100.0 * mat.S), 650)
    probe = ImageDraw.Draw(Image.new('L', (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), character, font=font)
    image = Image.new('L', (right-left, bottom-top))
    ImageDraw.Draw(image).text((-left, -top), character, font=font, fill=255)
    box = image.getbbox()
    return image.crop(box)


def draw_character(image, character, spec, basis, tint, opacity=1.0):
    mask = character_image(character)
    source = Image.new('RGBA', mask.size, tint)
    source.putalpha(mask.point(lambda value:round(value*opacity)))
    a, b, c, d = basis
    determinant = a*d-b*c
    corners = [(a*x+b*y, c*x+d*y) for x in (-source.width/2, source.width/2)
               for y in (-source.height/2, source.height/2)]
    centre_x, centre_y = spec.x*mat.S, spec.y*mat.S
    left = math.floor(centre_x+min(x for x,y in corners))-2
    top = math.floor(centre_y+min(y for x,y in corners))-2
    right = math.ceil(centre_x+max(x for x,y in corners))+2
    bottom = math.ceil(centre_y+max(y for x,y in corners))+2
    dx, dy = left-centre_x, top-centre_y
    inverse = (d/determinant, -b/determinant,
               (d*dx-b*dy)/determinant+source.width/2,
               -c/determinant, a/determinant,
               (-c*dx+a*dy)/determinant+source.height/2)
    sprite = source.transform((right-left,bottom-top), Image.Transform.AFFINE,
                              inverse, resample=Image.Resampling.BICUBIC)
    image.alpha_composite(sprite, (left,top))


def draw(image, times, colours, lighting=True, decimal_fraction=None):
    for row in range(3):
        for part, text, tint in (
                ('prefix', f'S{row+1}:', COLOURS['white']),
                ('time', times[row], COLOURS[colours[row]])):
            for index, character in enumerate(text):
                if character == ' ':
                    continue
                spec, basis = anchor(row, part, index, decimal_fraction)
                text_basis = glyph_basis(basis)
                if lighting:
                    a,b,c,d = text_basis
                    for effect in effects(part,tint):
                        position = geo.Text(spec.x+a*effect.x+b*effect.y,
                                            spec.y+c*effect.x+d*effect.y,spec.size)
                        scaled = tuple(value*effect.scale for value in text_basis)
                        draw_character(image,character,position,scaled,effect.colour+(255,),effect.opacity)
                draw_character(image, character, spec, text_basis, tint)
