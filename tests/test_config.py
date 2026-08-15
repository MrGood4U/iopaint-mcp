import os

import pytest

from iopaint_mcp.config import check_path


@pytest.mark.skipif(os.name == "nt", reason="Container path translation is exercised in a Linux container")
def test_translate_windows_host_path_to_container_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_PATH_MAPPINGS", "C:/Users/test/AppData/Local/Temp=>/host-temp")
    monkeypatch.setenv("MCP_ALLOWED_ROOTS", "/data:/host-temp")

    result = check_path(r"C:\Users\test\AppData\Local\Temp\attachment.png")

    assert str(result) == "/host-temp/attachment.png"


@pytest.mark.skipif(os.name == "nt", reason="Container path translation is exercised in a Linux container")
def test_path_mapping_does_not_match_sibling_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_PATH_MAPPINGS", "C:/Users/test/AppData/Local/Temp=>/host-temp")
    monkeypatch.setenv("MCP_ALLOWED_ROOTS", "/data:/host-temp")

    result = check_path(r"C:\Users\test\AppData\Local\Temp2\attachment.png")

    assert "/host-temp/" not in str(result)
