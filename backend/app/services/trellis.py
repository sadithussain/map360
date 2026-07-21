"""Client for the TRELLIS single-image-to-3D model on Colab Gradio.

FastAPI acts as the middleman between the browser and the GPU: this module
forwards an uploaded image to the notebook's live Gradio endpoint via
``gradio_client`` and returns the local path of the generated ``.glb`` file.

The Gradio URL is temporary (it changes every time the Colab notebook
restarts), so it is read from settings on each call rather than cached.
"""

from collections.abc import Mapping, Sequence

from app.core.config import get_settings
from gradio_client import Client, handle_file


class TrellisConfigError(RuntimeError):
    """Raised when the TRELLIS Gradio URL is not configured."""


class TrellisError(RuntimeError):
    """Raised when the TRELLIS Gradio call fails or returns no mesh."""


def _extract_glb_path(result: object) -> str:
    """Normalize a Gradio prediction result into a local ``.glb`` file path.

    Gradio may return the model output as a plain path string, a mapping with a
    ``path``/``name`` key, or a tuple/list of such values (when the endpoint has
    multiple outputs). This resolves the first ``.glb`` file it can find.
    """
    candidates: list[object] = []
    if isinstance(result, (str, Mapping)):
        candidates.append(result)
    elif isinstance(result, Sequence):
        candidates.extend(result)

    for candidate in candidates:
        path: str | None = None
        if isinstance(candidate, str):
            path = candidate
        elif isinstance(candidate, Mapping):
            value = candidate.get("path") or candidate.get("name")
            path = value if isinstance(value, str) else None

        if path and path.lower().endswith(".glb"):
            return path

    # Fall back to the first string-like path even without a .glb suffix.
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
        if isinstance(candidate, Mapping):
            value = candidate.get("path") or candidate.get("name")
            if isinstance(value, str) and value:
                return value

    raise TrellisError(f"TRELLIS returned no usable mesh file (result: {result!r}).")


def generate_mesh(image_path: str) -> str:
    """Send an image to TRELLIS and return the local path of the generated .glb.

    Args:
        image_path: Local filesystem path to the source image.

    Returns:
        Local filesystem path to the generated ``.glb`` mesh downloaded by the
        Gradio client.

    Raises:
        TrellisConfigError: When no Gradio URL is configured.
        TrellisError: When the Gradio server is unreachable, errors, or returns
            no mesh (e.g. the Colab notebook is asleep).
    """
    settings = get_settings()
    if not settings.trellis_gradio_url:
        raise TrellisConfigError(
            "TRELLIS_GRADIO_URL is not set. Start the Colab notebook and set "
            "the active *.gradio.live URL."
        )

    try:
        client = Client(settings.trellis_gradio_url)
    except Exception as exc:  # noqa: BLE001 - normalize connection errors
        raise TrellisError(
            f"Could not connect to the TRELLIS Gradio server "
            f"({settings.trellis_gradio_url}). Is the Colab notebook running? "
            f"({exc})"
        ) from exc

    try:
        result = client.predict(
            handle_file(image_path),
            api_name=settings.trellis_gradio_api_name,
        )
    except Exception as exc:  # noqa: BLE001 - normalize prediction errors
        raise TrellisError(f"TRELLIS generation failed: {exc}") from exc

    return _extract_glb_path(result)
