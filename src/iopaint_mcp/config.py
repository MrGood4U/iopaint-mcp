from __future__ import annotations

import os
import ntpath
import posixpath
import re
from pathlib import Path


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def output_dir() -> Path:
    path = Path(env("MCP_OUTPUT_DIR", "./runtime/output")).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def allowed_roots() -> list[Path] | None:
    value = os.environ.get("MCP_ALLOWED_ROOTS", "").strip()
    if not value:
        return None
    roots = [Path(item).expanduser().resolve() for item in value.split(os.pathsep) if item]
    return roots or None


def _normalize_external_path(value: str) -> tuple[str, bool]:
    """Normalize a path supplied by a host outside the MCP process.

    Docker on Linux can receive a Windows path from a desktop agent. Windows
    paths are normalized with ntpath so drive letters and backslashes work even
    though the MCP process itself runs on Linux.
    """
    value = value.strip().replace("\\", "/")
    is_windows = bool(re.match(r"^[A-Za-z]:/", value))
    if is_windows:
        return ntpath.normpath(value).replace("\\", "/"), True
    return posixpath.normpath(value), False


def path_mappings() -> list[tuple[str, str, bool]]:
    """Return external-to-process path mappings.

    Entries use ``source=>target`` and are separated by semicolons, for
    example ``C:/Users/me/AppData/Local/Temp=>/host-temp``. Semicolons are
    used instead of the platform path separator because Windows source paths
    contain a colon.
    """
    value = os.environ.get("MCP_PATH_MAPPINGS", "").strip()
    if not value:
        return []

    mappings: list[tuple[str, str, bool]] = []
    for entry in value.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if "=>" not in entry:
            raise ValueError("MCP_PATH_MAPPINGS entries must use source=>target format")
        source, target = entry.split("=>", 1)
        normalized_source, is_windows = _normalize_external_path(source)
        normalized_target = posixpath.normpath(target.strip().replace("\\", "/"))
        if normalized_source and normalized_target:
            mappings.append((normalized_source.rstrip("/"), normalized_target, is_windows))
    return mappings


def translate_path(path: str | Path) -> Path:
    """Translate a host path to a path visible to the MCP process."""
    raw = os.fspath(path)
    normalized, is_windows = _normalize_external_path(raw)
    for source, target, source_is_windows in path_mappings():
        if source_is_windows != is_windows:
            continue
        left = normalized.lower() if is_windows else normalized
        right = source.lower() if source_is_windows else source
        if left != right and not left.startswith(f"{right}/"):
            continue
        suffix = normalized[len(source):].lstrip("/")
        return Path(target, *suffix.split("/")) if suffix else Path(target)
    return Path(path)


def host_output_path(path: str | Path) -> str | None:
    """Return the host-visible path for a process-visible output path."""
    host_root = os.environ.get("MCP_HOST_OUTPUT_DIR", "").strip()
    if not host_root:
        return None

    output_root = output_dir()
    candidate = Path(path).expanduser().resolve()
    try:
        relative = candidate.relative_to(output_root)
    except ValueError:
        return None

    if re.match(r"^[A-Za-z]:[\\/]", host_root):
        return ntpath.join(host_root, *relative.parts)
    return str(Path(host_root, *relative.parts))


def check_path(path: str | Path, *, must_exist: bool = False) -> Path:
    resolved = translate_path(path).expanduser().resolve()
    roots = allowed_roots()
    if roots and not any(resolved == root or root in resolved.parents for root in roots):
        raise ValueError(f"Path is outside MCP_ALLOWED_ROOTS: {resolved}")
    if must_exist and not resolved.is_file():
        raise FileNotFoundError(f"File not found: {resolved}")
    return resolved
