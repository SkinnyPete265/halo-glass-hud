"""Approved glass material functions, ported into the shared v2 layout."""
import math
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from .layout import (
    WIDTH, HEIGHT, CX, CY, RADIUS, top, angle, arc_length, slat_points, point,
    WING_HEIGHT, WING_FACE_TOP, WING_FACE_BOTTOM, PEDAL_INNER_RADIUS, PEDAL_OUTER_RADIUS,
    WING_FACE_START, WING_FACE_END, WING_CORNER_RADIUS,
)

S = 3
FONT = str(Path(__file__).resolve().parents[1] / "assets/fonts/Saira/Saira.ttf")
CYAN = (76, 159, 203)
WHITE = (236, 248, 253)
ICE_CORE = (179, 216, 244)
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


def circle_stroke(image, centre, radius, color, width, glow):
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
    layer = Image.new('RGBA', mask.size, color[:3] + (0,))
    layer.putalpha(mask)
    result = image.copy()
    if glow:
        result.alpha_composite(layer.filter(ImageFilter.GaussianBlur(glow * S)), (left, top))
    result.alpha_composite(layer, (left, top))
    return result


def text(image,x,y,value,size,color=WHITE+(255,),rotation=0.,width_scale=1.,
         glow=False,weight=600,outline=0.,glow_color=ICE_GLOW,
         outline_color=(4,17,27,210)):
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
            halo.putalpha(alpha.filter(ImageFilter.GaussianBlur(radius*S)).point(lambda a:round(a*opacity)))
            image.alpha_composite(halo,(round(x*S-sprite.width/2),round(y*S-sprite.height/2)))
    image.alpha_composite(sprite,(round(x*S-sprite.width/2),round(y*S-sprite.height/2)))

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


def glass_wings():
    image=Image.new('RGBA',(WIDTH*S,HEIGHT*S));pixels=image.load()
    # A tinted instrument face isolates the lettering from bright scenery.
    # The surrounding glass and outer ends retain their soft transparency.
    for xx in range(75*S,1090*S):
        x=xx/S;y0=top(x);fade=min(1.,max(0.,min(x-75,1089-x)/48.))
        for yy in range(round(y0*S),min(image.height,round((y0+WING_HEIGHT)*S))):
            t=(yy/S-y0)/WING_HEIGHT
            highlight=math.exp(-((t-.07)/.075)**2)
            reflection=math.exp(-((t-.33)/.12)**2)
            lower=math.exp(-((t-.90)/.12)**2)
            alpha=round((WING_SMOKE_ALPHA+17*highlight+5*reflection+6*lower)*fade)
            pixels[xx,yy]=(round(28+45*highlight),round(49+64*highlight),round(59+67*highlight),alpha)
    # Separate thin glass facets; matching mirrored base geometry.
    facet=Image.new('RGBA',image.size);facet_pixels=facet.load()
    for side in (-1,1):
        for xx in range(round(WING_FACE_START*S),round(WING_FACE_END*S)+1):
            x=xx/S;y0=top(x)+WING_FACE_TOP;y1=top(x)+WING_FACE_BOTTOM
            fade=_smooth((WING_FACE_END-x)/WING_TIP_FADE_WIDTH)
            along=(arc_length(x)-arc_length(745.))/(arc_length(1089.)-arc_length(745.))
            root=max(0.,1.-along/ROOT_SHADE_FRACTION)
            root=root*root*(3.-2.*root)
            for yy in range(round(y0*S),round(y1*S)+1):
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
        path=[point(x,face_top) for x in range(round(end),round(inner+r)-1,-2)]
        path += [point(inner+r+r*math.cos(a),face_top+r+r*math.sin(a)) for a in (-math.pi/2-math.pi*i/32 for i in range(17))]
        path += [point(inner,face_bottom-r)]
        path += [point(inner+r+r*math.cos(a),face_bottom-r+r*math.sin(a)) for a in (math.pi-math.pi*i/32 for i in range(17))]
        path += [point(x,face_bottom) for x in range(round(inner+r),round(end)+1,2)]
        if side<0:path=[(2*CX-x,y) for x,y in path]
        image=stroke(image,path,CYAN+(168,),.8,2.0)
    return Image.alpha_composite(wing_edge_effects(), image)


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



def wing_edge_effects():
    """Soft exterior blue bloom and a downward-weighted glass-edge shadow."""
    masks = [Image.new("L", (WIDTH * S, HEIGHT * S)) for _ in range(3)]
    pixels = [mask.load() for mask in masks]
    for xx in range(745 * S, 1089 * S + 1):
        x = xx / S
        fade = _smooth((x - 745.) / 24.) * _smooth((1089. - x) / 42.)
        normal_scale = 1. / math.cos(math.radians(angle(x)))
        for edge_offset, direction in ((0., -1), (WING_HEIGHT, 1)):
            edge_y = round((top(x) + edge_offset) * S)
            for step in range(1, math.ceil(14. * normal_scale * S) + 1):
                yy = edge_y + direction * step
                if not 0 <= yy < HEIGHT * S:
                    continue
                distance = step / (S * normal_scale)
                shadow = (36. if direction < 0 else 44.) * math.exp(
                    -.5 * ((distance - 2.) / 3.4) ** 2)
                bloom = 52. * math.exp(-.5 * (distance / 2.2) ** 2)
                reflection = 35. * math.exp(-.5 * (distance / .55) ** 2)
                for target, value in zip(pixels, (shadow, bloom, reflection)):
                    alpha = round(value * fade)
                    target[xx, yy] = alpha
                    target[round(2 * CX * S) - xx, yy] = alpha
    image = Image.new("RGBA", (WIDTH * S, HEIGHT * S))
    for colour, mask in zip(((3, 12, 22), ICE_GLOW, (111, 178, 215)), masks):
        layer = Image.new("RGBA", image.size, colour + (0,))
        layer.putalpha(mask)
        image = Image.alpha_composite(image, layer)
    return image
