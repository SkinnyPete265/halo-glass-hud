"""Verify the stable texture crop and supported wing-extension expansion."""
import sys
import unittest

ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from halo import artwork, instruments, layout, material
from halo.composition import STABLE_BASE_CROP, crop_sprite
from halo.tuning import values


class CompositionCropTests(unittest.TestCase):
    def test_60px_stays_stable_and_75px_expands_without_clipping(self):
        original = values()
        results = []
        try:
            for extension in (60, 75):
                style = dict(original, wing_extension=extension)
                layout.refresh_style(style)
                material.sync_layout()
                instruments.refresh_style()
                artwork.base_static.cache_clear()

                source = artwork.finish(
                    artwork.texture_base('B'), layout.BASE_TEXTURE_RESOLUTION)
                alpha = source.getchannel('A')
                actual = alpha.getbbox()
                self.assertIsNotNone(actual)
                prepared, crop = crop_sprite('base', source)
                left, top, right, bottom = crop
                self.assertTrue(all(dimension % 4 == 0
                                    for dimension in (right - left, bottom - top)))
                self.assertGreaterEqual(actual[0], left)
                self.assertGreaterEqual(actual[1], top)
                self.assertLessEqual(actual[2], right)
                self.assertLessEqual(actual[3], bottom)

                if extension == 60:
                    self.assertEqual(crop, STABLE_BASE_CROP)
                    self.assertEqual(
                        (right - left, bottom - top),
                        (3728, 1320 + round(layout.ARTWORK_TOP_PADDING
                                           * layout.BASE_TEXTURE_RESOLUTION)),
                    )
                else:
                    self.assertNotEqual(crop, STABLE_BASE_CROP)

                # Confirm the crop plus sprite origin leaves the hub and both
                # full tail anchors at their authored HUD-space coordinates.
                origin_x = left / layout.BASE_TEXTURE_RESOLUTION - layout.WING_TEXTURE_PADDING
                origin_y = top / layout.BASE_TEXTURE_RESOLUTION - layout.ARTWORK_TOP_PADDING
                for x, y in (
                    (layout.CX, layout.CY),
                    (layout.WING_FACE_START, layout.top(layout.WING_FACE_START)),
                    (layout.WING_FACE_END, layout.top(layout.WING_FACE_END)),
                    (layout.WING_TEXTURE_END - 5., layout.top(layout.WING_TEXTURE_END - 5.)),
                    (2 * layout.CX - (layout.WING_TEXTURE_END - 5.),
                     layout.top(layout.WING_TEXTURE_END - 5.)),
                ):
                    source_x = (x + layout.WING_TEXTURE_PADDING) * layout.BASE_TEXTURE_RESOLUTION
                    crop_x = source_x - left
                    mapped_x = origin_x + crop_x / layout.BASE_TEXTURE_RESOLUTION
                    source_y = (y + layout.ARTWORK_TOP_PADDING) * layout.BASE_TEXTURE_RESOLUTION
                    crop_y = source_y - top
                    mapped_y = origin_y + crop_y / layout.BASE_TEXTURE_RESOLUTION
                    self.assertAlmostEqual(mapped_x, x, places=6)
                    self.assertAlmostEqual(mapped_y, y, places=6)

                parent_top = layout.hud_bounds([
                    max(0, 2 * layout.CX - layout.WING_EFFECT_END - 11),
                    -layout.ARTWORK_TOP_PADDING,
                    layout.WING_EFFECT_END + 11,
                    layout.HUD_BOX_BOTTOM,
                ])[1]
                sprite_top = layout.hud_bounds([
                    left / layout.BASE_TEXTURE_RESOLUTION + origin_x,
                    top / layout.BASE_TEXTURE_RESOLUTION - layout.ARTWORK_TOP_PADDING,
                    right / layout.BASE_TEXTURE_RESOLUTION + origin_x,
                    bottom / layout.BASE_TEXTURE_RESOLUTION - layout.ARTWORK_TOP_PADDING,
                ])[1]
                self.assertLessEqual(parent_top, sprite_top)

                # The last five artwork pixels of each extended tail still
                # contain alpha before the authored fade reaches its endpoint.
                for x in (layout.WING_TEXTURE_END - 5.,
                          2 * layout.CX - (layout.WING_TEXTURE_END - 5.)):
                    sample_x = round((x + layout.WING_TEXTURE_PADDING)
                                     * layout.BASE_TEXTURE_RESOLUTION)
                    x0, x1 = max(left, sample_x - 2), min(right, sample_x + 3)
                    tail = prepared.crop((x0, top, x1, bottom)).getchannel('A')
                    self.assertGreater(tail.getextrema()[1], 0)

                results.append((extension, crop, actual, prepared.size))
        finally:
            layout.refresh_style(original)
            material.sync_layout()
            instruments.refresh_style()
            artwork.base_static.cache_clear()

        for extension, crop, bounds, size in results:
            print(f'{extension}px: source={size}, crop={crop}, alpha_bounds={bounds}')


if __name__ == '__main__':
    unittest.main()
