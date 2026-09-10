"""Bounded image decoding, metadata stripping and actual alpha validation."""

import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
MAX_PIXELS = 16_000_000
ALLOWED_MIME = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}


class InvalidAvatarImage(ValueError):
    pass


def _decode(raw: bytes, *, mime: str | None = None) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in ALLOWED_MIME.values():
                    raise InvalidAvatarImage("Gebruik een PNG-, JPEG- of WebP-afbeelding.")
                if mime is not None and source.format != ALLOWED_MIME.get(mime):
                    raise InvalidAvatarImage("Het bestandstype komt niet overeen met de afbeelding.")
                if source.width * source.height > MAX_PIXELS:
                    raise InvalidAvatarImage("De afbeelding mag maximaal 16 megapixels groot zijn.")
                if source.width < 32 or source.height < 32:
                    raise InvalidAvatarImage("De afbeelding moet minimaal 32 bij 32 pixels zijn.")
                if getattr(source, "n_frames", 1) != 1:
                    raise InvalidAvatarImage("Kies een stilstaande afbeelding.")
                source.load()
                return ImageOps.exif_transpose(source).convert("RGBA")
    except InvalidAvatarImage:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise InvalidAvatarImage("De afbeelding kan niet veilig worden gelezen.") from exc


def _png(image: Image.Image) -> bytes:
    # Copy pixels to a fresh object: do not preserve EXIF, text or ICC metadata.
    clean = Image.new("RGBA", image.size)
    clean.paste(image)
    output = BytesIO()
    clean.save(output, format="PNG", optimize=True)
    return output.getvalue()


def remove_alpha_noise(image: Image.Image) -> Image.Image:
    """Make near-transparent background pixels empty, preserving edge colors."""
    clean = image.copy()
    clean.putalpha(image.getchannel("A").point([0] * 16 + list(range(16, 256))))
    return clean


def normalize_upload(raw: bytes, mime: str) -> bytes:
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise InvalidAvatarImage("De foto mag maximaal 8 MB groot zijn.")
    image = _decode(raw, mime=mime)
    image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    return _png(image)


def validate_transparent_png(raw: bytes) -> bytes:
    if not raw or len(raw) > MAX_OUTPUT_BYTES or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise InvalidAvatarImage("Het model leverde geen geldige PNG-afbeelding.")
    image = _decode(raw, mime="image/png")
    histogram = image.getchannel("A").histogram()
    pixels = image.width * image.height
    # Merely writing RGBA with alpha=255 is not a transparent background.
    if sum(histogram[:16]) < pixels * 0.01 or sum(histogram[240:]) < pixels * 0.01:
        raise InvalidAvatarImage("Het model leverde geen zichtbaar poppetje met transparante achtergrond.")
    image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    return _png(image)
