"""Frame acquisition — webcam/network capture with graceful fallbacks.

OpenCV is an optional dependency: when installed it drives real capture
from local webcams and IP/RTSP streams. Without it, or for webcam cameras
in headless deployments, the :class:`SyntheticFrameSource` supplies
deterministic frames so the pipeline and detectors remain testable.
"""

from __future__ import annotations

from typing import Iterator

from ai.base import Frame

try:
    import cv2  # type: ignore[import-not-found]
    import numpy  # noqa: F401  (imported for its side effect of validating cv2)

    _OPENCV_AVAILABLE = True
except ImportError:
    _OPENCV_AVAILABLE = False


class FrameSourceError(RuntimeError):
    """Raised when a frame source cannot be built (e.g. OpenCV missing)."""


class OpenCVFrameSource:
    """Captures JPEG frames from a video device index or stream URL."""

    def __init__(
        self,
        source: int | str,
        camera_id: int | None = None,
        fps: int | None = None,
    ) -> None:
        if not _OPENCV_AVAILABLE:
            raise FrameSourceError(
                "OpenCV (cv2) is not installed; cannot capture video"
            )
        self.camera_id = camera_id
        self._capture = cv2.VideoCapture(source)
        if fps:
            self._capture.set(cv2.CAP_PROP_FPS, fps)

    def read(self) -> Frame | None:
        """Read one frame, returning ``None`` at end-of-stream."""
        if self._capture is None:
            return None
        ok, array = self._capture.read()
        if not ok or array is None:
            return None
        _, encoded = cv2.imencode(".jpg", array)
        return Frame(
            image=encoded.tobytes(),
            camera_id=self.camera_id,
            metadata={"source": "opencv", "encoding": "jpeg"},
        )

    def stream(self, limit: int | None = None) -> Iterator[Frame]:
        """Yield frames until the stream ends or ``limit`` is reached."""
        emitted = 0
        while True:
            frame = self.read()
            if frame is None:
                break
            yield frame
            emitted += 1
            if limit is not None and emitted >= limit:
                break

    def close(self) -> None:
        """Release the underlying capture device."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "OpenCVFrameSource":
        return self

    def __exit__(self, *_args) -> None:
        self.close()


class SyntheticFrameSource:
    """Deterministic, dependency-free frame source for development and tests.

    Frames carry no pixel data; detection logic keys off the ``seed`` and
    ``index`` metadata entries so results are reproducible across runs.
    """

    def __init__(
        self,
        camera_id: int | None = None,
        frame_count: int = 10,
        seed: int = 0,
    ) -> None:
        self.camera_id = camera_id
        self.frame_count = max(1, frame_count)
        self.seed = seed
        self._index = 0

    def read(self) -> Frame | None:
        """Return the next frame, or ``None`` once the budget is exhausted."""
        if self._index >= self.frame_count:
            return None
        frame = Frame(
            image=b"",
            camera_id=self.camera_id,
            metadata={
                "source": "synthetic",
                "seed": self.seed,
                "index": self._index,
            },
        )
        self._index += 1
        return frame

    def stream(self, limit: int | None = None) -> Iterator[Frame]:
        """Yield up to ``limit`` (or all) frames."""
        budget = self.frame_count if limit is None else min(limit, self.frame_count)
        for _ in range(budget):
            frame = self.read()
            if frame is None:
                break
            yield frame

    def close(self) -> None:
        """No-op; kept for interface symmetry with OpenCV sources."""
        self._index = self.frame_count

    def __enter__(self) -> "SyntheticFrameSource":
        return self

    def __exit__(self, *_args) -> None:
        self.close()
