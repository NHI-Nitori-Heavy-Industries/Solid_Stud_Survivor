import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import obj2stud


class ReadObjTests(unittest.TestCase):
    def test_preserves_hashes_in_object_names_and_ignores_subgroups(self):
        source = """# Model comment
o vehicle#track_r_0 # trailing comment
v 0 0 0
v 1 0 0
v 0 1 0
f 1 2 3
g vehicle#track_r_0_0
v 2 0 0
v 3 0 0
v 2 1 0
f 4 5 6
o vehicle#track_l_1
f 1 3 2
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "objects.obj"
            path.write_text(source, encoding="utf-8")

            _vertices, groups = obj2stud.read_obj(str(path))

        self.assertEqual(
            [(name, len(faces)) for name, faces in groups],
            [("vehicle#track_r_0", 2), ("vehicle#track_l_1", 1)],
        )

    def test_uses_groups_when_obj_has_no_object_records(self):
        source = """g first#group
v 0 0 0
v 1 0 0
v 0 1 0
f 1 2 3
g second
f 1 3 2
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.obj"
            path.write_text(source, encoding="utf-8")

            _vertices, groups = obj2stud.read_obj(str(path))

        self.assertEqual(
            [(name, len(faces)) for name, faces in groups],
            [("first#group", 1), ("second", 1)],
        )

    def test_reports_missing_material_libraries_and_material_assignments(self):
        source = """mtllib colors.mtl
usemtl red
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "materials.obj"
            path.write_text(source, encoding="utf-8")

            has_assignments, missing = obj2stud.obj_material_info(str(path))

        self.assertTrue(has_assignments)
        self.assertEqual(missing, ["colors.mtl"])

    def test_small_piece_filter_is_disabled_by_default(self):
        args = obj2stud.build_parser().parse_args(["model.obj", "--width", "10"])

        self.assertEqual(args.min_piece, 0.0)

    def test_stud_width_converts_to_millimeters(self):
        self.assertEqual(obj2stud.studs_to_mm("1"), 7.8)
        self.assertEqual(obj2stud.studs_to_mm("2.5"), 19.5)


class WritePartTests(unittest.TestCase):
    def test_writes_a_plain_dat_header_and_separate_sidecars(self):
        points = np.asarray(
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            dtype=np.float64,
        )
        faces = np.asarray([(0, 1, 2)], dtype=np.int64)
        with tempfile.TemporaryDirectory() as directory:
            parts = os.path.join(directory, "parts")
            collider = os.path.join(directory, "collider")
            connectivity = os.path.join(directory, "connectivity")

            obj2stud.write_part(
                parts,
                "triangle",
                points,
                faces,
                "Aioli",
                collider_dir=collider,
                connectivity_dir=connectivity,
            )

            dat_lines = Path(parts, "triangle.dat").read_text(encoding="utf-8").splitlines()
            self.assertEqual(dat_lines[0], "0 triangle")
            self.assertTrue(any(line.startswith("3 16 ") for line in dat_lines))
            self.assertTrue(Path(collider, "triangle.col").is_file())
            self.assertTrue(Path(connectivity, "triangle.conn").is_file())

    def test_conversion_reports_dimensions_in_studs(self):
        source = """o triangle
v 0 0 0
v 1 0 0
v 0 1 0
f 1 2 3
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "triangle.obj"
            path.write_text(source, encoding="utf-8")
            args = SimpleNamespace(
                input=str(path),
                width=7.8,
                scale=None,
                faces=None,
                min_piece=0,
                drop=[],
                zup=False,
                name="triangle",
                out=directory,
                author="Aioli",
                weld_tol=1e-5,
                list=False,
            )
            output = io.StringIO()

            with redirect_stdout(output):
                obj2stud.run(args)

        self.assertIn("Dimensions: 1.00 x 1.00 x 0.00 studs", output.getvalue())


if __name__ == "__main__":
    unittest.main()
