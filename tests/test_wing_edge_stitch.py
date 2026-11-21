"""Verify filtered exterior edge passes stitch to the continuous render."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
from halo import layout, material
from halo.tuning import values


class WingEdgeStitchTests(unittest.TestCase):
    def test_split_matches_continuous_render_at_supported_extensions(self):
        original = values()
        results = []
        try:
            for variant in ('B', 'B+4'):
                for extension in (60, 75):
                    layout.refresh_style(dict(original, wing_extension=extension))
                    material.sync_layout()
                    padding = layout.WING_TEXTURE_PADDING
                    width = (layout.WIDTH + 2 * padding) * material.S
                    top_padding = layout.ARTWORK_TOP_PADDING
                    height = round((layout.HEIGHT + top_padding) * material.S)
                    split = layout.WING_TEXTURE_NATIVE_END_DISTANCE
                    start = layout.WING_FACE_START - layout.CX
                    end = layout.WING_TEXTURE_END - layout.CX

                    continuous = material.wing_edge_effects(
                        padding=padding, draw_from=start, draw_to=end, variant=variant,
                        top_padding=top_padding,
                    )
                    native = material.wing_edge_effects(
                        padding=0, draw_from=start, draw_to=split, variant=variant,
                        context_split=split, top_padding=top_padding,
                    )
                    tail = material.wing_edge_effects(
                        padding=padding, draw_from=split, draw_to=end, variant=variant,
                        context_split=split, top_padding=top_padding,
                    )
                    stitched = Image.new('RGBA', (width, height))
                    stitched.alpha_composite(native, (padding * material.S, 0))
                    stitched.alpha_composite(tail)

                    self.assertEqual(stitched.size, continuous.size)
                    self.assertEqual(
                        stitched.tobytes(), continuous.tobytes(),
                        f'{variant} {extension}px stitched exterior differs from continuous render',
                    )

                    # Every pixel centre in the exterior-effect interval belongs to
                    # exactly one half-open pass on each mirrored wing.
                    for x in range(width):
                        distance_from_hub = (
                            (x + .5) / material.S - padding - layout.CX
                        )
                        for side in (-1, 1):
                            distance = side * distance_from_hub
                            in_full = start <= distance < end
                            native_owns = start <= distance < split
                            tail_owns = split <= distance < end
                            self.assertEqual(
                                int(native_owns) + int(tail_owns), int(in_full),
                                f'{variant} {extension}px column {x} side {side} has incorrect ownership',
                            )

                    results.append((variant, extension, stitched.size, split, start, end))
        finally:
            layout.refresh_style(original)
            material.sync_layout()

        for variant, extension, size, split, start, end in results:
            print(
                f'{variant} {extension}px: {size[0]}x{size[1]}, split={split:g}, '
                f'owned interval=[{start:g}, {end:g}); stitched pixels match continuous'
            )


if __name__ == '__main__':
    unittest.main()
