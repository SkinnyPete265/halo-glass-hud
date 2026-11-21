"""Centre-out DRS highlight study using a soft, trailing native-mask profile."""
from functools import lru_cache
import math
from PIL import Image
from . import artwork as art, layout as geo, material as mat, feature_assets

PERIOD = 1.0
CURVE = 'default_curve_1'
WINDOW_WIDTH = 84.
END_MARGIN = 40.


def rail_limits():
    """Return the current rail endpoints, including live tuning changes."""
    return geo.DRS_RAIL_START, geo.DRS_RAIL_END


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
    inner_x, outer_x = rail_limits()
    start = inner_x-geo.CX-END_MARGIN-WINDOW_WIDTH/2
    end = outer_x-geo.CX+END_MARGIN+WINDOW_WIDTH/2
    return start+(end-start)*max(0.,min(1.,phase))


@lru_cache(maxsize=8)
def _surface_for_geometry(inner_x, outer_x, width, height):
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


def surface():
    return _surface_for_geometry(
        geo.DRS_RAIL_START, geo.DRS_RAIL_END, geo.WIDTH, geo.HEIGHT
    )


@lru_cache(maxsize=16)
def _side_surface_for_geometry(side, inner_x, outer_x, width, height):
    image = surface().copy()
    alpha = image.getchannel('A')
    middle = round(geo.CX * art.S)
    if side == 'left':
        alpha.paste(0, (middle, 0, image.width, image.height))
    else:
        alpha.paste(0, (0, 0, middle, image.height))
    image.putalpha(alpha)
    return image


def side_surface(side):
    return _side_surface_for_geometry(
        side, geo.DRS_RAIL_START, geo.DRS_RAIL_END, geo.WIDTH, geo.HEIGHT
    )


def invalidate():
    """Discard cached DRS textures after a wing geometry change."""
    _surface_for_geometry.cache_clear()
    _side_surface_for_geometry.cache_clear()


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
