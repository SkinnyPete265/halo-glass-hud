"""One art-space geometry source for composition, artwork and previews."""
from dataclasses import dataclass
import math
from .tuning import values

STYLE = values()

WIDTH, HEIGHT = 1200, 440
CX, CY = 582.0, 95.0
RADIUS = 640.0
# Restore the v0.31.0 effective scale: 0.0065 * 1.485 / 0.018.
HUD_SCALE = 0.53625
WING_HEIGHT = 122.0 * 1.15
WING_FACE_TOP = 10.0
WING_FACE_BOTTOM = WING_HEIGHT - 9.0
WING_FACE_START = 745.0
WING_FACE_END = 1068.0  # About 10% more backing, on the existing contour sample grid.
WING_CORNER_RADIUS = 8.0
DRS_RAIL_START = WING_FACE_START + WING_CORNER_RADIUS
DRS_RAIL_END = 1032.0  # About 10% longer along the curved wing.
DRS_RAIL_EDGES = ('top', 'bottom')
DRS_OPEN_CURVE = 'generic_fade_on_slow'
DRS_OPEN_DURATION = .30
DRS_CLOSE_DURATION = .075
DRS_CLOSE_CURVE = 'generic_fade_off_fast'
HUD_BOX_BOTTOM = 412.0 + (WING_HEIGHT - 122.0)
BATTERY_CENTRE = (CX, STYLE['battery_y'])
BATTERY_WIDTH, BATTERY_HEIGHT = STYLE['battery_width'], STYLE['battery_height']
BATTERY_CORNER_RADIUS = BATTERY_HEIGHT * .28
BATTERY_TEXTURE_RESOLUTION = 3
BATTERY_FILL_FEATHER = 0.0
BATTERY_FILL_INSET = 3.0
DRS_CENTRE = (CX, 211.0)
# All DRS status text uses the same native family as the HUD readouts.
DRS_STATUS_TEXT_SIZE = 17.5
DRS_TEXT_STYLE = 'OSD_24_bold'
DRS_TEXT_COLOUR = (154, 247, 199, 255)
DRS_PROMPT_COLOUR = (255, 255, 255, 255)
DRS_PROMPT_OUTLINE_RADIUS = .4
DRS_PROMPT_OUTLINE_ALPHA = 85
DRS_LABEL_GLOW_RADIUS = .7
DRS_LABEL_GLOW_ALPHA = 8
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
    return [(cx + .7, cy - 4.7), (cx - 3.6, cy + .3),
            (cx - .4, cy + .3), (cx - 1.0, cy + 4.7),
            (cx + 3.9, cy - .9), (cx + .9, cy - .9)]

FONT_PATH = "assets/fonts/Saira/Saira.ttf"

@dataclass(frozen=True)
class Text:
    x: float
    y: float
    size: float
    rotation: float = 0.0

SPEED = Text(CX, STYLE['speed_y'], STYLE['speed_size'])
KPH = Text(CX, CY - 34.0, 15.0)
SPECIAL_GEAR = Text(CX, CY + 72.0, 19.0)
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
RPM_LABEL_GLOW_RINGS = ((0.9, 14),)
RPM_LABEL_GLOW_SAMPLES = 4
RPM_NUMBER_GLOW_RINGS = ((1.2, 10),)
RPM_NUMBER_GLOW_SAMPLES = 6
BASE_TEXTURE_RESOLUTION = 2
PEDAL_INNER_RADIUS = 95.5
PEDAL_OUTER_RADIUS = PEDAL_INNER_RADIUS + (137.0 - PEDAL_INNER_RADIUS) * 1.20
PEDAL_MASK_SCALE = 2.20
PEDAL_MASK_SPAN = .92 * PEDAL_MASK_SCALE / .0065


def gears_caption():
    x = 902.5
    return Text(x, top(x) + 23.0, STYLE['gears_size'], angle(x))

def top(x):
    return 30.0 + RADIUS - math.sqrt(RADIUS ** 2 - (x - CX) ** 2)

def angle(x):
    return math.degrees(math.asin((x - CX) / RADIUS))

def wing_face_bounds(x):
    corner_x = max(WING_FACE_START + WING_CORNER_RADIUS - x, 0.)
    corner = WING_CORNER_RADIUS - math.sqrt(max(0., WING_CORNER_RADIUS ** 2 - corner_x ** 2))
    return top(x) + WING_FACE_TOP + corner, top(x) + WING_FACE_BOTTOM - corner


def drs_rail_points(edge):
    offset = 5.0 if edge == 'top' else WING_HEIGHT - 5.0
    return [(x, top(x) + offset)
            for x in range(round(DRS_RAIL_START), round(DRS_RAIL_END) + 1)]


def arc_length(x):
    return RADIUS * math.asin((x - CX) / RADIUS)

def gear_position(gear):
    distance = arc_length(780.0) + (
        arc_length(1025.0) - arc_length(780.0)
    ) * (gear - 1) / 7
    x = CX + RADIUS * math.sin(distance / RADIUS)
    return Text(x, top(x) + GEAR_ROW_OFFSET, GEAR_NUMBER_SIZE, angle(x) * 0.25)

def rpm_position():
    x = 902.5
    return Text(x, top(x) + RPM_READOUT_OFFSET, RPM_NUMBER_SIZE, angle(x) * 0.30)

def hud_point(x, y):
    return [round((x - CX) * HUD_SCALE, 6),
            round((y - CY) * HUD_SCALE, 6)]

def hud_bounds(box):
    return hud_point(*box[:2]) + hud_point(*box[2:])

def rpm_points():
    return [(x, top(x) + RPM_BAR_OFFSET) for x in range(780, 1026)]

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
