import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

import png2decal


def triangle_area(triangles):
    return np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1
    ) / 2


class MeshTests(unittest.TestCase):
    def test_caps_cover_exactly_the_mask_area(self):
        mask = np.array(
            [
                [1, 1, 0, 1],
                [1, 1, 0, 1],
                [0, 1, 1, 1],
            ],
            dtype=bool,
        )
        triangles = png2decal.decal_triangles(mask, 0.5, 0.5, 0.05)
        flat = np.ptp(triangles[:, :, 1], axis=1) == 0
        cap_area = triangle_area(triangles[flat]).sum()

        self.assertAlmostEqual(cap_area, 2 * mask.sum() * 0.25)
        self.assertAlmostEqual(triangles[:, :, 1].max(), 0.05)

    def test_wall_area_matches_outline_length(self):
        mask = np.ones((2, 3), dtype=bool)
        triangles = png2decal.decal_triangles(mask, 1.0, 1.0, 0.1)
        walls = triangles[np.ptp(triangles[:, :, 1], axis=1) > 0]

        self.assertAlmostEqual(triangle_area(walls).sum(), 10 * 0.1)
        self.assertEqual(len(triangles), 4 + 8)


class RunTests(unittest.TestCase):
    def make_args(self, directory, path, **overrides):
        values = dict(
            input=str(path),
            width=15.6,
            scale=None,
            thickness=0.05,
            mask="alpha",
            threshold=128,
            max_pixels=512,
            name="decal",
            out=directory,
            author="Aioli",
        )
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_width_scales_the_cropped_pattern(self):
        image = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
        image.paste((255, 0, 0, 255), (10, 5, 30, 15))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decal.png"
            image.save(path)
            output = io.StringIO()

            with redirect_stdout(output):
                png2decal.run(self.make_args(directory, path))

            lines = Path(directory, "decal.dat").read_text(encoding="utf-8").splitlines()

        self.assertIn("15.60 x 0.05 x 7.80 mm", output.getvalue())
        self.assertIn("Dimensions: 2.00 x 0.006 x 1.00 studs", output.getvalue())
        self.assertTrue(all(line.startswith("3 16 ") for line in lines[5:]))

    def test_dark_mask_selects_dark_pixels(self):
        image = Image.new("RGB", (10, 10), "white")
        image.paste((0, 0, 0), (0, 0, 5, 10))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dark.png"
            image.save(path)

            mask, _cell = png2decal.read_mask(str(path), "dark", 128, 0)

        self.assertEqual(png2decal.crop_mask(mask).shape, (10, 5))

    def test_empty_mask_is_rejected(self):
        with self.assertRaises(ValueError):
            png2decal.crop_mask(np.zeros((3, 3), dtype=bool))


if __name__ == "__main__":
    unittest.main()
