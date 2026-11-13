"""Instrument definitions shared by native authoring and offline previews."""
import math
from . import artwork as art, layout as geo, material as mat

S = art.S

BATTERY_BLUE = (86, 199, 237)
BATTERY_RED = (235, 78, 91)
BATTERY_YELLOW = (245, 213, 76)
# The same charge-domain curve runs in both discharge and recharge directions.
BATTERY_COLOUR_KEYS = (
    (0.00, BATTERY_RED),
    (0.10, BATTERY_RED),
    (0.125, BATTERY_YELLOW),
    (0.30, BATTERY_YELLOW),
    (0.35, BATTERY_BLUE),
    (1.00, BATTERY_BLUE),
)

def battery_colour(charge):
    charge = max(0.0, min(1.0, charge))
    for (lower, first), (upper, second) in zip(
            BATTERY_COLOUR_KEYS, BATTERY_COLOUR_KEYS[1:]):
        if charge <= upper:
            weight = (charge - lower) / (upper - lower)
            return tuple(round(a + (b - a) * weight)
                         for a, b in zip(first, second))
    return BATTERY_BLUE


def rpm_labels(value):
    """Centre the complete number/unit pair along the wing's arc."""
    number = str(value)
    centre = geo.rpm_position()
    number_size, unit_size, gap = centre.size, geo.UNIT_LABEL_SIZE, geo.RPM_UNIT_GAP
    number_width = mat.typeface(round(number_size * S), 600).getlength(number) / S
    unit_width = mat.typeface(round(unit_size * S), 600).getlength("RPM") / S
    number_width += 2 * max(radius for radius, alpha in geo.RPM_NUMBER_GLOW_RINGS)
    unit_width += 2 * max(radius for radius, alpha in geo.RPM_LABEL_GLOW_RINGS)
    baseline_angle = geo.angle(centre.x)
    rotation = math.radians(baseline_angle)
    number_offset = -(unit_width + gap) / 2
    unit_offset = (number_width + gap) / 2
    number_at = geo.Text(
        centre.x + number_offset * math.cos(rotation),
        centre.y + number_offset * math.sin(rotation),
        number_size, baseline_angle)
    baseline_offset = (number_size - unit_size) * .336
    unit_at = geo.Text(
        centre.x + unit_offset * math.cos(rotation) - baseline_offset * math.sin(rotation),
        centre.y + unit_offset * math.sin(rotation) + baseline_offset * math.cos(rotation),
        unit_size, baseline_angle)
    return number_at, unit_at


def gear_artwork(gear, selected):
    image = art.canvas()
    spec = geo.gear_position(gear)
    art.label(image, geo.Text(spec.x, spec.y, geo.GEAR_SELECTED_SIZE if selected else spec.size,
                              spec.rotation), str(gear),
              color=(mat.GEAR_SELECTED_CORE if selected else mat.GEAR_IDLE_CORE) + (255,),
              weight=750 if selected else 550, glow=selected, outline=.45)
    return image
