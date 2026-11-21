"""Rounded moving RPM tip with a native position path along the wing arc."""
import math
from PIL import Image, ImageChops
from . import layout as geo

KEY_COUNT = 33
TEXTURE_SIZE = (2048, 512)
MARGIN = 12.
FIRST_X, LAST_X = 780., 1025.
def limits():
    return geo.wing_content_x(FIRST_X), geo.wing_content_x(LAST_X)


def tangent():
    first, last = limits()
    return math.radians(geo.angle((first + last) / 2))

TANGENT = tangent()
COS, SIN = math.cos(TANGENT), math.sin(TANGENT)


def refresh_style():
    global TANGENT, COS, SIN
    TANGENT = tangent()
    COS, SIN = math.cos(TANGENT), math.sin(TANGENT)


def window():
    first, last = limits()
    width=last-first+4*MARGIN
    height=2*(geo.top(last+MARGIN)-geo.top(first-MARGIN)+2*MARGIN)
    return width,height


def tip(fraction):
    first, last = limits()
    x=first-MARGIN+(last-first+2*MARGIN)*max(0.,min(1.,fraction))
    return x,geo.top(x)+geo.RPM_BAR_OFFSET


def path():
    width,_=window()
    return [geo.hud_point(x-width/2+MARGIN,y)
            for x,y in (tip(index/(KEY_COUNT-1)) for index in range(KEY_COUNT))]


def coverage(x,y):
    """A half-plane and a circular cap retain the full stroke behind the tip."""
    projection=x*COS+y*SIN
    plane=max(0.,min(1.,.5-projection/.55))
    distance=math.hypot(x,y)
    radius=geo.RPM_BAR_WIDTH/2
    core=max(0.,min(1.,.5+(radius-distance)/.55))
    halo=.15*math.exp(-max(0.,distance-radius)/2.)
    return max(plane,core,halo)


def texture():
    width,height=TEXTURE_SIZE
    span_x,span_y=window()
    xs=[MARGIN-span_x+(x+.5)*span_x/width for x in range(width)]
    image=Image.new('RGBA',(width,height))
    image.putdata([(255,255,255,round(255*coverage(x,(y+.5)*span_y/height-span_y/2)))
                   for y in range(height) for x in xs])
    return image


def clip(image,fraction,scale):
    """Apply the same tip profile to the cropped offline RPM artwork."""
    if fraction<=0.:
        return Image.new('RGBA',image.size)
    if fraction>=1.:
        return image.copy()
    bounds=image.getbbox()
    part=image.crop(bounds)
    x0,y0=tip(fraction)
    values=[round(255*coverage((x+bounds[0]+.5)/scale-x0,
                                (y+bounds[1]+.5)/scale-y0))
            for y in range(part.height) for x in range(part.width)]
    mask=Image.new('L',part.size);mask.putdata(values)
    part.putalpha(ImageChops.multiply(part.getchannel('A'),mask))
    result=Image.new('RGBA',image.size)
    result.alpha_composite(part,bounds[:2])
    return result
