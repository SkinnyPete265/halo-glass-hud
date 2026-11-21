"""Validated shared style settings for authoring and the local tuning tool."""

import json
import math
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = {
    "battery_width": ("Battery width", 30.0, 120.0, 0.5),
    "battery_height": ("Battery height", 12.0, 44.0, 0.25),
    "battery_y": ("Battery vertical position", 115.0, 185.0, 0.5),
    "gears_size": ("GEARS size", 8.0, 22.0, 0.25),
    "gears_weight": ("GEARS weight", 300.0, 900.0, 10.0),
    "gears_x": ("GEARS horizontal position", 780.0, 1025.0, 1.0),
    "gears_y": ("GEARS vertical position", 0.0, 60.0, 0.5),
    "hud_size": ("Overall HUD size (%)", 70.0, 130.0, 1.0),
    "wing_extension": ("Wing outward extension", 0.0, 75.0, 1.0),
    "text_size": ("All text size (%)", 60.0, 150.0, 1.0),
    "text_glow": ("Text outer glow radius", 0.0, 3.0, 0.05),
    "text_glow_strength": ("Text glow strength (%)", 0.0, 200.0, 1.0),
    "text_outline": ("Text outline width (%)", 0.0, 200.0, 1.0),
    "speed_size": ("Speed number size", 24.0, 56.0, 0.5),
    "speed_y": ("Speed vertical position", 70.0, 120.0, 0.5),
    "rpm_width": ("RPM bar width", 2.0, 8.0, 0.1),
}
COLOURS = {
    "gears_colour": "GEARS colour",
    "text_colour": "All other text colour",
    "battery_blue": "Battery high-charge colour",
    "battery_yellow": "Battery mid-charge colour",
    "battery_red": "Battery low-charge colour",
}
FLAGS = {
    "wing_content_follow": "Keep wing content proportional",
}
ART_ONLY_KEYS = frozenset(("gears_size", "gears_weight", "gears_colour"))


def validate(values):
    if not isinstance(values, dict) or set(values) != (
        set(SPECS) | set(COLOURS) | set(FLAGS)
    ):
        raise ValueError("Style settings must contain exactly the supported keys")
    result = {}
    for key, value in values.items():
        if key in FLAGS:
            if not isinstance(value, bool):
                raise ValueError("Expected a boolean for " + key)
            result[key] = value
            continue
        if key in COLOURS:
            if not isinstance(value, str) or not re.fullmatch(
                r"#[0-9a-fA-F]{6}", value
            ):
                raise ValueError("Expected #RRGGBB for " + key)
            result[key] = value.lower()
            continue
        _, minimum, maximum, _ = SPECS[key]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("Expected a finite number for " + key)
        if not minimum <= value <= maximum:
            raise ValueError("Style value outside range for " + key)
        result[key] = value
    return result


def values():
    path = Path(os.environ.get("HALO_TUNING_FILE", ROOT / "style.json"))
    return validate(json.loads(path.read_text(encoding="utf-8")))


def rgb(value):
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def schema():
    result = {
        key: {
            "label": label,
            "type": "number",
            "min": minimum,
            "max": maximum,
            "step": step,
        }
        for key, (label, minimum, maximum, step) in SPECS.items()
    }
    result.update(
        {key: {"label": label, "type": "colour"} for key, label in COLOURS.items()}
    )
    result.update(
        {key: {"label": label, "type": "boolean"} for key, label in FLAGS.items()}
    )
    return result
