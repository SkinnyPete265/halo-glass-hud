"""One art-space geometry source for composition, artwork and previews."""
from dataclasses import dataclass
import math
from .tuning import values

STYLE = values()

WIDTH = 1200
HEIGHT = 440
CX, CY = 582.0, 95.0
# Transparent room for the speedometer's existing outer halo. The disc's
# current 6 px top clearance is shorter than the 4-sigma glow extent.
ARTWORK_TOP_PADDING = 24.0
WHITE_ARC_CROWN = CY - 1.5 * 89.
WHITE_ARC_TOP = math.floor(WHITE_ARC_CROWN) - 4
# A wider arc reduces the falloff across extended wings while preserving the
# hub and the wings' cross-section height.
RADIUS = 850.0


def top(x):
    return 30.0 + RADIUS - math.sqrt(RADIUS ** 2 - (x - CX) ** 2)


# Treat the previously approved 110% size as the new 100% baseline.
HUD_SIZE_BASE_FACTOR = 1.10
HUD_SIZE_FACTOR = HUD_SIZE_BASE_FACTOR * STYLE['hud_size'] / 100.0
# Restore the v0.31.0 effective scale: 0.0065 * 1.485 / 0.018.
HUD_SCALE = 0.53625 * HUD_SIZE_FACTOR
BASE_WING_HEIGHT = 122.0 * 1.15
WING_HEIGHT = BASE_WING_HEIGHT
WING_CENTER_OFFSET = BASE_WING_HEIGHT / 2
WING_FACE_TOP = 10.0
WING_FACE_BOTTOM = WING_HEIGHT - 9.0
WING_FACE_CENTER_OFFSET = (WING_FACE_TOP + WING_FACE_BOTTOM) / 2
MAX_WING_TIP_HEIGHT_INCREASE = 10.0
WING_FACE_START = 745.0
BASE_WING_FACE_END = 1068.0
WING_FACE_END = BASE_WING_FACE_END + STYLE['wing_extension']
WING_EFFECT_END = WING_FACE_END + 21.0
WING_TEXTURE_OVERHANG = 78.0
WING_TEXTURE_EXTENSION = WING_TEXTURE_OVERHANG - 21.0
WING_TEXTURE_END = WING_FACE_END + WING_TEXTURE_OVERHANG
WING_TEXTURE_NATIVE_END_DISTANCE = min(CX, WIDTH - CX) - 3.0
WING_TEXTURE_PADDING = max(0, math.ceil(WING_TEXTURE_END - 2 * CX) + 6)
WING_CORNER_RADIUS = 8.0


def wing_cross_section_scale(x):
    """Compensate for the arc narrowing the wing at its extended outer tip."""
    distance = abs(x - CX)
    base_distance = BASE_WING_FACE_END - CX
    if distance <= base_distance or STYLE['wing_extension'] <= 0:
        return 1.0
    distance = min(distance, WING_FACE_END - CX)
    base_normal = math.sqrt(RADIUS ** 2 - base_distance ** 2) / RADIUS
    current_normal = math.sqrt(RADIUS ** 2 - distance ** 2) / RADIUS
    scale = base_normal / current_normal
    # Preserve the band's original proportions without making the wing taller.
    maximum = (BASE_WING_HEIGHT + MAX_WING_TIP_HEIGHT_INCREASE) / BASE_WING_HEIGHT
    return min(scale, maximum)


def wing_backing_bounds(x):
    """Return the symmetrically widened outer wing bounds at this x position."""
    scale = wing_cross_section_scale(x)
    return (
        top(x) + WING_CENTER_OFFSET - WING_HEIGHT / 2 * scale,
        top(x) + WING_CENTER_OFFSET + WING_HEIGHT / 2 * scale,
    )


def wing_face_edges(x):
    """Return the face edges, widened around the original wing centreline."""
    scale = wing_cross_section_scale(x)
    half_height = (WING_FACE_BOTTOM - WING_FACE_TOP) / 2
    return (
        top(x) + WING_FACE_CENTER_OFFSET - half_height * scale,
        top(x) + WING_FACE_CENTER_OFFSET + half_height * scale,
    )


WING_TIP_TOP = wing_backing_bounds(WING_FACE_END)[0]
WING_TIP_BOTTOM = wing_backing_bounds(WING_FACE_END)[1]
HEIGHT = max(440, math.ceil(wing_backing_bounds(WING_EFFECT_END)[1] + 45.0))
DRS_RAIL_START = WING_FACE_START + WING_CORNER_RADIUS
DRS_RAIL_END = WING_FACE_END
DRS_RAIL_EDGES = ('top', 'bottom')
DRS_OPEN_CURVE = 'generic_fade_on_slow'
DRS_OPEN_DURATION = .30
DRS_CLOSE_DURATION = .075
DRS_CLOSE_CURVE = 'generic_fade_off_fast'
HUD_BOX_BOTTOM = max(422.0, wing_backing_bounds(WING_EFFECT_END)[1] + 34.0)
BATTERY_CENTRE = (CX, STYLE['battery_y'])
BATTERY_WIDTH, BATTERY_HEIGHT = STYLE['battery_width'], STYLE['battery_height']
BATTERY_CORNER_RADIUS = BATTERY_HEIGHT * .16
BATTERY_TEXTURE_RESOLUTION = 3
BATTERY_FILL_FEATHER = 0.0
# Let the fill meet the one-pixel rim with one supersampled texel of overlap.
BATTERY_FILL_INSET = 1.0 - 1.0 / BATTERY_TEXTURE_RESOLUTION
DRS_CENTRE = (CX, 211.0)
# All DRS status text uses the same native family as the HUD readouts.
DRS_STATUS_TEXT_SIZE = 17.5
DRS_TEXT_STYLE = 'OSD_24_bold'
DRS_TEXT_COLOUR = (154, 247, 199, 255)
DRS_PROMPT_COLOUR = (255, 255, 255, 255)
DRS_PROMPT_OUTLINE_RADIUS = .4 * STYLE['text_outline']
DRS_PROMPT_OUTLINE_ALPHA = round(85 * STYLE['text_glow_strength'] / 100.)
DRS_LABEL_GLOW_RADIUS = .7 * STYLE['text_glow']
DRS_LABEL_GLOW_ALPHA = round(8 * STYLE['text_glow_strength'] / 100.)
DRS_DISTANCE_GAP = 5.5
DRS_PROMPT_GAP = 8.0


def battery_fill_bounds():
    cx, cy = BATTERY_CENTRE
    return (cx - BATTERY_WIDTH / 2 + BATTERY_FILL_INSET,
            cy - BATTERY_HEIGHT / 2 + BATTERY_FILL_INSET,
            cx + BATTERY_WIDTH / 2 - BATTERY_FILL_INSET,
            cy + BATTERY_HEIGHT / 2 - BATTERY_FILL_INSET)


def battery_fill_edge(charge):
    left, _, right, _ = battery_fill_bounds()
    return left + (right - left) * charge + BATTERY_FILL_FEATHER / 2

def battery_bolt_points():
    cx, cy = BATTERY_CENTRE
    # A narrow, forward-leaning flash with an offset kink, traced from the reference.
    points = [(2.9,-5.8), (-3.3,.4), (-.4,.4), (-2.4,5.8), (3.2,-.8), (.5,-.8)]
    scale = BATTERY_HEIGHT / 23.5
    return [(cx+x*scale,cy+y*scale) for x,y in points]

FONT_PATH = "assets/fonts/Saira/Saira.ttf"

@dataclass(frozen=True)
class Text:
    x: float
    y: float
    size: float
    rotation: float = 0.0

SPEED = Text(CX, STYLE['speed_y'], STYLE['speed_size'])
KPH = Text(CX, CY - 57., 14.)


def circle_speed(season26):
    return Text(SPEED.x, SPEED.y - 34., SPEED.size)


def circle_readouts(season26):
    return (
        ('kph_unit', KPH, 'KM/H'),
        ('mph', Text(CX, CY + 37., SPEED.size * .77), None),
        ('mph_unit', Text(CX, CY + 55., 14.), 'MPH'),
    )


BOOST_STATUS = Text(CX, CY - 5., 13.)
OVERTAKE_STATUS = Text(CX, CY + 12., 13.)
SPECIAL_GEAR = Text(CX - 46., CY + 76., 14.)
GEAR_ROW_OFFSET = 57.0
GEAR_NUMBER_SIZE = 17.0 * 0.97 * 1.02
GEAR_SELECTED_SIZE = 27.0 * 0.97 * 1.05
GEAR_FADE_START = 0.30
GEAR_FADE_DURATION = 0.15
SECTOR_FADE_START = .55
SECTOR_FADE_CURVE = 'generic_fade_on'
SECTOR_FADE_DURATION = .15
RPM_BAR_OFFSET = 87.0
RPM_BAR_WIDTH = STYLE['rpm_width']
GEARS_FONT_WEIGHT = STYLE['gears_weight']
RPM_READOUT_OFFSET = 114.0
RPM_NUMBER_SIZE = 16.5 * 0.95
UNIT_LABEL_SIZE = 12.5
RPM_UNIT_GAP = 10.0
RPM_LABEL_GLOW_RINGS = ((0.9 * STYLE['text_glow'], round(14 * STYLE['text_glow_strength'] / 100.)),)
RPM_LABEL_GLOW_SAMPLES = 4
RPM_NUMBER_GLOW_RINGS = ((1.2 * STYLE['text_glow'], round(10 * STYLE['text_glow_strength'] / 100.)),)
RPM_NUMBER_GLOW_SAMPLES = 6
BASE_TEXTURE_RESOLUTION = 3
PEDAL_INNER_RADIUS = 95.5
PEDAL_OUTER_RADIUS = PEDAL_INNER_RADIUS + (137.0 - PEDAL_INNER_RADIUS) * 1.20
PEDAL_MASK_SCALE = 2.20
PEDAL_MASK_SPAN = .92 * PEDAL_MASK_SCALE / .0065


def gears_caption():
    x = wing_content_x(STYLE['gears_x'])
    return Text(x, top(x) + STYLE['gears_y'], STYLE['gears_size'], angle(x))

def angle(x):
    return math.degrees(math.asin((x - CX) / RADIUS))

def wing_content_x(x):
    """Keep wing-mounted content at the same relative position as each wing grows."""
    if not STYLE['wing_content_follow'] or STYLE['wing_extension'] == 0:
        return x
    scale = (WING_FACE_END - WING_FACE_START) / (BASE_WING_FACE_END - WING_FACE_START)
    left_root = 2 * CX - WING_FACE_START
    if x >= WING_FACE_START:
        return WING_FACE_START + (x - WING_FACE_START) * scale
    if x <= left_root:
        return left_root + (x - left_root) * scale
    return x

def wing_content_point(x, y):
    """Map a wing-mounted point and keep it at the same offset from the arc."""
    moved_x = wing_content_x(x)
    return moved_x, y + top(moved_x) - top(x)

def wing_face_bounds(x):
    corner_x = max(WING_FACE_START + WING_CORNER_RADIUS - x, 0.)
    corner = WING_CORNER_RADIUS - math.sqrt(max(0., WING_CORNER_RADIUS ** 2 - corner_x ** 2))
    upper, lower = wing_face_edges(x)
    return upper + corner, lower - corner


def drs_rail_points(edge):
    points = []
    for x in range(round(DRS_RAIL_START), round(DRS_RAIL_END) + 1):
        upper, lower = wing_backing_bounds(x)
        points.append((x, upper + 5.0 if edge == 'top' else lower - 5.0))
    return points


def arc_length(x):
    return RADIUS * math.asin((x - CX) / RADIUS)

def gear_position(gear):
    distance = arc_length(780.0) + (
        arc_length(1025.0) - arc_length(780.0)
    ) * (gear - 1) / 7
    x = wing_content_x(CX + RADIUS * math.sin(distance / RADIUS))
    return Text(x, top(x) + GEAR_ROW_OFFSET, GEAR_NUMBER_SIZE, angle(x) * 0.25)

def rpm_position():
    x = wing_content_x(902.5)
    return Text(x, top(x) + RPM_READOUT_OFFSET, RPM_NUMBER_SIZE, angle(x) * 0.30)

def hud_point(x, y):
    return [round((x - CX) * HUD_SCALE, 6),
            round((y - CY) * HUD_SCALE, 6)]

def hud_bounds(box):
    return hud_point(*box[:2]) + hud_point(*box[2:])

def rpm_points():
    points = []
    for original_x in range(780, 1026):
        x = wing_content_x(original_x)
        points.append((x, top(x) + RPM_BAR_OFFSET))
    return points

def slat_points(side, index):
    """The accepted straight slats follow concentric speed-circle rails."""
    y_ref = CY + 51.85 + 1.26442 - index * 9.8
    slope, x_ref = 0.205, 126.5
    def on_circle(radius, offset):
        intercept = y_ref - CY - slope * x_ref + offset
        a = 1.0 + slope * slope
        discriminant = (slope * intercept) ** 2 - a * (
            intercept * intercept - radius * radius)
        x = (-slope * intercept + math.sqrt(discriminant)) / a
        return CX + side * x, CY + slope * x + intercept
    return [on_circle(PEDAL_INNER_RADIUS, -3.55), on_circle(PEDAL_OUTER_RADIUS, -3.55),
            on_circle(PEDAL_OUTER_RADIUS, 3.55), on_circle(PEDAL_INNER_RADIUS, 3.55)]


def point(x, offset):
    return x, top(x) + offset



def pedal_label(side):
    """Initial label anchor below the complete pedal bank, aligned to the wing."""
    points = [point for index in range(10) for point in slat_points(side, index)]
    x = (min(point[0] for point in points) + max(point[0] for point in points)) / 2
    y = max(point[1] for point in points) + 14.0
    return Text(x, y, UNIT_LABEL_SIZE * 0.97, angle(x))


def refresh_style(style=None):
    """Refresh style-derived layout values for the interactive preview process."""
    global STYLE, HUD_SIZE_FACTOR, HUD_SCALE, WING_FACE_END, WING_EFFECT_END
    global WING_TEXTURE_EXTENSION, WING_TEXTURE_END
    global WING_TEXTURE_NATIVE_END_DISTANCE, WING_TEXTURE_PADDING
    global WING_TIP_TOP, WING_TIP_BOTTOM, HEIGHT
    global DRS_RAIL_END, HUD_BOX_BOTTOM, BATTERY_CENTRE, BATTERY_WIDTH
    global BATTERY_HEIGHT, BATTERY_CORNER_RADIUS, DRS_PROMPT_OUTLINE_RADIUS
    global DRS_PROMPT_OUTLINE_ALPHA, DRS_LABEL_GLOW_RADIUS, DRS_LABEL_GLOW_ALPHA
    global SPEED, RPM_BAR_WIDTH, GEARS_FONT_WEIGHT
    global RPM_LABEL_GLOW_RINGS, RPM_NUMBER_GLOW_RINGS

    STYLE = values() if style is None else style
    HUD_SIZE_FACTOR = HUD_SIZE_BASE_FACTOR * STYLE['hud_size'] / 100.0
    HUD_SCALE = 0.53625 * HUD_SIZE_FACTOR
    WING_FACE_END = BASE_WING_FACE_END + STYLE['wing_extension']
    WING_EFFECT_END = WING_FACE_END + 21.0
    WING_TEXTURE_EXTENSION = WING_TEXTURE_OVERHANG - 21.0
    WING_TEXTURE_END = WING_FACE_END + WING_TEXTURE_OVERHANG
    WING_TEXTURE_NATIVE_END_DISTANCE = min(CX, WIDTH - CX) - 3.0
    WING_TEXTURE_PADDING = max(0, math.ceil(WING_TEXTURE_END - 2 * CX) + 6)
    WING_TIP_TOP, WING_TIP_BOTTOM = wing_backing_bounds(WING_FACE_END)
    HEIGHT = max(440, math.ceil(wing_backing_bounds(WING_EFFECT_END)[1] + 45.0))
    DRS_RAIL_END = WING_FACE_END
    HUD_BOX_BOTTOM = max(422.0, wing_backing_bounds(WING_EFFECT_END)[1] + 34.0)
    BATTERY_CENTRE = (CX, STYLE['battery_y'])
    BATTERY_WIDTH = STYLE['battery_width']
    BATTERY_HEIGHT = STYLE['battery_height']
    BATTERY_CORNER_RADIUS = BATTERY_HEIGHT * .16
    DRS_PROMPT_OUTLINE_RADIUS = .4 * STYLE['text_outline']
    DRS_PROMPT_OUTLINE_ALPHA = round(85 * STYLE['text_glow_strength'] / 100.)
    DRS_LABEL_GLOW_RADIUS = .7 * STYLE['text_glow']
    DRS_LABEL_GLOW_ALPHA = round(8 * STYLE['text_glow_strength'] / 100.)
    SPEED = Text(CX, STYLE['speed_y'], STYLE['speed_size'])
    RPM_BAR_WIDTH = STYLE['rpm_width']
    GEARS_FONT_WEIGHT = STYLE['gears_weight']
    RPM_LABEL_GLOW_RINGS = (
        (.9 * STYLE['text_glow'], round(14 * STYLE['text_glow_strength'] / 100.)),
    )
    RPM_NUMBER_GLOW_RINGS = (
        (1.2 * STYLE['text_glow'], round(10 * STYLE['text_glow_strength'] / 100.)),
    )
