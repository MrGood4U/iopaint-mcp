from __future__ import annotations

import uuid
from typing import Any

from PIL import Image, ImageDraw

from .config import check_path, host_output_path, output_dir


def build_region_mask(
    image_path: str,
    regions: list[dict[str, int]],
    margin: int = 8,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Build a white-on-black mask from xywh regions supplied by an external detector."""
    if margin < 0:
        raise ValueError("margin must be non-negative")

    image = Image.open(check_path(image_path, must_exist=True))
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    normalized: list[dict[str, int]] = []

    for index, region in enumerate(regions):
        required = {"x", "y", "width", "height"}
        missing = required - region.keys()
        if missing:
            raise ValueError(f"regions[{index}] is missing: {', '.join(sorted(missing))}")
        x, y = int(region["x"]), int(region["y"])
        width, height = int(region["width"]), int(region["height"])
        if width <= 0 or height <= 0:
            raise ValueError(f"regions[{index}] width and height must be positive")
        left = max(0, x - margin)
        top = max(0, y - margin)
        right = min(image.width - 1, x + width + margin)
        bottom = min(image.height - 1, y + height + margin)
        if left <= right and top <= bottom:
            draw.rectangle((left, top, right, bottom), fill=255)
        normalized.append({"x": x, "y": y, "width": width, "height": height})

    if output_path:
        target = check_path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        target = output_dir() / f"region_mask_{uuid.uuid4().hex}.png"

    mask.save(target)
    result: dict[str, Any] = {"mask_path": str(target.resolve()), "region_count": len(normalized), "regions": normalized}
    visible_path = host_output_path(target)
    if visible_path:
        result["host_mask_path"] = visible_path
    return result
