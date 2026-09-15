"""Pixel portrait style and bounded CPU composition with the supplied player body."""

from collections import deque
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from app.avatar_images import InvalidAvatarImage, validate_transparent_png

PIXEL_STYLE = "pixel-v1"
LEGACY_STYLE = "legacy"
LOCAL_STYLES = {LEGACY_STYLE, PIXEL_STYLE}
TEMPLATE_PATH = Path(__file__).parent / "assets" / "avatar-player-template.png"
PIXEL_PROMPT = (
    "Edit image 1, keeping the same recognizable person and their expression. "
    "Preserve natural facial proportions and all visible features: detailed eyes "
    "with irises and eyelids, eyebrows, nose, lips and jaw. Preserve the person's "
    "own hairstyle, hairline, hair colour and facial hair if present. "
    "Render a detailed modern pixel-art portrait using fine pixel clusters, subtle "
    "stepped edges and many shades. Preserve facial anatomy, readable eyes and "
    "specific likeness with high facial detail. Use a 32-bit game portrait style, "
    "not coarse 8-bit blocks. Keep small pixel details in hair, eyelids and lips. "
    "Show only the complete head and a short neck, without clothing or shoulders. "
    "Keep all hair and both ears, centered with generous empty margin. Pure white background."
)
PIXEL_NEGATIVE_PROMPT = (
    "missing eyes, blank face, flat icon, vector avatar, caricature, enlarged eyes, "
    "changed expression, cropped hair, photo collage, scenery, text, watermark, checkerboard"
)


def pixel_template() -> Image.Image:
    with Image.open(TEMPLATE_PATH) as source:
        source.load()
        if source.mode != "RGBA" or source.size != (1380, 1140):
            raise InvalidAvatarImage("Het spelerssjabloon is niet beschikbaar.")
        return Image.frombytes("RGBA", source.size, source.tobytes())


def on_white(image: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", image.size, "white")
    canvas.alpha_composite(image.convert("RGBA"))
    return canvas.convert("RGB")


def extract_pixel_head(image: Image.Image) -> Image.Image:
    """Remove border-connected near-white, retaining enclosed eye/highlight detail."""
    width, height = image.size
    if not (64 <= width <= 1536 and 64 <= height <= 1536):
        raise InvalidAvatarImage("Het model gaf geen bruikbaar portret terug.")
    source = image.convert("RGBA")
    pixels = source.tobytes()
    eligible = bytearray(width * height)
    for index in range(width * height):
        offset = index * 4
        eligible[index] = pixels[offset + 3] == 0 or min(pixels[offset:offset + 3]) >= 240
    background = bytearray(width * height)
    pending = deque()

    def visit(index: int) -> None:
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
    for index, selected in enumerate(background):
        if selected:
            output[index * 4:index * 4 + 4] = bytes(4)
    head = Image.frombytes("RGBA", source.size, bytes(output))
    bbox = head.getchannel("A").getbbox()
    # An opaque/full-frame result must not become a "valid" avatar merely
    # because the transparent body below it contributes empty canvas pixels.
    if (bbox is None or sum(background) < width * height * 0.10
            or width * height - sum(background) < width * height * 0.02):
        raise InvalidAvatarImage("Geen vrijstaand hoofd gevonden in het portret.")
    left, top, right, bottom = bbox
    if left == 0 or top == 0 or right == width or not 0.6 <= (bottom - top) / (right - left) <= 2.5:
        raise InvalidAvatarImage("Het portret is afgesneden of heeft onbruikbare verhoudingen.")
    return head.crop(bbox)


def place_pixel_head(head: Image.Image, body: Image.Image) -> Image.Image:
    """Use the inspected C placement, preserving every visible template pixel."""
    if body.size != (1380, 1140) or body.mode != "RGBA":
        raise InvalidAvatarImage("Het spelerssjabloon heeft onjuiste afmetingen.")
    if head.width < 1 or not 0.6 <= head.height / head.width <= 2.5:
        raise InvalidAvatarImage("Het portret heeft onbruikbare verhoudingen.")
    fitted = head.resize((600, round(head.height * 600 / head.width)), Image.Resampling.LANCZOS)
    x, y = 690 - fitted.width // 2, 465 - fitted.height
    top = min(0, y)
    canvas = Image.new("RGBA", (body.width, body.height - top))
    canvas.alpha_composite(fitted, (x, y - top))
    # Copy RGBA exactly, including translucent collar/outline pixels. Normal
    # alpha composition would mix those pixels with the generated head.
    canvas.paste(body, (0, -top), body.getchannel("A").point(lambda value: 255 if value else 0))
    return canvas


def compose_pixel_avatar(image: Image.Image, body: Image.Image) -> bytes:
    composed = place_pixel_head(extract_pixel_head(image), body)
    bbox = composed.getchannel("A").getbbox()
    fitted = ImageOps.contain(composed.crop(bbox), (608, 608), Image.Resampling.LANCZOS)
    framed = Image.new("RGBA", (640, 640))
    framed.alpha_composite(fitted, ((640 - fitted.width) // 2, (640 - fitted.height) // 2))
    output = BytesIO()
    framed.save(output, format="PNG")
    return validate_transparent_png(output.getvalue())
