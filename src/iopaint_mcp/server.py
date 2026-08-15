from __future__ import annotations

import argparse
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import IOPaintClient
from .mask import build_region_mask


def _client() -> IOPaintClient:
    return IOPaintClient(os.environ.get("IOPAINT_URL", "http://127.0.0.1:28680"))


mcp = FastMCP(
    "IOPaint MCP",
    instructions=(
        "Local IOPaint image-editing server. IOPaint REST must already be running at IOPAINT_URL. "
        "Use inpaint_image when you already have a mask; white/255 pixels are edited and black/0 pixels are preserved. "
        "Use erase_regions when an external OCR/vision detector supplies image-pixel rectangles {x,y,width,height}; "
        "this server does not perform OCR. Inputs and outputs are local filesystem paths, not URLs or base64. "
        "In Docker, configured host-to-container path mappings can make desktop-agent attachment paths usable directly; "
        "otherwise use paths under the mounted /data directory. In Docker, write generated files under /data/output and "
        "use host_output_path in tool results when presenting the file to the desktop agent. "
        "Call health_check first if needed."
    ),
)


@mcp.tool()
def health_check() -> dict[str, Any]:
    """Check whether the IOPaint REST backend at IOPAINT_URL is reachable.

    Call this first when the backend may not be running. If it fails, do not retry
    image-editing tools until IOPaint has been started or IOPAINT_URL is corrected.
    """
    return _client().health_check()


@mcp.tool()
def get_server_info() -> dict[str, Any]:
    """Return IOPaint capabilities, including available plugins, models and samplers.

    Use this to discover what the currently running IOPaint instance supports
    before selecting a model or plugin. This does not perform image editing.
    """
    return _client().server_info()


@mcp.tool()
def list_models() -> list[dict[str, Any]]:
    """List models currently discovered by IOPaint.

    Use an exact returned model name with switch_model or inpaint_image(model=...).
    The list depends on the IOPaint installation and whether models have loaded.
    """
    return _client().list_models()


@mcp.tool()
def switch_model(name: str) -> dict[str, Any]:
    """Switch IOPaint's active model, such as ``lama`` or a diffusion model.

    Call list_models first when the name is unknown. Switching changes the shared
    IOPaint process state and may take time or require substantial memory.
    """
    return _client().switch_model(name)


@mcp.tool()
def inpaint_image(
    image_path: str,
    mask_path: str,
    output_path: str | None = None,
    model: str | None = None,
    hd_strategy: str = "Crop",
    hd_strategy_crop_margin: int = 128,
    prompt: str = "",
    negative_prompt: str = "",
    sd_steps: int = 50,
    sd_strength: float = 1.0,
    sd_seed: int = 42,
) -> dict[str, Any]:
    """Inpaint the white regions of a mask and save the edited image.

    ``image_path`` and ``mask_path`` must be readable by the MCP process, and the
    mask should match the image dimensions. In Docker, a configured host path
    mapping may allow desktop-agent attachment paths as inputs; write outputs
    under ``/data/output``. White/255 mask pixels are replaced;
    black/0 pixels are preserved. Use this when a mask already exists. Use
    create_mask_from_regions or erase_regions when only external coordinates exist.
    ``model`` is optional and changes IOPaint's shared active model. ``output_path``
    is optional; when omitted, the server creates an output file and returns its path.
    ``hd_strategy`` is typically ``Crop`` (local repair), ``Resize`` or ``Original``.
    Prompt parameters are mainly relevant to diffusion-based models. Example:
    ``inpaint_image("input.png", "mask.png", output_path="clean.png")``.
    """
    client = _client()
    if model:
        client.switch_model(model)
    return client.inpaint(
        image_path,
        mask_path,
        output_path,
        hd_strategy=hd_strategy,
        hd_strategy_crop_margin=hd_strategy_crop_margin,
        prompt=prompt,
        negative_prompt=negative_prompt,
        sd_steps=sd_steps,
        sd_strength=sd_strength,
        sd_seed=sd_seed,
    )


@mcp.tool()
def adjust_mask(mask_path: str, operation: str, kernel_size: int = 5, output_path: str | None = None) -> dict[str, Any]:
    """Modify an existing mask through IOPaint.

    ``operation`` must be ``expand``, ``shrink`` or ``reverse``. Expand/shrink
    change the edited area around mask edges; ``kernel_size`` controls the amount.
    Use this when a detector's mask is slightly too small or too large. The result
    is a new mask path unless ``output_path`` is supplied.
    """
    if operation not in {"expand", "shrink", "reverse"}:
        raise ValueError("operation must be expand, shrink, or reverse")
    return _client().adjust_mask(mask_path, operation, kernel_size, output_path)


@mcp.tool()
def run_plugin_gen_mask(plugin_name: str, image_path: str, clicks: list[list[int]] | None = None, output_path: str | None = None) -> dict[str, Any]:
    """Run an enabled IOPaint plugin that generates a mask.

    The plugin must be available in the running IOPaint instance; discover plugins
    with get_server_info. For interactive segmentation, ``clicks`` uses
    ``[x, y, label]`` points in image pixels, where the plugin defines the label
    meaning (commonly 1=foreground and 0=background). Omit clicks for plugins that
    do not need them. Returns the generated mask path.
    """
    return _client().plugin_mask(plugin_name, image_path, clicks, output_path)


@mcp.tool()
def run_plugin_gen_image(plugin_name: str, image_path: str, scale: float = 2.0, output_path: str | None = None) -> dict[str, Any]:
    """Run an enabled IOPaint plugin that generates an image.

    Use get_server_info to confirm the plugin is available. ``scale`` is commonly
    used by super-resolution plugins such as ``realesrgan``; the accepted range and
    behavior are plugin-specific. Returns the generated image path.
    """
    return _client().plugin_image(plugin_name, image_path, scale, output_path)


@mcp.tool()
def create_mask_from_regions(
    image_path: str,
    regions: list[dict[str, int]],
    margin: int = 8,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Create a white-on-black mask from externally supplied rectangles.

    ``regions`` must contain dictionaries with integer pixel coordinates
    ``{x, y, width, height}``, where x/y are the top-left corner. ``margin`` adds
    pixels on every side, and rectangles are clipped to the image. This tool does
    not perform OCR or vision detection; the caller/another agent must provide the
    coordinates. Use the returned ``mask_path`` with inpaint_image.
    """
    return build_region_mask(image_path, regions, margin, output_path)


@mcp.tool()
def erase_regions(
    image_path: str,
    regions: list[dict[str, int]],
    output_path: str | None = None,
    mask_output_path: str | None = None,
    margin: int = 8,
    model: str = "lama",
    hd_strategy: str = "Crop",
) -> dict[str, Any]:
    """Create a mask from external rectangles and erase them in one call.

    ``regions`` must be image-pixel rectangles in ``{x, y, width, height}`` form;
    this tool does not contain OCR. It is intended for coordinates produced by an
    OCR, computer-vision system, or the calling agent. ``margin`` expands each
    rectangle before inpainting. In Docker, mapped desktop-agent attachment paths
    can be used directly as inputs; write generated files under ``/data/output``.
    ``model`` defaults to ``lama``. The result includes
    the edited ``output_path``, the generated ``mask_path``, the normalized regions,
    and ``region_count``. Example region: ``{"x": 120, "y": 80, "width": 240,
    "height": 48}``. Use inpaint_image instead when you already have a mask.
    """
    mask_info = build_region_mask(image_path, regions, margin, mask_output_path)
    client = _client()
    if model:
        client.switch_model(model)
    result = client.inpaint(
        image_path,
        mask_info["mask_path"],
        output_path,
        hd_strategy=hd_strategy,
        hd_strategy_crop_margin=max(32, margin * 4),
        sd_seed=42,
    )
    return {
        **result,
        "mask_path": mask_info["mask_path"],
        "host_mask_path": mask_info.get("host_mask_path"),
        "region_count": mask_info["region_count"],
        "regions": mask_info["regions"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP server for IOPaint")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "28681")))
    args = parser.parse_args()
    if args.transport == "stdio":
        mcp.run()
    else:
        # MCP SDK 1.x reads HTTP settings from mcp.settings rather than from
        # FastMCP.run(). This also remains compatible with newer 1.x releases.
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        # Keep the standard stateful Streamable HTTP + SSE behavior. It is the
        # most interoperable mode for clients such as Codex; JSON/stateless mode
        # can leave some clients waiting during the initialize handshake.
        mcp.settings.stateless_http = False
        mcp.settings.json_response = False
        mcp.run(transport="streamable-http")
