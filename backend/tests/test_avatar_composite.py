import importlib.util
import stat
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/avatar_composite.py"
spec = importlib.util.spec_from_file_location("avatar_composite", SCRIPT)
composite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(composite)


def test_extraction_removes_border_white_but_preserves_enclosed_white_and_foreground():
    source = Image.new("RGBA", (9, 9), "white")
    ImageDraw.Draw(source).rectangle((2, 2, 6, 6), outline="black", width=1)
    source.putpixel((3, 3), (253, 252, 250, 255))
    source.putpixel((4, 2), (120, 30, 20, 130))
    original = source.tobytes()
    result, metadata = composite.remove_border_white(source, threshold=240)
    assert result.getpixel((0, 0)) == (0, 0, 0, 0)
    assert result.getpixel((4, 4)) == (255, 255, 255, 255)
    assert result.getpixel((3, 3)) == (253, 252, 250, 255)
    assert result.getpixel((4, 2)) == (120, 30, 20, 130)
    assert metadata["removed_visible_pixels"] == 56
    assert metadata["retained_near_white_pixels"] == 9
    assert metadata["visible_bbox_xyxy"] == [2, 2, 7, 7]
    assert metadata["visible_bbox_normalized_xyxy"] == [0.222222, 0.222222, 0.777778, 0.777778]
    assert metadata["visible_border_pixels"] == 0
    assert metadata["partial_alpha_pixels"] == 1
    assert source.tobytes() == original


def test_extraction_threshold_and_four_connected_boundary_are_explicit():
    source = Image.new("RGBA", (3, 3), "black")
    source.putpixel((0, 0), (245, 245, 245, 255))
    source.putpixel((1, 1), (255, 255, 255, 255))
    strict, _ = composite.remove_border_white(source, threshold=250)
    relaxed, metadata = composite.remove_border_white(source, threshold=240)
    assert strict.getpixel((0, 0))[3] == 255
    assert relaxed.getpixel((0, 0))[3] == 0
    assert relaxed.getpixel((1, 1))[3] == 255
    assert metadata["connectivity"] == 4
    assert any("Visible pixels still touch" in caveat for caveat in metadata["caveats"])


def test_composition_preserves_all_body_rgba_pixels_and_expands_canvas():
    body = Image.new("RGBA", (4, 4))
    body.putpixel((1, 1), (20, 50, 90, 64))
    body.putpixel((2, 2), (30, 80, 110, 255))
    original = body.tobytes()
    head = Image.new("RGBA", (4, 4), (240, 180, 100, 255))
    result, metadata = composite.compose_head(head, body, box=(-1, -1, 4, 4), padding=2,
                                               resample="nearest")
    assert result.size == (9, 9)
    assert metadata["body_origin_in_output_xy"] == [3, 3]
    assert metadata["head_origin_in_output_xy"] == [2, 2]
    assert result.getpixel((4, 4)) == body.getpixel((1, 1))
    assert result.getpixel((5, 5)) == body.getpixel((2, 2))
    assert result.getpixel((2, 2)) == head.getpixel((0, 0))
    assert result.getpixel((0, 0))[3] == 0
    assert metadata["body_visible_pixels_copied_unchanged"] == 2
    assert metadata["translucent_body_pixels_overlapping_head"] == 1
    assert body.tobytes() == original


def test_neck_anchor_uses_manual_crop_bottom_center_without_stretching():
    source = Image.new("RGBA", (10, 10))
    ImageDraw.Draw(source).rectangle((2, 2, 5, 7), fill=(100, 80, 50, 255))
    body = Image.new("RGBA", (20, 20))
    result, metadata = composite.compose_head(source, body, source_box=(2, 2, 4, 6),
                                               neck_anchor=(10, 12), head_width=8, resample="nearest")
    assert result.size == body.size
    assert metadata["source_bbox_xyxy"] == [2, 2, 6, 8]
    assert metadata["head_box_in_body_xywh"] == [6, 0, 8, 12]
    assert metadata["neck_anchor_in_body_xy"] == [10, 12]
    assert result.getchannel("A").getbbox() == (6, 0, 14, 12)


def test_png_and_metadata_are_private_and_have_no_source_exif(tmp_path):
    image = Image.new("RGBA", (3, 3), (40, 60, 80, 120))
    exif = Image.Exif()
    exif[270] = "private camera metadata"
    image.info["exif"] = exif.tobytes()
    path = tmp_path / "private" / "result.png"
    composite.save_result(path, image, {"operation": "test"})
    with Image.open(path) as saved:
        assert saved.mode == "RGBA"
        assert saved.getexif() == {}
        assert saved.tobytes() == image.tobytes()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.with_suffix(".metadata.json").stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        composite.save_result(path, Image.new("RGBA", (1, 1)), {})
    assert Image.open(path).size == (3, 3)
