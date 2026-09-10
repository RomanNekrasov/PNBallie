"""Explicit local GPU acceptance check; never calls OpenAI or downloads weights."""

import argparse
import json
import time
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.avatar_images import (
    ALLOWED_MIME,
    MAX_UPLOAD_BYTES,
    normalize_upload,
    validate_transparent_png,
)
from app.avatar_providers import AvatarSettings
from app.avatar_service import QwenRuntime


def main():
    parser = argparse.ArgumentParser(description="Generate one local Qwen avatar and inspect its alpha channel")
    parser.add_argument("portrait", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.portrait.stat().st_size > MAX_UPLOAD_BYTES:
        parser.error("The portrait exceeds the 8 MiB upload limit")
    if args.output.exists():
        parser.error("Choose a new output path; the smoke check will not overwrite a file")
    raw = args.portrait.read_bytes()
    with Image.open(BytesIO(raw)) as image:
        mime = next((mime for mime, fmt in ALLOWED_MIME.items() if fmt == image.format), None)
    if mime is None:
        parser.error("Use a PNG, JPEG or WebP portrait")
    source = normalize_upload(raw, mime)
    reference = normalize_upload(AvatarSettings.from_env().reference_path.read_bytes(), "image/png")
    started = time.monotonic()
    result = validate_transparent_png(QwenRuntime().generate(source, reference))
    args.output.write_bytes(result)
    with Image.open(BytesIO(result)) as image:
        histogram = image.getchannel("A").histogram()
        print(json.dumps({"mode": image.mode, "format": image.format,
                          "width": image.width, "height": image.height,
                          "transparent_fraction": round(sum(histogram[:16]) / (image.width * image.height), 4),
                          "seconds": round(time.monotonic() - started, 1)}, indent=2))


if __name__ == "__main__":
    main()
