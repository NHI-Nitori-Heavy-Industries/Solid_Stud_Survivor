#!/usr/bin/env python3
"""Convert a PNG image into a single-colour Stud.io decal part (.dat/.col/.conn).

Requirements:
    Python 3.9+, numpy, Pillow

Examples:
    python png2decal.py logo.png --width 15.6
    python png2decal.py logo.png --width 15.6 --thickness 0.05 --mask dark
    python png2decal.py logo.png --scale 0.05

Opaque pixels (or dark pixels with --mask dark) become a thin slab lying flat
in the LDraw X/Z plane. The slab is centered in X/Z, rests at Y=0, and the top
edge of the image points to the back of the part. All triangles use LDraw
color 16, so the decal takes the part color chosen in Stud.io.
"""

import argparse
import os

import numpy as np

import obj2stud

DEFAULT_THICKNESS_MM = 0.05


def runs(flags):
    """Return (start, end) index pairs of consecutive True values."""
    padded = np.zeros(len(flags) + 2, dtype=np.int8)
    padded[1:-1] = flags
    changes = np.flatnonzero(np.diff(padded))
    return list(zip(changes[0::2].tolist(), changes[1::2].tolist()))


def read_mask(path, mode, threshold, max_pixels):
    """Return the decal mask and the source-pixel size of one mask cell (x, y)."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("PNG conversion requires Pillow: pip install Pillow") from exc

    with Image.open(path) as image:
        image.load()
        source_size = image.size
        if mode == "alpha":
            channel = image.convert("RGBA").getchannel("A")
        else:
            luminance, alpha = (np.asarray(band, dtype=np.float64) for band in image.convert("LA").split())
            coverage = (255.0 - luminance) * alpha / 255.0
            channel = Image.fromarray(np.round(coverage).astype(np.uint8))

    if max_pixels and max(channel.size) > max_pixels:
        ratio = max_pixels / max(channel.size)
        channel = channel.resize(
            (max(1, round(channel.size[0] * ratio)), max(1, round(channel.size[1] * ratio))),
            Image.BOX,
        )
    cell = (source_size[0] / channel.size[0], source_size[1] / channel.size[1])
    return np.asarray(channel) >= threshold, cell


def crop_mask(mask):
    rows = np.flatnonzero(mask.any(axis=1))
    columns = np.flatnonzero(mask.any(axis=0))
    if not len(rows):
        raise ValueError("no pixels were selected; check --mask and --threshold")
    return mask[rows[0]:rows[-1] + 1, columns[0]:columns[-1] + 1]


def mask_rectangles(mask):
    """Cover the mask with (x0, y0, x1, y1) rectangles by stacking identical row runs."""
    rectangles = []
    open_runs = {}
    for row_index in range(mask.shape[0] + 1):
        row_runs = set(runs(mask[row_index])) if row_index < mask.shape[0] else set()
        for run in [run for run in open_runs if run not in row_runs]:
            rectangles.append((run[0], open_runs.pop(run), run[1], row_index))
        for run in row_runs:
            open_runs.setdefault(run, row_index)
    return np.asarray(rectangles, dtype=np.float64).reshape((-1, 4))


def outline_segments(mask):
    """Return merged outline segments (x0, y0, x1, y1) along pixel edges."""
    padded = np.pad(mask, 1).astype(np.int8)
    segments = []
    horizontal = np.diff(padded, axis=0)[:, 1:-1]
    for y, line in enumerate(horizontal):
        for side in (-1, 1):
            segments.extend((x0, y, x1, y) for x0, x1 in runs(line == side))
    vertical = np.diff(padded, axis=1)[1:-1, :]
    for x, column in enumerate(vertical.T):
        for side in (-1, 1):
            segments.extend((x, y0, x, y1) for y0, y1 in runs(column == side))
    return np.asarray(segments, dtype=np.float64).reshape((-1, 4))


def decal_triangles(mask, cell_x, cell_y, thickness):
    """Build slab triangles in millimeters (X right, Y up, image top toward -Z)."""
    height, width = mask.shape
    offset = np.array([width * cell_x / 2, height * cell_y / 2])

    def plane(x, y):
        return np.stack((x * cell_x - offset[0], y * cell_y - offset[1]), axis=-1)

    rectangles = mask_rectangles(mask)
    x0, y0, x1, y1 = rectangles.T
    corners = np.stack((plane(x0, y0), plane(x1, y0), plane(x1, y1), plane(x0, y1)), axis=1)
    caps = []
    for level in (0.0, thickness):
        lifted = np.insert(corners, 1, level, axis=2)
        caps.append(lifted[:, [0, 1, 2]])
        caps.append(lifted[:, [0, 2, 3]])

    segments = outline_segments(mask)
    start = plane(segments[:, 0], segments[:, 1])
    end = plane(segments[:, 2], segments[:, 3])
    wall = np.stack(
        (
            np.insert(start, 1, 0.0, axis=1),
            np.insert(end, 1, 0.0, axis=1),
            np.insert(end, 1, thickness, axis=1),
            np.insert(start, 1, thickness, axis=1),
        ),
        axis=1,
    )
    walls = [wall[:, [0, 1, 2]], wall[:, [0, 2, 3]]]
    return np.concatenate(caps + walls)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Convert a PNG image to a single-colour Stud.io decal part (.dat/.col/.conn)"
    )
    parser.add_argument("input", help="input image (.png)")
    size_group = parser.add_mutually_exclusive_group()
    size_group.add_argument(
        "--width", type=obj2stud.valid_positive_float, help="finished X width in mm"
    )
    size_group.add_argument(
        "--scale", type=obj2stud.valid_positive_float, help="mm per source image pixel"
    )
    parser.add_argument(
        "--thickness",
        type=obj2stud.valid_positive_float,
        default=DEFAULT_THICKNESS_MM,
        help=f"decal thickness in mm (default: {DEFAULT_THICKNESS_MM:g})",
    )
    parser.add_argument(
        "--mask",
        choices=("alpha", "dark"),
        default="alpha",
        help="pixels forming the decal: opaque (alpha) or dark on a light background (default: alpha)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=128,
        help="0-255 alpha/darkness cutoff for decal pixels (default: 128)",
    )
    parser.add_argument(
        "--max-pixels",
        type=int,
        default=512,
        help="downsample so the longest side is at most this many pixels; 0 keeps the original (default: 512)",
    )
    parser.add_argument("--name", help="output part name (defaults to input filename)")
    parser.add_argument("--out", default=".", help="output directory (default: current directory)")
    parser.add_argument("--author", default="", help="author field written to the .dat file")
    return parser


def run(args):
    if os.path.splitext(args.input)[1].lower() != ".png":
        raise ValueError("input file must have a .png extension")
    if not os.path.isfile(args.input):
        raise ValueError(f"input file does not exist: {args.input}")
    if args.width is None and args.scale is None:
        raise ValueError("one of --width or --scale is required")
    if not 1 <= args.threshold <= 255:
        raise ValueError("--threshold must be between 1 and 255")
    if args.max_pixels < 0:
        raise ValueError("--max-pixels must be 0 or greater")

    mask, (source_x, source_y) = read_mask(args.input, args.mask, args.threshold, args.max_pixels)
    if args.mask == "alpha" and mask.all():
        print(
            "Warning: the image has no transparent pixels, so the decal is a full rectangle; "
            "use the dark-pixel mask for images on a light background."
        )
    mask = crop_mask(mask)

    if args.width is not None:
        cell_x = args.width / mask.shape[1]
        cell_y = cell_x * source_y / source_x
    else:
        cell_x = args.scale * source_x
        cell_y = args.scale * source_y

    triangles = decal_triangles(mask, cell_x, cell_y, args.thickness)
    ldraw_points = triangles.reshape((-1, 3)) / obj2stud.LDU_MM
    ldraw_points[:, 1] *= -1
    ldraw_points[:, 2] *= -1
    faces = np.arange(len(ldraw_points), dtype=np.int64).reshape((-1, 3))

    name = args.name or os.path.splitext(os.path.basename(args.input))[0]
    obj2stud.validate_part_name(name)
    parts_dir = getattr(args, "parts_dir", args.out)
    collider_dir = getattr(args, "collider_dir", args.out)
    connectivity_dir = getattr(args, "connectivity_dir", args.out)
    obj2stud.write_part(
        parts_dir,
        name,
        ldraw_points,
        faces,
        args.author,
        collider_dir=collider_dir,
        connectivity_dir=connectivity_dir,
    )

    size = np.array([mask.shape[1] * cell_x, args.thickness, mask.shape[0] * cell_y])
    size_studs = size / obj2stud.STUD_MM
    print(f"Mask: {mask.shape[1]} x {mask.shape[0]} pixels; pixel size {cell_x:.4g} x {cell_y:.4g} mm")
    print(
        f"Exported {len(faces)} faces; size "
        f"{size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} mm (width x height x length)"
    )
    print(
        f"Dimensions: {size_studs[0]:.2f} x {size_studs[1]:.3f} x "
        f"{size_studs[2]:.2f} studs (1 stud = {obj2stud.STUD_MM:g} mm)"
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
