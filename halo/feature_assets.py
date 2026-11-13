"""Layered native sprites for charge colour animation and DRS effects."""
from functools import lru_cache
import math
from PIL import Image, ImageDraw, ImageChops
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
        box,radius=geo.BATTERY_CORNER_RADIUS*S,fill=(5,27,39,195))
    draw = ImageDraw.Draw(images["frame"])
    draw.rounded_rectangle(box,radius=geo.BATTERY_CORNER_RADIUS*S,outline=(255,255,255,225),width=S)
    draw.rounded_rectangle(((right+1)*S,(cy-3)*S,(right+4)*S,(cy+3)*S),
                           radius=2*S,fill=(255,255,255,180))
    fill_left, fill_top, fill_right, fill_bottom = geo.battery_fill_bounds()
    ImageDraw.Draw(images["fill"]).rounded_rectangle(
        (round(fill_left*S),round(fill_top*S),round(fill_right*S)-1,round(fill_bottom*S)-1),
        radius=(geo.BATTERY_CORNER_RADIUS-geo.BATTERY_FILL_INSET)*S,fill=(255,255,255,230))
    bolt = [(round(x*S),round(y*S)) for x,y in geo.battery_bolt_points()]
    draw = ImageDraw.Draw(images['bolt'])
    draw.line(bolt+[bolt[0]],fill=(3,16,24,205),width=max(1,round(.6*S)),joint='curve')
    draw.polygon(bolt,fill=mat.WHITE+(255,))
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
    """Align the rail ends to the wings' horizontal span with a soft fade."""
    row=Image.new('L',(geo.WIDTH*S,1))
    values=[]
    for xx in range(row.width):
        x=geo.CX+abs(xx/S-geo.CX)
        fade=mat._smooth((x-geo.WING_FACE_START)/1.25)
        fade*=mat._smooth((geo.DRS_RAIL_END+28.-x)/32.)
        values.append(round(255*fade))
    row.putdata(values)
    return row.resize((geo.WIDTH*S,geo.HEIGHT*S),Image.Resampling.NEAREST)

def clip_drs(image):
    image.putalpha(ImageChops.multiply(image.getchannel('A'),drs_clip_mask()))
    return image


@lru_cache(maxsize=1)
def drs_rails():
    image=art.canvas()
    for edge in geo.DRS_RAIL_EDGES:
        for side in (-1,1):
            points=geo.drs_rail_points(edge)
            if side<0:
                points=[(2*geo.CX-x,y) for x,y in points]
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
            (round((.5 + (x - geo.CX) / geo.PEDAL_MASK_SPAN) * sample_size),
             round((.5 + (y - geo.CY) / geo.PEDAL_MASK_SPAN) * sample_size))
            for x, y in geo.slat_points(side, index)
        ]
        draw.polygon(points, fill=(255, 255, 255, 255))
    return image.resize((size, size), Image.Resampling.LANCZOS)
