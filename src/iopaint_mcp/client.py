from __future__ import annotations

import base64
import mimetypes
import uuid
from pathlib import Path
from typing import Any

import httpx

from .config import check_path, host_output_path, output_dir


def _as_data_url(raw: bytes, path: Path | None = None) -> str:
    mime = mimetypes.guess_type(str(path))[0] if path else None
    mime = mime or "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


class IOPaintClient:
    def __init__(self, base_url: str, timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = httpx.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:2000]
            raise RuntimeError(f"IOPaint API {path} returned {exc.response.status_code}: {detail}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Cannot reach IOPaint at {self.base_url}: {exc}") from exc

    def health_check(self) -> dict[str, Any]:
        response = self._request("GET", "/api/v1/server-config")
        return {"ok": True, "url": self.base_url, "server_config": response.json()}

    def server_info(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/server-config").json()

    def list_models(self) -> list[dict[str, Any]]:
        return self.server_info().get("modelInfos", [])

    def switch_model(self, name: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/model", json={"name": name}).json()

    def inpaint(self, image_path: str, mask_path: str, output_path: str | None = None, **options: Any) -> dict[str, Any]:
        image = check_path(image_path, must_exist=True)
        mask = check_path(mask_path, must_exist=True)
        payload: dict[str, Any] = {
            "image": _as_data_url(image.read_bytes(), image),
            "mask": _as_data_url(mask.read_bytes(), mask),
        }
        payload.update(options)
        response = self._request("POST", "/api/v1/inpaint", json=payload)
        return self._save_result(response.content, output_path, image.suffix or ".png", response.headers.get("X-Seed"))

    def adjust_mask(self, mask_path: str, operation: str, kernel_size: int = 5, output_path: str | None = None) -> dict[str, Any]:
        mask = check_path(mask_path, must_exist=True)
        response = self._request(
            "POST",
            "/api/v1/adjust_mask",
            json={"mask": _as_data_url(mask.read_bytes(), mask), "operate": operation, "kernel_size": kernel_size},
        )
        return self._save_result(response.content, output_path, ".png")

    def plugin_mask(self, plugin_name: str, image_path: str, clicks: list[list[int]] | None = None, output_path: str | None = None) -> dict[str, Any]:
        image = check_path(image_path, must_exist=True)
        response = self._request(
            "POST",
            "/api/v1/run_plugin_gen_mask",
            json={"name": plugin_name, "image": _as_data_url(image.read_bytes(), image), "clicks": clicks or []},
        )
        return self._save_result(response.content, output_path, ".png")

    def plugin_image(self, plugin_name: str, image_path: str, scale: float = 2.0, output_path: str | None = None) -> dict[str, Any]:
        image = check_path(image_path, must_exist=True)
        response = self._request(
            "POST",
            "/api/v1/run_plugin_gen_image",
            json={"name": plugin_name, "image": _as_data_url(image.read_bytes(), image), "scale": scale},
        )
        return self._save_result(response.content, output_path, ".png")

    @staticmethod
    def _save_result(raw: bytes, requested: str | None, suffix: str, seed: str | None = None) -> dict[str, Any]:
        if requested:
            target = check_path(requested)
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            target = output_dir() / f"iopaint_{uuid.uuid4().hex}{suffix.lower()}"
        target.write_bytes(raw)
        result: dict[str, Any] = {"output_path": str(target), "bytes": len(raw)}
        visible_path = host_output_path(target)
        if visible_path:
            result["host_output_path"] = visible_path
        if seed:
            result["seed"] = seed
        return result
