"""Tests for the TRELLIS Gradio client helper.

These cover result normalization and the missing-configuration guard only; the
live Colab Gradio server is never contacted.
"""

import pytest
from app.services import trellis
from app.services.trellis import (
    TrellisConfigError,
    TrellisError,
    _extract_glb_path,
    generate_mesh,
)


def test_extract_glb_path_from_string() -> None:
    assert _extract_glb_path("/tmp/out/model.glb") == "/tmp/out/model.glb"


def test_extract_glb_path_from_mapping() -> None:
    result = {"path": "/tmp/out/model.glb", "name": "model.glb"}
    assert _extract_glb_path(result) == "/tmp/out/model.glb"


def test_extract_glb_path_prefers_glb_in_sequence() -> None:
    result = [
        {"path": "/tmp/out/preview.png"},
        {"path": "/tmp/out/model.glb"},
    ]
    assert _extract_glb_path(result) == "/tmp/out/model.glb"


def test_extract_glb_path_falls_back_to_first_path() -> None:
    # No .glb suffix present, so the first usable path is returned.
    assert _extract_glb_path(["/tmp/out/model.obj"]) == "/tmp/out/model.obj"


def test_extract_glb_path_raises_on_empty_result() -> None:
    with pytest.raises(TrellisError):
        _extract_glb_path(None)


def test_generate_mesh_requires_configured_url(monkeypatch) -> None:
    class _Settings:
        trellis_gradio_url = None
        trellis_gradio_api_name = "/generate"

    monkeypatch.setattr(trellis, "get_settings", lambda: _Settings())

    with pytest.raises(TrellisConfigError):
        generate_mesh("/tmp/source.jpg")
