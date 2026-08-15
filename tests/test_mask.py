from pathlib import Path

from PIL import Image

from iopaint_mcp.mask import build_region_mask


def test_build_region_mask_expands_xywh_regions(tmp_path: Path) -> None:
    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    Image.new("RGB", (100, 80), "white").save(image_path)
    result = build_region_mask(
        str(image_path),
        [{"x": 20, "y": 20, "width": 10, "height": 8}],
        margin=3,
        output_path=str(mask_path),
    )
    assert result["region_count"] == 1
    mask = Image.open(mask_path)
    assert mask.getpixel((17, 17)) == 255
    assert mask.getpixel((5, 5)) == 0
