"""Layered native sprites for charge colour animation and DRS effects."""
from functools import lru_cache
import math
from PIL import Image, ImageDraw, ImageChops, ImageFilter
from . import artwork as art, layout as geo, material as mat

S = art.S

@lru_cache(maxsize=1)
def battery_layers():
    images = {name:art.canvas() for name in ("housing","frame","fill","bolt")}
    cx,cy = geo.BATTERY_CENTRE
    left,right = cx-geo.BATTERY_WIDTH/2,cx+geo.BATTERY_WIDTH/2
    top,bottom = cy-geo.BATTERY_HEIGHT/2,cy+geo.BATTERY_HEIGHT/2
    box = (round(left*S),round(top*S),round(right*S),round(bottom*S))
    ImageDraw.Draw(images["housing"]).rounded_rectangle(
        box,radius=geo.BATTERY_CORNER_RADIUS*S,fill=(36,55,70,245))
    # Filter the frame and terminal independently so their narrow separator
    # remains visible after the existing 3x-to-sprite composition.
    frame_source = Image.new('L', images["frame"].size)
    ImageDraw.Draw(frame_source).rounded_rectangle(
        box, radius=geo.BATTERY_CORNER_RADIUS*S, outline=255, width=2*S
    )
    frame_mask = mat._box_filter_alpha_3x3(frame_source)
    # Keep the crisp core above the charge artwork. A soft skirt lifts the
    # outer silhouette off the dial without opening a gap around the fill.
    bloom = frame_source.filter(ImageFilter.GaussianBlur(1.6*S)).point(lambda a: round(.7*a))
    frame_mask = ImageChops.lighter(frame_mask,bloom)
    terminal_source = Image.new('L', images["frame"].size)
    ImageDraw.Draw(terminal_source).rounded_rectangle(
        (box[2]+S,(cy-3)*S,(right+4)*S,(cy+3)*S),
        radius=2*S,fill=180,
    )
    terminal_mask = mat._box_filter_alpha_3x3(terminal_source)
    # Keep the two original transparent texels between the frame and
    # terminal. The normalized filter otherwise blends both strokes across
    # this deliberately open separator.
    centre_y = round(cy*S)
    frame_x = [x for x in range(round(right*S)-S*2, round(right*S)+S*2+1)
               if frame_source.getpixel((x, centre_y))]
    terminal_x = [x for x in range(round(right*S)-S*2, round((right+4)*S)+1)
                  if terminal_source.getpixel((x, centre_y))]
    if frame_x and terminal_x:
        gap_start, gap_end = max(frame_x)+1, min(terminal_x)
        if gap_end-gap_start == 2:
            terminal_bounds = terminal_source.getbbox()
            for y in range(terminal_bounds[1], terminal_bounds[3]):
                for x in range(gap_start, gap_end):
                    frame_mask.putpixel((x, y), 0)
                    terminal_mask.putpixel((x, y), 0)
    for mask in (frame_mask, terminal_mask):
        layer = Image.new('RGBA', mask.size, (255,255,255,0))
        layer.putalpha(mask)
        images["frame"].alpha_composite(layer)
    fill_left, fill_top, fill_right, fill_bottom = geo.battery_fill_bounds()
    ImageDraw.Draw(images["fill"]).rounded_rectangle(
        (round(fill_left*S),round(fill_top*S),round(fill_right*S)-1,round(fill_bottom*S)-1),
        radius=(geo.BATTERY_CORNER_RADIUS-geo.BATTERY_FILL_INSET)*S,fill=(255,255,255,230))
    bolt = [(round(x*S),round(y*S)) for x,y in geo.battery_bolt_points()]
    draw = ImageDraw.Draw(images['bolt'])
    draw.line(bolt+[bolt[0]],fill=(3,16,24,205),width=max(1,round(.6*S)),joint='curve')
    draw.polygon(bolt,fill=(6,207,220,255))
    return images

def fill_edge_mask(window_width, feather, width=512, height=8):
    image = Image.new('RGBA', (width, height))
    row = []
    for x in range(width):
        distance = (1. - x / (width - 1)) * window_width
        coverage = max(0., min(1., distance / feather))
        coverage = coverage * coverage * (3. - 2. * coverage)
        row.append((255, 255, 255, round(255 * coverage)))
    image.putdata(row * height)
    return image


@lru_cache(maxsize=1)
def drs_clip_mask():
    """Fade the rail core and halo together at the outer wing-face tips."""
    mask = Image.new('L',(geo.WIDTH*S,geo.HEIGHT*S))
    draw = ImageDraw.Draw(mask)
    ends = geo.wing_edge_ends()
    for xx in range(mask.width):
        x = (xx+.5)/S
        side = -1 if x < geo.CX else 1
        run = abs(x-geo.CX)
        root = mat._smooth((run-(geo.DRS_RAIL_START-geo.CX))/1.25)
        middle = round((geo.top(x)+geo.WING_CENTER_OFFSET)*S)
        for k,(first,last) in enumerate(((0,middle-1),(middle,mask.height-1))):
            fade = root*mat._smooth((ends[side,k]-run)/32.)
            if fade:
                draw.line((xx,first,xx,last), fill=round(255*fade))
    return mask

def clip_drs(image):
    image.putalpha(ImageChops.multiply(image.getchannel('A'),drs_clip_mask()))
    return image


@lru_cache(maxsize=1)
def drs_rails():
    image=art.canvas()
    for edge in geo.DRS_RAIL_EDGES:
        for side in (-1,1):
            points=geo.drs_rail_points(edge,side)
            image=mat.rounded_stroke(image,points,(48,211,132,145),4.2,7.0)
            image=mat.rounded_stroke(image,points,(67,249,160,220),4.2,2.1)
            image=mat.rounded_stroke(image,points,(144,255,199,235),1.1)
    return clip_drs(image)


def drs_side(side):
    image=drs_rails().copy()
    centre=round(geo.CX*S)
    if side=="left":
        image.paste((0,0,0,0),(centre,0,image.width,image.height))
    else:
        image.paste((0,0,0,0),(0,0,centre,image.height))
    return image

def drs_text(image, centre, value, colour=None, outline=False):
    """Preview the native crisp text core and its low-opacity offset effects."""
    colour = geo.DRS_PROMPT_COLOUR if colour is None else colour
    rings = [(geo.DRS_PROMPT_OUTLINE_RADIUS,geo.DRS_PROMPT_OUTLINE_ALPHA,(0,0,0))]
    if outline:
        rings = [(geo.DRS_LABEL_GLOW_RADIUS,geo.DRS_LABEL_GLOW_ALPHA,colour[:3])]
        rings.insert(0,(.28,30,(0,0,0)))
    for radius,alpha,tint in rings:
        for index in range(4):
            angle=index*math.tau/4
            art.label(image,geo.Text(centre[0]+radius*math.cos(angle),
                      centre[1]+radius*math.sin(angle),geo.DRS_STATUS_TEXT_SIZE),
                      value,color=tint+(alpha,),weight=700)
    art.label(image,geo.Text(*centre,geo.DRS_STATUS_TEXT_SIZE),value,color=colour,weight=700)


@lru_cache(maxsize=1)
def drs_label():
    image=art.canvas()
    drs_text(image,geo.DRS_CENTRE,"DRS OPEN",geo.DRS_TEXT_COLOUR,outline=True)
    return image


def pedal_mask(side, size=512):
    """Full native mask UV frame generated from the same slats as the base."""
    if geo.PEDAL_OUTER_RADIUS >= geo.PEDAL_MASK_SPAN / 2:
        raise ValueError("Pedal geometry exceeds its native mask frame")
    sample_size = size * 2
    image = Image.new("RGBA", (sample_size, sample_size))
    draw = ImageDraw.Draw(image)
    for index in range(10):
        points = [
            (round((.5 + (x - geo.CX) / geo.PEDAL_MASK_SPAN) * sample_size - .5),
             round((.5 + (y - geo.CY) / geo.PEDAL_MASK_SPAN) * sample_size - .5))
            for x, y in geo.slat_points(side, index)
        ]
        draw.polygon(points, fill=(255, 255, 255, 255))
    # The idle base uses a one-art-pixel box on 3x coverage. On this 2x
    # supersample a 512 px mask that footprint is about 3.29 sample texels.
    # Filter alpha before Lanczos reduction so the downsampler is included in
    # the final edge profile instead of stacking a second blur on top of it.
    footprint = max(1.0, sample_size / geo.PEDAL_MASK_SPAN)

    def box_weights(width, radius):
        half_width = width / 2.
        return tuple(max(0., min(half_width, index + .5) -
                         max(-half_width, index - .5)) / width
                     for index in range(-radius, radius + 1))

    if footprint > 5.0:
        alpha = image.getchannel('A').filter(
            ImageFilter.BoxBlur((footprint - 1.) / 2.)
        )
    elif footprint <= 3.0:
        radius = 1
        weights = box_weights(footprint, radius)
        kernel_size = 3
        kernel = tuple(a * b for a in weights for b in weights)
        alpha = image.getchannel('A').filter(ImageFilter.Kernel(
            (kernel_size, kernel_size), kernel, scale=1.0
        ))
    else:
        radius = 2
        weights = box_weights(footprint, radius)
        kernel_size = 5
        kernel = tuple(a * b for a in weights for b in weights)
        alpha = image.getchannel('A').filter(ImageFilter.Kernel(
            (kernel_size, kernel_size), kernel, scale=1.0
        ))
    alpha = alpha.resize((size, size), Image.Resampling.LANCZOS)
    result = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    result.putalpha(alpha)
    return result


def pedal_slat(side, index):
    """One complete lit slat using the idle geometry and active artwork filter."""
    points = geo.slat_points(side,index)
    left = math.floor(min(x for x,y in points))-2
    top = math.floor(min(y for x,y in points))-2
    right = math.ceil(max(x for x,y in points))+2
    bottom = math.ceil(max(y for x,y in points))+2
    size = ((right-left)*S,(bottom-top)*S)
    mask = Image.new('L',size)
    ImageDraw.Draw(mask).polygon([(round((x-left)*S),round((y-top)*S)) for x,y in points],fill=255)
    layer = Image.new('RGBA',size,(249,72,70) if side<0 else (83,234,151))
    layer.putalpha(mask.filter(ImageFilter.GaussianBlur(.34*S)))
    result = art.canvas()
    result.alpha_composite(layer,(left*S,top*S))
    return result


def status_band(row, state):
    """Traced proportions of the 2026 reference's segmented Boost and solid Overtake bands."""
    image = art.canvas()
    draw = ImageDraw.Draw(image)
    colour = {'dim': (75, 85, 100, 210), 'ready': (97, 125, 143, 230),
              'active': (35, 144, 79, 245)}[state]
    y = (geo.BOOST_STATUS if row == 'boost' else geo.OVERTAKE_STATUS).y
    def panel(left, right):
        points = [(left-1,-7), (right+1,-7), (right,7), (left,7)]
        draw.polygon([((geo.CX+x)*S,(y+dy)*S) for x,dy in points],
                     fill=colour, outline=tuple(min(255,c+34) for c in colour[:3])+(230,), width=S)
    if row == 'boost':
        panel(-33,33)
        for side in (-1,1):
            for x in (36,44,52):
                panel(*sorted((side*x,side*(x+4))))
    else:
        panel(-59,59)
    return image
