from io import BytesIO

import pytest
from PIL import Image
from pillow_heif import register_heif_opener
from sqlmodel import Session
from test_avatars import api as api

from app.avatar_images import InvalidAvatarImage, normalize_upload
from app.avatar_models import AvatarJob


def heic():
    register_heif_opener()
    image = Image.new("RGB", (80, 40), (140, 80, 40))
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private-photo-metadata"
    image.info["exif"] = exif.tobytes()
    output = BytesIO()
    image.save(output, format="HEIF", quality=90)
    return output.getvalue()


@pytest.mark.parametrize("mime", ["image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"])
def test_heic_orientation_and_metadata_are_normalized(mime):
    result = Image.open(BytesIO(normalize_upload(heic(), mime)))
    assert result.format == "PNG" and result.mode == "RGBA" and result.size == (40, 80)
    assert not result.getexif() and "exif" not in result.info and "xmp" not in result.info
    assert b"private-photo-metadata" not in normalize_upload(heic(), mime)


def test_heic_upload_stores_only_normalized_primary_image(api):
    client, database, _ = api
    raw = heic()
    response = client.post("/api/avatars/me/jobs", content=raw, headers={"Content-Type": "image/heic"})
    assert response.status_code == 202
    with Session(database) as session:
        source = session.get(AvatarJob, response.json()["id"]).source_png
        assert source.startswith(b"\x89PNG") and source != raw
        assert Image.open(BytesIO(source)).size == (40, 80)
        assert b"private-photo-metadata" not in source


def test_large_phone_jpeg_is_resized_before_rgba_copy():
    output = BytesIO()
    Image.new("RGB", (6000, 4000), (80, 130, 170)).save(output, format="JPEG")
    result = Image.open(BytesIO(normalize_upload(output.getvalue(), "image/jpeg")))
    assert result.size == (1024, 683)


def test_heif_uses_primary_photo_instead_of_another_container_image():
    register_heif_opener()
    output = BytesIO()
    first = Image.new("RGB", (80, 40), "red")
    primary = Image.new("RGB", (64, 96), "blue")
    first.save(output, format="HEIF", save_all=True, append_images=[primary], primary_index=1)
    result = Image.open(BytesIO(normalize_upload(output.getvalue(), "image/heif")))
    assert result.size == primary.size
    red, _, blue, _ = result.getpixel((32, 48))
    assert blue > red + 100


def test_photo_limits_and_actual_format_still_apply(monkeypatch):
    from app import avatar_images

    with pytest.raises(InvalidAvatarImage):
        normalize_upload(heic(), "image/png")
    with pytest.raises(InvalidAvatarImage):
        normalize_upload(b"not a HEIC photo", "image/heic")
    monkeypatch.setattr(avatar_images, "MAX_PHOTO_PIXELS", 100)
    with pytest.raises(InvalidAvatarImage, match="megapixels"):
        normalize_upload(heic(), "image/heic")
