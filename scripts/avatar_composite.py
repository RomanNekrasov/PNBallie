#!/usr/bin/env python3
"""CPU-only avatar experiments using Pillow; no model or cloud calls.

Extract only border-connected near-white pixels, then optionally place a manual
head crop behind the original body. This is a comparison tool, not a semantic
background remover. Inspect the light/dark contact sheet before choosing a mask.

Run with backend/.venv/bin/python scripts/avatar_composite.py --help.
Output files must be new; PNGs and their metadata sidecars are written as 0600.
All coordinates refer to the image after applying its EXIF orientation.
"""

import argparse
import json
import os
from collections import deque
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

DEFAULT_BODY = Path(__file__).resolve().parents[1] / "backend/app/assets/avatar-body.png"


def clean_rgba(image: Image.Image) -> Image.Image:
    """Copy pixels only, discarding EXIF and other embedded source metadata."""
    rgba = image.convert("RGBA")
    return Image.frombytes("RGBA", rgba.size, rgba.tobytes())


def load_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return clean_rgba(ImageOps.exif_transpose(image))


def alpha_metadata(image: Image.Image) -> dict:
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    pixels = image.width * image.height
    bbox = alpha.getbbox()
    border = {x for x in range(image.width)} | {
        (image.height - 1) * image.width + x for x in range(image.width)
    } | {y * image.width for y in range(image.height)} | {
        y * image.width + image.width - 1 for y in range(image.height)
    }
    values = alpha.tobytes()
    return {
        "size": list(image.size),
        "mode": image.mode,
        "transparent_pixels": histogram[0],
        "partial_alpha_pixels": sum(histogram[1:255]),
        "opaque_pixels": histogram[255],
        "transparent_fraction": round(histogram[0] / pixels, 6),
        "visible_bbox_xyxy": list(bbox) if bbox else None,
        "visible_bbox_normalized_xyxy": [round(bbox[0] / image.width, 6),
                                         round(bbox[1] / image.height, 6),
                                         round(bbox[2] / image.width, 6),
                                         round(bbox[3] / image.height, 6)] if bbox else None,
        "visible_border_pixels": sum(values[index] > 0 for index in border),
    }


def remove_border_white(image: Image.Image, threshold: int = 240) -> tuple[Image.Image, dict]:
    """Clear four-connected border pixels with every RGB channel >= threshold.

    Existing transparent pixels also connect the flood fill. White areas enclosed
    by non-white pixels are deliberately retained, including shirt and eye detail.
    No foreground colors are altered, feathered or guessed.
    """
    if not 1 <= threshold <= 255:
        raise ValueError("White threshold must be between 1 and 255")
    source = clean_rgba(image)
    width, height = source.size
    pixels = source.tobytes()
    eligible = bytearray(width * height)
    for index in range(width * height):
        offset = index * 4
        eligible[index] = pixels[offset + 3] == 0 or min(pixels[offset:offset + 3]) >= threshold
    background = bytearray(width * height)
    pending = deque()

    def visit(index):
        if eligible[index] and not background[index]:
            background[index] = 1
            pending.append(index)

    for x in range(width):
        visit(x)
        visit((height - 1) * width + x)
    for y in range(height):
        visit(y * width)
        visit(y * width + width - 1)
    while pending:
        index = pending.popleft()
        x, y = index % width, index // width
        if x:
            visit(index - 1)
        if x + 1 < width:
            visit(index + 1)
        if y:
            visit(index - width)
        if y + 1 < height:
            visit(index + width)
    output = bytearray(pixels)
    removed = 0
    for index, selected in enumerate(background):
        if selected:
            offset = index * 4
            removed += pixels[offset + 3] > 0
            output[offset:offset + 4] = b"\x00\x00\x00\x00"
    result = Image.frombytes("RGBA", source.size, bytes(output))
    metadata = alpha_metadata(result)
    caveats = [
        "Color flood fill has no subject awareness: near-white foreground touching the background can be removed.",
        "Enclosed white regions remain opaque, including background holes enclosed by the subject.",
        "Edges are not feathered or color-decontaminated; inspect light and dark backgrounds for white halos or lost detail.",
    ]
    if not removed:
        caveats.append("No visible border-connected near-white pixels were removed at this threshold.")
    if metadata["visible_border_pixels"]:
        caveats.append("Visible pixels still touch the image border; the subject may be cropped or the background may remain.")
    if metadata["visible_bbox_xyxy"] is None:
        caveats.append("The result is completely transparent; increase the threshold or use another extraction method.")
    metadata.update({
        "operation": "border_white_extraction",
        "white_threshold": threshold,
        "connectivity": 4,
        "removed_visible_pixels": removed,
        "retained_near_white_pixels": sum(eligible[index] and not background[index] and pixels[index * 4 + 3] > 0
                                          for index in range(width * height)),
        "caveats": caveats,
    })
    return result, metadata


def compose_head(head: Image.Image, body: Image.Image, *, source_box=None, box=None,
                 neck_anchor=None, head_width=None, padding=0, resample="lanczos") -> tuple[Image.Image, dict]:
    """Place a head behind the unchanged body; boxes are x,y,width,height.

    A destination box contains the head without stretching, centered horizontally
    and aligned at the bottom. A neck anchor places the crop's bottom center at
    that body-space point. These are explicit geometric choices, not face/neck
    detection. Every body pixel whose alpha is nonzero is copied verbatim last.
    """
    head, body = clean_rgba(head), clean_rgba(body)
    if padding < 0:
        raise ValueError("Padding cannot be negative")
    if source_box is None:
        source_bbox = head.getchannel("A").getbbox()
        if source_bbox is None:
            raise ValueError("The head image is completely transparent")
    else:
        x, y, width, height = source_box
        if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > head.width or y + height > head.height:
            raise ValueError("The source box must fit inside the head image")
        source_bbox = (x, y, x + width, y + height)
    crop = head.crop(source_bbox)
    if not crop.getchannel("A").getbbox():
        raise ValueError("The selected head crop is completely transparent")
    sampler = {"nearest": Image.Resampling.NEAREST, "lanczos": Image.Resampling.LANCZOS}[resample]
    if box is not None:
        if neck_anchor is not None or head_width is not None:
            raise ValueError("Choose a destination box or a neck anchor with head width")
        x, y, width, height = box
        if width <= 0 or height <= 0:
            raise ValueError("The destination box needs a positive width and height")
        fitted = ImageOps.contain(crop, (width, height), sampler)
        x += (width - fitted.width) // 2
        y += height - fitted.height
    else:
        if neck_anchor is None or head_width is None or head_width <= 0:
            raise ValueError("Provide a destination box or a neck anchor with a positive head width")
        height = max(1, round(crop.height * head_width / crop.width))
        fitted = crop.resize((head_width, height), sampler)
        x, y = neck_anchor[0] - head_width // 2, neck_anchor[1] - height
    left, top = min(0, x) - padding, min(0, y) - padding
    right, bottom = max(body.width, x + fitted.width) + padding, max(body.height, y + fitted.height) + padding
    canvas = Image.new("RGBA", (right - left, bottom - top))
    canvas.alpha_composite(fitted, (x - left, y - top))
    beneath_body = canvas.crop((-left, -top, body.width - left, body.height - top)).getchannel("A").tobytes()
    body_alpha = body.getchannel("A")
    body_values = body_alpha.tobytes()
    overlap = sum(0 < alpha < 255 and beneath_body[index] > 0 for index, alpha in enumerate(body_values))
    # A normal alpha-composite would alter partially transparent body-edge pixels.
    # The binary mask copies their original RGBA exactly, even where the head overlaps.
    canvas.paste(body, (-left, -top), body_alpha.point(lambda alpha: 255 if alpha else 0))
    metadata = alpha_metadata(canvas)
    metadata.update({
        "operation": "head_on_original_body",
        "source_bbox_xyxy": list(source_bbox),
        "head_box_in_body_xywh": [x, y, fitted.width, fitted.height],
        "body_origin_in_output_xy": [-left, -top],
        "head_origin_in_output_xy": [x - left, y - top],
        "neck_anchor_in_body_xy": list(neck_anchor) if neck_anchor is not None else None,
        "resample": resample,
        "padding": padding,
        "body_visible_pixels_copied_unchanged": sum(alpha > 0 for alpha in body_values),
        "translucent_body_pixels_overlapping_head": overlap,
        "caveats": [
            "Head crop and placement are manual; inspect neck joins and likeness.",
            "All nontransparent body pixels retain their original RGBA; translucent edges overwrite the head too.",
            "Canvas expansion prevents placement clipping but cannot restore content missing from either source.",
        ],
    })
    return canvas, metadata


def comparison_sheet(images: list[Image.Image], labels: list[str], cell_size=360) -> Image.Image:
    """One row per candidate, with the same scale on light and dark backgrounds."""
    if not images or len(images) != len(labels) or cell_size < 32:
        raise ValueError("Provide at least one image, one label per image and cell size >= 32")
    label_height = 30
    sheet = Image.new("RGBA", (cell_size * 2, (cell_size + label_height) * len(images)))
    draw = ImageDraw.Draw(sheet)
    for row, (image, label) in enumerate(zip(images, labels, strict=True)):
        fitted = ImageOps.contain(clean_rgba(image), (cell_size - 16, cell_size - 16), Image.Resampling.LANCZOS)
        for column, (background, foreground, suffix) in enumerate([
            ("#f4f4f4", "#171717", "light"), ("#1b1b1b", "#eeeeee", "dark"),
        ]):
            x, y = column * cell_size, row * (cell_size + label_height)
            draw.rectangle((x, y, x + cell_size - 1, y + cell_size + label_height - 1), fill=background)
            draw.text((x + 8, y + 8), f"{label} / {suffix}", fill=foreground)
            sheet.alpha_composite(fitted, (x + (cell_size - fitted.width) // 2,
                                          y + label_height + (cell_size - fitted.height) // 2))
    return sheet


def private_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)


def save_result(path: Path, image: Image.Image, metadata: dict):
    if path.suffix.lower() != ".png":
        raise ValueError("Output must have a .png extension")
    metadata_path = path.with_suffix(".metadata.json")
    if path.exists() or metadata_path.exists():
        raise FileExistsError("Choose new output names; existing images or metadata will not be overwritten")
    output = BytesIO()
    clean_rgba(image).save(output, format="PNG")
    private_bytes(path, output.getvalue())
    private_bytes(metadata_path, (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode())


def coordinates(length):
    def parse(value):
        try:
            values = tuple(int(component) for component in value.split(","))
        except ValueError as exc:
            raise argparse.ArgumentTypeError("Use comma-separated integers") from exc
        if len(values) != length:
            raise argparse.ArgumentTypeError(f"Expected {length} comma-separated integers")
        return values
    return parse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="Remove border-connected near-white background")
    extract.add_argument("--input", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--white-threshold", type=int, default=240)
    compose = commands.add_parser("compose", help="Place an explicit head crop behind the original body")
    compose.add_argument("--head", type=Path, required=True)
    compose.add_argument("--body", type=Path, default=DEFAULT_BODY)
    compose.add_argument("--output", type=Path, required=True)
    compose.add_argument("--source-box", type=coordinates(4), metavar="X,Y,W,H",
                         help="Source crop; defaults to the head image's visible bounding box")
    placement = compose.add_mutually_exclusive_group(required=True)
    placement.add_argument("--box", type=coordinates(4), metavar="X,Y,W,H",
                           help="Body-space box; preserve aspect ratio and align at bottom center")
    placement.add_argument("--neck-anchor", type=coordinates(2), metavar="X,Y",
                           help="Place the crop's bottom center here; requires --head-width")
    compose.add_argument("--head-width", type=int)
    compose.add_argument("--padding", type=int, default=0,
                         help="Extra border pixels; out-of-bounds placement is always padded automatically")
    compose.add_argument("--resample", choices=["nearest", "lanczos"], default="lanczos")
    compare = commands.add_parser("compare", help="Create a light/dark comparison sheet")
    compare.add_argument("--input", type=Path, action="append", required=True)
    compare.add_argument("--label", action="append", help="Repeat once per input, in the same order")
    compare.add_argument("--output", type=Path, required=True)
    compare.add_argument("--cell-size", type=int, default=360)
    args = parser.parse_args()
    try:
        if args.command == "extract":
            image, metadata = remove_border_white(load_image(args.input), args.white_threshold)
        elif args.command == "compose":
            image, metadata = compose_head(load_image(args.head), load_image(args.body),
                                           source_box=args.source_box, box=args.box,
                                           neck_anchor=args.neck_anchor, head_width=args.head_width,
                                           padding=args.padding, resample=args.resample)
        else:
            labels = args.label or [path.stem for path in args.input]
            image = comparison_sheet([load_image(path) for path in args.input], labels, args.cell_size)
            metadata = {**alpha_metadata(image), "operation": "light_dark_comparison", "labels": labels}
        save_result(args.output, image, metadata)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
