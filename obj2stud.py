#!/usr/bin/env python3
"""Convert OBJ/STL meshes to Stud.io custom-part files (.dat/.col/.conn).

Requirements:
    Python 3.8+, numpy

Optional mesh reduction:
    pip install fast-simplification

Examples:
    python obj2stud.py type74.obj --width 85.8
    python obj2stud.py type74.obj --width 85.8 --faces 20000 --name type74 --out parts
    python obj2stud.py tank.stl --scale 0.0259 --min-piece 0
    python obj2stud.py type74.obj --list

Input is assumed to use Y-up coordinates. Pass --zup for Z-up models.
The output is centered in X/Z, rests at Y=0, and uses LDraw units
(1 LDU = 0.4 mm) with the LDraw -Y-up orientation.
"""

import argparse
import fnmatch
import os
import struct
import sys

import numpy as np

LDU_MM = 0.4


def read_obj(path):
    """Return vertices and named triangle groups from an OBJ file."""
    vertices = []
    groups = {}
    order = []
    current_group = "default"

    with open(path, "r", encoding="utf-8", errors="replace") as source:
        for line_number, raw_line in enumerate(source, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            fields = line.split()
            command = fields[0]

            if command == "v":
                if len(fields) < 4:
                    raise ValueError(f"OBJ line {line_number}: vertex needs at least 3 coordinates")
                try:
                    vertices.append(tuple(float(value) for value in fields[1:4]))
                except ValueError as exc:
                    raise ValueError(f"OBJ line {line_number}: invalid vertex coordinates") from exc
            elif command in ("o", "g"):
                current_group = " ".join(fields[1:]) or "default"
            elif command == "f":
                if len(fields) < 4:
                    raise ValueError(f"OBJ line {line_number}: face needs at least 3 vertices")
                face_indices = []
                for token in fields[1:]:
                    try:
                        index = int(token.split("/", 1)[0])
                    except ValueError as exc:
                        raise ValueError(f"OBJ line {line_number}: invalid face index {token!r}") from exc
                    if index == 0:
                        raise ValueError(f"OBJ line {line_number}: OBJ vertex indices cannot be zero")
                    resolved = index - 1 if index > 0 else len(vertices) + index
                    if resolved < 0 or resolved >= len(vertices):
                        raise ValueError(f"OBJ line {line_number}: vertex index {index} is out of range")
                    face_indices.append(resolved)

                if current_group not in groups:
                    groups[current_group] = []
                    order.append(current_group)
                for index in range(1, len(face_indices) - 1):
                    groups[current_group].append(
                        (face_indices[0], face_indices[index], face_indices[index + 1])
                    )

    vertex_array = np.asarray(vertices, dtype=np.float64).reshape((-1, 3))
    if not np.isfinite(vertex_array).all():
        raise ValueError("OBJ contains non-finite vertex coordinates")
    faces = [
        (name, np.asarray(groups[name], dtype=np.int64).reshape((-1, 3)))
        for name in order
        if groups[name]
    ]
    return vertex_array, faces


def read_stl(path):
    """Return vertices and one triangle group from an ASCII or binary STL."""
    with open(path, "rb") as source:
        data = source.read()

    triangle_count = struct.unpack("<I", data[80:84])[0] if len(data) >= 84 else 0
    if len(data) == 84 + triangle_count * 50:
        records = np.frombuffer(
            data[84:],
            dtype=[("normal", "<f4", 3), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")],
            count=triangle_count,
        )
        triangles = records["vertices"].astype(np.float64)
    else:
        points = [
            tuple(map(float, line.split()[1:4]))
            for line in data.decode("ascii", "ignore").splitlines()
            if line.strip().lower().startswith("vertex ")
        ]
        if len(points) % 3:
            raise ValueError("ASCII STL has an incomplete triangle")
        triangles = np.asarray(points, dtype=np.float64).reshape((-1, 3, 3))

    vertices = triangles.reshape((-1, 3))
    if not np.isfinite(vertices).all():
        raise ValueError("STL contains non-finite vertex coordinates")
    faces = np.arange(len(vertices), dtype=np.int64).reshape((-1, 3))
    name = os.path.splitext(os.path.basename(path))[0]
    return vertices, [(name, faces)] if len(faces) else []


def weld(vertices, faces, tolerance):
    """Merge near-identical used vertices and discard degenerate/duplicate faces."""
    used = np.unique(faces)
    points = vertices[used]
    keys = np.round(points / tolerance).astype(np.int64)
    _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    remap = np.zeros(vertices.shape[0], dtype=np.int64)
    remap[used] = inverse
    welded_faces = remap[faces]
    welded_points = points[first]

    valid = (
        (welded_faces[:, 0] != welded_faces[:, 1])
        & (welded_faces[:, 1] != welded_faces[:, 2])
        & (welded_faces[:, 0] != welded_faces[:, 2])
    )
    welded_faces = welded_faces[valid]
    if len(welded_faces):
        _, unique_indices = np.unique(np.sort(welded_faces, axis=1), axis=0, return_index=True)
        welded_faces = welded_faces[np.sort(unique_indices)]
    return welded_points, welded_faces


def components(vertex_count, faces):
    """Return connected-component labels using a NumPy union-find implementation."""
    parent = np.arange(vertex_count, dtype=np.int64)
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]]))
    while True:
        first = parent[edges[:, 0]]
        second = parent[edges[:, 1]]
        smaller = np.minimum(first, second)
        changed = False
        for side in (first, second):
            mask = smaller < parent[side]
            if mask.any():
                np.minimum.at(parent, side[mask], smaller[mask])
                changed = True
        while True:
            compressed = parent[parent]
            if np.array_equal(compressed, parent):
                break
            parent = compressed
        if not changed:
            break
    _, labels = np.unique(parent, return_inverse=True)
    return labels


def drop_small_pieces(points, faces, minimum_size):
    """Remove connected mesh pieces whose largest bounding-box dimension is too small."""
    if minimum_size <= 0 or len(faces) == 0:
        return faces
    labels = components(len(points), faces)
    component_count = labels.max() + 1
    minimum = np.full((component_count, 3), np.inf)
    maximum = np.full((component_count, 3), -np.inf)
    np.minimum.at(minimum, labels, points)
    np.maximum.at(maximum, labels, points)
    sizes = (maximum - minimum).max(axis=1)
    return faces[sizes[labels[faces[:, 0]]] >= minimum_size]


def compact(points, faces):
    used, inverse = np.unique(faces, return_inverse=True)
    return points[used], inverse.reshape(faces.shape)


def allocate(parts, budget):
    """Distribute a face budget by bounding-box area, respecting each part's face cap."""
    part_count = len(parts)
    if budget < part_count:
        raise ValueError(
            f"--faces must be at least the number of output objects ({part_count})"
        )

    def surface_weight(part):
        size = part["points"].max(axis=0) - part["points"].min(axis=0)
        area = size[0] * size[1] + size[1] * size[2] + size[0] * size[2]
        return max(area, 1e-12) ** 0.75

    weights = np.asarray([surface_weight(part) for part in parts], dtype=np.float64)
    capacities = np.asarray([len(part["faces"]) for part in parts], dtype=np.int64)
    allocated = np.ones(part_count, dtype=np.int64)
    remaining = budget - part_count

    while remaining > 0:
        available = allocated < capacities
        if not available.any():
            break
        shares = np.zeros(part_count, dtype=np.float64)
        shares[available] = remaining * weights[available] / weights[available].sum()
        additions = np.floor(shares).astype(np.int64)
        additions = np.minimum(additions, capacities - allocated)
        added = int(additions.sum())
        if added == 0:
            candidates = np.flatnonzero(available)
            selected = candidates[np.argmax(shares[candidates])]
            additions[selected] = 1
            added = 1
        allocated += additions
        remaining -= added
    return allocated


def decimate(points, faces, target):
    if target >= len(faces):
        return points, faces
    try:
        import fast_simplification
    except ImportError as exc:
        raise RuntimeError(
            "Mesh reduction requires fast-simplification: "
            "pip install fast-simplification"
        ) from exc
    reduction = 1.0 - target / len(faces)
    reduced_points, reduced_faces = fast_simplification.simplify(
        points.astype(np.float32),
        faces.astype(np.int32),
        target_reduction=reduction,
    )
    return np.asarray(reduced_points, dtype=np.float64), np.asarray(reduced_faces, dtype=np.int64)


def write_part(output_dir, name, ldraw_points, faces, author, collider_dir=None, connectivity_dir=None):
    collider_dir = collider_dir or output_dir
    connectivity_dir = connectivity_dir or output_dir
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(collider_dir, exist_ok=True)
    os.makedirs(connectivity_dir, exist_ok=True)
    filename = name + ".dat"
    dat_path = os.path.join(output_dir, filename)
    with open(dat_path, "w", encoding="utf-8", newline="\r\n") as output:
        output.write(
            f"0 FILE {filename}\n"
            f"0 {name}\n"
            f"0 Name:  {filename}\n"
            f"0 Author:  {author}\n"
            f"0 BL_Item_No {name}\n"
            "0 BFC NOCERTIFY\n"
        )
        for first, second, third in ldraw_points[faces]:
            output.write(
                "3 16 %.3f %.3f %.3f %.3f %.3f %.3f %.3f %.3f %.3f\n"
                % (*first, *second, *third)
            )
    open(os.path.join(collider_dir, name + ".col"), "wb").close()
    open(os.path.join(connectivity_dir, name + ".conn"), "wb").close()


def valid_positive_float(value):
    number = float(value)
    if not np.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return number


def valid_nonnegative_float(value):
    number = float(value)
    if not np.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than or equal to zero")
    return number


def build_parser():
    parser = argparse.ArgumentParser(
        description="Convert OBJ/STL models to Stud.io custom-part files (.dat/.col/.conn)"
    )
    parser.add_argument("input", help="input model (.obj or .stl)")
    size_group = parser.add_mutually_exclusive_group()
    size_group.add_argument("--width", type=valid_positive_float, help="finished X width in mm")
    size_group.add_argument("--scale", type=valid_positive_float, help="model-unit to mm multiplier")
    parser.add_argument("--name", help="output part name (defaults to input filename)")
    parser.add_argument("--out", default=".", help="output directory (default: current directory)")
    parser.add_argument("--faces", type=int, help="target total face count; omit to keep all faces")
    parser.add_argument(
        "--min-piece",
        type=valid_nonnegative_float,
        default=2.0,
        help="remove disconnected pieces smaller than this size in mm (0 disables; default: 2)",
    )
    parser.add_argument(
        "--drop",
        nargs="*",
        default=["*antenna*"],
        help="case-insensitive object-name patterns to omit (default: *antenna*)",
    )
    parser.add_argument("--zup", action="store_true", help="input model uses Z-up coordinates")
    parser.add_argument("--author", default="", help="author field written to the .dat file")
    parser.add_argument(
        "--weld-tol",
        type=valid_positive_float,
        default=1e-5,
        help="vertex weld tolerance in model units (default: 1e-5)",
    )
    parser.add_argument("--list", action="store_true", help="list object names and face counts, then exit")
    return parser


def validate_part_name(name):
    invalid_characters = '<>:"/\\|?*'
    if (
        not name
        or name in (".", "..")
        or any(character in invalid_characters or ord(character) < 32 for character in name)
        or name.endswith((" ", "."))
    ):
        raise ValueError("part name must be a valid filename without path separators")


def run(args):
    extension = os.path.splitext(args.input)[1].lower()
    if extension not in (".obj", ".stl"):
        raise ValueError("input file must have an .obj or .stl extension")
    if not os.path.isfile(args.input):
        raise ValueError(f"input file does not exist: {args.input}")
    if args.faces is not None and args.faces <= 0:
        raise ValueError("--faces must be greater than zero")
    if not args.list and args.width is None and args.scale is None:
        raise ValueError("one of --width or --scale is required unless --list is used")

    vertices, groups = read_stl(args.input) if extension == ".stl" else read_obj(args.input)
    if args.zup:
        vertices = vertices[:, [0, 2, 1]] * np.array([1, 1, -1])

    if args.list:
        for name, faces in groups:
            print(f"{len(faces):8d}  {name}")
        print(f"{sum(len(faces) for _, faces in groups):8d}  total ({len(groups)} objects)")
        return
    if not groups:
        raise ValueError("input model contains no triangles")

    patterns = [pattern.lower() for pattern in (args.drop or [])]
    included_objects = getattr(args, "include_objects", None)
    kept = [
        (name, faces)
        for name, faces in groups
        if (
            name in included_objects
            if included_objects is not None
            else not any(fnmatch.fnmatch(name.lower(), pattern) for pattern in patterns)
        )
    ]
    dropped = [name for name, _ in groups if all(name != kept_name for kept_name, _ in kept)]
    if not kept:
        raise ValueError("all objects were removed by --drop; adjust the patterns")

    used_vertices = np.unique(np.concatenate([faces.ravel() for _, faces in kept]))
    retained_width = vertices[used_vertices, 0].max() - vertices[used_vertices, 0].min()
    if args.width is not None and retained_width <= 0:
        raise ValueError("cannot calculate --width scaling because the retained model has zero X width")
    scale = args.scale if args.scale is not None else args.width / retained_width

    parts = []
    removed_small_faces = 0
    for name, faces in kept:
        points, cleaned_faces = weld(vertices, faces, args.weld_tol)
        previous_face_count = len(cleaned_faces)
        cleaned_faces = drop_small_pieces(points, cleaned_faces, args.min_piece / scale)
        removed_small_faces += previous_face_count - len(cleaned_faces)
        if len(cleaned_faces):
            points, cleaned_faces = compact(points, cleaned_faces)
            parts.append({"name": name, "points": points, "faces": cleaned_faces})
    if not parts:
        raise ValueError("no faces remain after removing degenerate faces and small pieces")

    if args.faces is not None:
        targets = allocate(parts, args.faces)
        for part, target in zip(parts, targets):
            part["points"], part["faces"] = decimate(
                part["points"], part["faces"], int(target)
            )

    point_sets = []
    face_sets = []
    offset = 0
    for part in parts:
        point_sets.append(part["points"])
        face_sets.append(part["faces"] + offset)
        offset += len(part["points"])
    points = np.vstack(point_sets)
    faces = np.vstack(face_sets)

    minimum = points.min(axis=0)
    maximum = points.max(axis=0)
    millimeter_points = (
        points - np.array([(minimum[0] + maximum[0]) / 2, minimum[1], (minimum[2] + maximum[2]) / 2])
    ) * scale
    ldraw_points = millimeter_points / LDU_MM
    ldraw_points[:, 1] *= -1
    ldraw_points[:, 2] *= -1

    name = args.name or os.path.splitext(os.path.basename(args.input))[0]
    validate_part_name(name)
    parts_dir = getattr(args, "parts_dir", args.out)
    collider_dir = getattr(args, "collider_dir", args.out)
    connectivity_dir = getattr(args, "connectivity_dir", args.out)
    write_part(
        parts_dir,
        name,
        ldraw_points,
        faces,
        args.author,
        collider_dir=collider_dir,
        connectivity_dir=connectivity_dir,
    )

    size = millimeter_points.max(axis=0) - millimeter_points.min(axis=0)
    print(f"Scale: {scale:.6g} (approximately 1:{1000 / scale:.1f} if source units are meters)")
    if dropped:
        print(f"Removed {len(dropped)} object(s): {', '.join(dropped)}")
    if removed_small_faces:
        print(f"Removed {removed_small_faces} faces from pieces smaller than {args.min_piece} mm")
    print(
        f"Exported {len(faces)} faces; size "
        f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm (width x height x length)"
    )
    print(f"Files: {os.path.join(parts_dir, name)}.dat")
    print(f"       {os.path.join(collider_dir, name)}.col")
    print(f"       {os.path.join(connectivity_dir, name)}.conn")


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
