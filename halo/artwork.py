"""Data-free sprites. Shared geometry supplies every instrument anchor."""
import math
from PIL import Image, ImageDraw, ImageChops
from . import layout as geo, material as mat

S = mat.S
RPM_WARNING_START = 0.83
RPM_WARNING_COLOUR = (255, 36, 52)

def rpm_warning_weight(fraction):
    weight = max(0.0, min(1.0, (fraction - RPM_WARNING_START) /
                           (1.0 - RPM_WARNING_START)))
    return weight * weight * (3.0 - 2.0 * weight)


def canvas():
    return Image.new("RGBA", (geo.WIDTH * S, geo.HEIGHT * S))

def label(image, spec, value, **options):
    mat.text(image, spec.x, spec.y, value, spec.size,
             rotation=spec.rotation, **options)

def base():
    image = mat.glass_wings()
    image.alpha_composite(mat.pedal_backing())
    image.alpha_composite(mat.pedal_accents())
    disc = canvas()
    pixels = disc.load()
    radius = 89.0
    for yy in range(round((geo.CY - radius) * S), round((geo.CY + radius) * S) + 1):
        for xx in range(round((geo.CX - radius) * S), round((geo.CX + radius) * S) + 1):
            dx = ((xx + .5) / S - geo.CX) / radius
            dy = ((yy + .5) / S - geo.CY) / radius
            distance = math.hypot(dx, dy)
            coverage = max(0., min(1., .5 + (1. - distance) * radius * S))
            if coverage == 0:
                continue
            highlight = math.exp(-((dy + .6) / .3) ** 2) * max(0, 1 - distance ** 2)
            pixels[xx, yy] = (round(7 + 18 * highlight),
                              round(29 + 30 * highlight),
                              round(40 + 37 * highlight), round((195 + 24 * min(distance, 1.)) * coverage))
    image.alpha_composite(disc)
    image = mat.circle_stroke(image, (geo.CX, geo.CY), radius, mat.CYAN + (125,), 3.0, 4.5)
    image = mat.circle_stroke(image, (geo.CX, geo.CY), radius, (150, 210, 238, 170), .8, 1.0)
    speed_ring = [(geo.CX + 61 * math.cos(a), geo.CY + 61 * math.sin(a))
                  for a in (math.radians(140 + 260 * i / 180) for i in range(181))]
    image = mat.stroke(image, speed_ring, mat.WHITE + (230,), 1.6, .8)
    idle_slats = canvas()
    draw = ImageDraw.Draw(idle_slats)
    for side in (-1, 1):
        for index in range(10):
            draw.polygon([(round(x * S), round(y * S))
                          for x, y in geo.slat_points(side, index)],
                         fill=(126, 176, 187, 55))
    image.alpha_composite(idle_slats)
    label(image, geo.KPH, "KPH",
          color=(176, 211, 232, 240))
    label(image, geo.gears_caption(), "GEARS", weight=geo.GEARS_FONT_WEIGHT, glow=True,
          glow_color=(221, 242, 253), outline=.45)
    return mat.rounded_stroke(image, geo.rpm_points(), mat.WHITE + (30,), geo.RPM_BAR_WIDTH)

def rpm_fill():
    points = geo.rpm_points()
    image = mat.rounded_stroke(canvas(), points, (221, 242, 253, 242), geo.RPM_BAR_WIDTH, 2.5)
    first, last = points[0][0], points[-1][0]
    gradient = Image.new("L", (image.width, 1))
    gradient.putdata([
        round(255 * rpm_warning_weight((x / S - first) / (last - first)))
        for x in range(image.width)
    ])
    gradient = gradient.resize(image.size, Image.Resampling.NEAREST)
    warning = Image.new("RGBA", image.size, RPM_WARNING_COLOUR + (0,))
    warning.putalpha(ImageChops.multiply(image.getchannel("A"), gradient))
    image.alpha_composite(warning)
    return image

def finish(image, resolution=1, resample=Image.Resampling.LANCZOS):
    return image.resize((geo.WIDTH * resolution, geo.HEIGHT * resolution), resample)
