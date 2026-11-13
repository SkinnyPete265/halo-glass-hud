"""Centre-out DRS highlight study using a soft, trailing native-mask profile."""
from functools import lru_cache
import math
from PIL import Image, ImageChops
from . import artwork as art, layout as geo, material as mat, feature_assets

PERIOD = 1.0
CURVE = 'default_curve_1'
INNER_X, OUTER_X = geo.DRS_RAIL_START, geo.DRS_RAIL_END
WINDOW_WIDTH = 84.
END_MARGIN = 40.


def mask_weight(u):
    if not 0. < u < 1.:
        return 0.
    if u <= .72:
        light = math.exp((u-.72)/.28)
    else:
        light = math.exp(-((u-.72)/.15)**2)
    edge = min(1.,u/.06,(1.-u)/.06)
    return light*edge*edge*(3.-2.*edge)


def window_centre(phase):
    start = INNER_X-geo.CX-END_MARGIN-WINDOW_WIDTH/2
    end = OUTER_X-geo.CX+END_MARGIN+WINDOW_WIDTH/2
    return start+(end-start)*max(0.,min(1.,phase))


@lru_cache(maxsize=1)
def surface():
    image = art.canvas()
    for edge in geo.DRS_RAIL_EDGES:
        for side in (-1,1):
            points=geo.drs_rail_points(edge)
            if side < 0:
                points = [(2*geo.CX-x,y) for x,y in points]
            image = mat.rounded_stroke(image,points,(40,245,139,225),9.0,10.0)
            image = mat.rounded_stroke(image,points,(118,255,185,245),6.0,3.0)
            image = mat.rounded_stroke(image,points,(230,255,242,255),2.2)
    return feature_assets.clip_drs(image)


@lru_cache(maxsize=2)
def side_surface(side):
    image = surface().copy()
    alpha = image.getchannel('A')
    middle = round(geo.CX * art.S)
    if side == 'left':
        alpha.paste(0, (middle, 0, image.width, image.height))
    else:
        alpha.paste(0, (0, 0, middle, image.height))
    image.putalpha(alpha)
    return image


def mask_texture(side, width=256, height=8):
    """A reusable 2D mask for the game's eMaskTexture window."""
    image = Image.new('RGBA',(width,height))
    values=[]
    for x in range(width):
        u=x/(width-1)
        if side=='left':
            u=1.-u
        alpha=round(255*mask_weight(u))
        values.append((255,255,255,alpha))
    image.putdata(values*height)
    return image


def draw(image,phase,opacity=1.0,reveal=1.0):
    highlight=surface().copy()
    centre=window_centre(phase)
    values=[]
    limit=INNER_X-geo.CX+(OUTER_X-INNER_X)*reveal
    for x in range(highlight.width):
        radius=abs(x/art.S-geo.CX)
        u=.5+(radius-centre)/WINDOW_WIDTH
        fade=max(0.,min(1.,(limit+3.-radius)/6.)) if reveal<1. else 1.
        values.append(round(255*mask_weight(u)*fade*opacity*reveal))
    mask=Image.new('L',(highlight.width,1))
    mask.putdata(values)
    mask=mask.resize(highlight.size,Image.Resampling.NEAREST)
    highlight.putalpha(ImageChops.multiply(highlight.getchannel('A'),mask))
    image.alpha_composite(highlight)
