"""Wing-mounted ERS panel. All projection and rail construction use artwork pixels."""
import math
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from . import artwork as art, layout as geo
from .sectors import surface_basis

LEFT, RIGHT = 275., 397.
RAIL_DEPTH = 2.
ICE = (125, 225, 249)
GREEN = (145, 235, 194)

# Nominal column, depth, type size and maximum artwork width.
ROWS = {
    'charge': (306., -23., 32., 78.),
    'mode': (368., -32., 12., 60.),
    'flow': (368., -15., 10., 65.),
    'deploy_caption': (305., 20., 10., 65.),
    'harvest_caption': (367., 20., 10., 65.),
    'deploy_kw': (305., 36., 18., 60.),
    'harvest_kw': (367., 36., 18., 60.),
}
CAPTIONS = {'deploy_caption': 'DEPLOY kW', 'harvest_caption': 'HARVEST kW'}


def point(u, v):
    x = geo.wing_content_x(u)
    _, b, _, d = surface_basis(x)
    top, bottom = geo.wing_face_edges(x)
    return x + b*v, (top + bottom)/2 + d*v


def text_anchor(name):
    u, v, size, _ = ROWS[name]
    x, y = point(u, v)
    x0, y0 = point(u-.5, v)
    x1, y1 = point(u+.5, v)
    a, _, c, _ = surface_basis(geo.wing_content_x(u))
    return geo.Text(x, y, size * math.hypot(a, c), math.degrees(math.atan2(y1-y0, x1-x0)))


def capsule(left, right, v, radius):
    # Straight sections in surface space become curves on the dial.
    pts = []
    for i in range(65):
        pts.append((left+radius+(right-left-2*radius)*i/64, v-radius))
    for i in range(17):
        t = -math.pi/2 + math.pi*i/16
        pts.append((right-radius+radius*math.cos(t), v+radius*math.sin(t)))
    for i in range(65):
        pts.append((right-radius-(right-left-2*radius)*i/64, v+radius))
    for i in range(17):
        t = math.pi/2 + math.pi*i/16
        pts.append((left+radius+radius*math.cos(t), v+radius*math.sin(t)))
    return [point(x, y) for x, y in pts]


def cavity():
    return capsule(LEFT+1.3, RIGHT-1.3, RAIL_DEPTH, 4.2)


def rail_limits():
    xs = [x for x, _ in cavity()]
    # Pixel-aligned support of the filled polygon, independent of sprite padding.
    return math.floor(min(xs)*art.S)/art.S, (math.floor(max(xs)*art.S)+1)/art.S


def pixels(points):
    return [(x*art.S, y*art.S) for x, y in points]


def fill():
    image = art.canvas()
    draw = ImageDraw.Draw(image)
    draw.polygon(pixels(cavity()), fill=(41, 195, 229, 255))
    draw.polygon(pixels(capsule(LEFT+2, RIGHT-2, RAIL_DEPTH-1, 2.2)), fill=(101, 230, 251, 255))
    return image


def track():
    layer = art.canvas()
    draw = ImageDraw.Draw(layer)
    def rim(points, colour, ink):
        path = pixels(points)
        draw.polygon(path, fill=ink)
        draw.line([*path,path[0]], fill=colour, width=2, joint='curve')
    rim(capsule(LEFT, RIGHT, RAIL_DEPTH, 5.5), (115,194,212,195), (5,24,35,180))
    for i in range(1, 10):
        u = LEFT+(RIGHT-LEFT)*i/10
        draw.line(pixels([point(u,RAIL_DEPTH-2.6), point(u,RAIL_DEPTH+2.6)]),
                  fill=(135,198,215,142),width=2)
    rim(capsule(340.,396.,-32.,8.), (89,186,218,215), (10,42,57,178))
    return layer


def rail_glow():
    # A separate moving gauge clips the diffuse light at the same charge front.
    alpha = fill().getchannel('A').filter(ImageFilter.GaussianBlur(2*art.S))
    left, right = rail_limits()
    ramp = Image.new('L',(alpha.width,1))
    ramp.putdata([round(255*max(0.,min(1.,((i+.5)/art.S-left)/2,
                                           (right-(i+.5)/art.S)/2))) for i in range(alpha.width)])
    alpha = ImageChops.multiply(alpha,ramp.resize(alpha.size,Image.Resampling.NEAREST))
    result = Image.new('RGBA', alpha.size, ICE)
    result.putalpha(alpha.point(lambda a: round(a*.48)))
    return result


def front_mask(width):
    # Feather only the last 1.5 artwork pixels on the filled side.
    row = Image.new('RGBA', (1024,1))
    row.putdata([(255,255,255,round(255*min(1., (1-(x+.5)/1024)*width/1.5)))
                 for x in range(1024)])
    return row.resize((1024,8),Image.Resampling.NEAREST)


def text_record(name, spec, box, *, literal=None, leaf=None, prefix=''):
    record = {'kind':'text', 'id':name, 'style':'OSD_24_bold', 'align':'centre',
              'cap_height':round(spec.size*.672*geo.HUD_SCALE*geo.STYLE['text_size']/100,6),
              'box':box*geo.HUD_SCALE, 'at':geo.hud_point(spec.x,spec.y),
              'rot':spec.rotation, 'layer':29}
    if literal is None:
        record['value'] = {'view_model':prefix+leaf}
    else:
        record['literal'] = literal
    return record
