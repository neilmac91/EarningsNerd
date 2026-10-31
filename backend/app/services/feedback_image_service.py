"""Decode untrusted feedback images in one disposable, deadline-bound process.

The API process never loads image pixels. The child imports no application configuration,
receives no environment credentials, and emits only bounded pixel-only PNG bytes. A permit
stays held until the child has exited, including during cancellation or startup.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
from pathlib import Path
import struct
import sys
import warnings
from dataclasses import dataclass

import anyio

MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_DIMENSION = 8192
DECODE_TIMEOUT_SECONDS = 15.0
_HEADER = struct.Struct("!4sII")
_execution_lock = asyncio.Lock()

_ERROR_MESSAGES = {
    "input_size": "Each screenshot must be no larger than 5 MiB.",
    "format": "Use a PNG, JPEG or static WebP screenshot.",
    "animation": "Animated images are not supported. Choose a single screenshot.",
    "dimensions": "Crop the screenshot to 16 megapixels and at most 8,192 pixels on each side.",
    "output_size": "The screenshot is too large after processing. Crop it to the relevant area.",
    "invalid": "This image could not be read. Choose a different screenshot.",
}
_ERROR_CODES = tuple(_ERROR_MESSAGES)


class FeedbackImageError(ValueError):
    """A fixed, content-free validation failure suitable for the feedback form."""

    def __init__(self, code: str = "invalid") -> None:
        self.code = code if code in _ERROR_MESSAGES else "invalid"
        super().__init__(_ERROR_MESSAGES[self.code])


class FeedbackImageBusy(RuntimeError):
    """The instance's sole decoder is occupied; retry without queueing more pixels."""


class FeedbackImageTimeout(RuntimeError):
    """Native decoding reached its deadline and its process has been reaped."""


@dataclass(frozen=True)
class NormalizedFeedbackImage:
    data: bytes
    width: int
    height: int
    sha256: str
    content_type: str = "image/png"


class _BoundedBuffer(io.BytesIO):
    def write(self, data: bytes) -> int:
        if self.tell() + len(data) > MAX_OUTPUT_BYTES:
            raise FeedbackImageError("output_size")
        return super().write(data)


def _dimensions(width: int, height: int) -> None:
    if not (0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION) or width * height > MAX_PIXELS:
        raise FeedbackImageError("dimensions")


def _normalize_pixels(data: bytes) -> tuple[bytes, int, int]:
    """Child-only decoder; do not call from a request or a worker thread."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if not data or len(data) > MAX_INPUT_BYTES:
        raise FeedbackImageError("input_size")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            # The header check precedes load and verify, including highly compressed images.
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format not in {"PNG", "JPEG", "WEBP"}:
                    raise FeedbackImageError("format")
                _dimensions(*probe.size)
                if getattr(probe, "is_animated", False) or getattr(probe, "n_frames", 1) != 1:
                    raise FeedbackImageError("animation")
                probe.verify()
            # verify() invalidates the reader; fresh load must also succeed before publication.
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                ImageOps.exif_transpose(source, in_place=True)
                _dimensions(*source.size)
                has_alpha = "A" in source.getbands() or "transparency" in source.info
                # Convert while palette transparency is available, then discard all metadata.
                with source.convert("RGBA" if has_alpha else "RGB") as pixels:
                    pixels.info.clear()
                    with _BoundedBuffer() as target:
                        pixels.save(target, format="PNG", optimize=False)
                        return target.getvalue(), pixels.width, pixels.height
    except FeedbackImageError:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise FeedbackImageError("dimensions") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, MemoryError):
        # Never surface decoder messages: they may quote metadata from the uploaded file.
        raise FeedbackImageError("invalid") from None


def _command() -> tuple[str, ...]:
    # A direct, isolated script does not import app.__init__, load .env, or share DB pools.
    return sys.executable, "-I", "-B", str(Path(__file__).resolve())


async def _exchange(process: asyncio.subprocess.Process, data: bytes) -> bytes:
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write(data)
        await process.stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass  # The fixed exit code below decides whether the child rejected the image.
    finally:
        process.stdin.close()
    # readexactly bounds a broken worker too; it cannot make communicate() collect forever.
    try:
        await process.stdout.readexactly(MAX_OUTPUT_BYTES + _HEADER.size + 1)
    except asyncio.IncompleteReadError as exc:
        output = exc.partial
    else:
        raise FeedbackImageError("invalid")
    await process.wait()
    if process.returncode:
        index = process.returncode - 10
        raise FeedbackImageError(_ERROR_CODES[index] if 0 <= index < len(_ERROR_CODES) else "invalid")
    return output


async def _reap(spawn: asyncio.Task[asyncio.subprocess.Process]) -> None:
    try:
        process = await spawn
    except (OSError, RuntimeError):
        return  # No child was created; the original spawn failure is still propagated.
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    if process.stdin is not None:
        process.stdin.close()
    # Drain after kill: Process.wait can otherwise wait on a full stdout pipe's transport.
    if process.stdout is not None:
        while await process.stdout.read(64 * 1024):
            pass
    await process.wait()


async def _finish_child(spawn: asyncio.Task[asyncio.subprocess.Process]) -> None:
    cleanup = asyncio.create_task(_reap(spawn))
    cancelled = False
    while True:
        try:
            with anyio.CancelScope(shield=True):
                await asyncio.shield(cleanup)
            break
        except asyncio.CancelledError:
            # Task.cancel() can arrive again while cleanup runs, outside anyio's shield.
            cancelled = True
            if cleanup.done():
                cleanup.result()
                break
    if cancelled:
        raise asyncio.CancelledError


async def normalize_feedback_image(data: bytes) -> NormalizedFeedbackImage:
    """Validate and normalize one image, or refuse promptly while another is decoding."""
    if not data or len(data) > MAX_INPUT_BYTES:
        raise FeedbackImageError("input_size")
    # No await separates this check and acquisition on the serving event loop.
    if _execution_lock.locked():
        raise FeedbackImageBusy("Screenshot processing is busy. Please retry shortly.")
    async with _execution_lock:
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(
            *_command(), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env={},
        ))
        try:
            try:
                async with asyncio.timeout(DECODE_TIMEOUT_SECONDS):
                    # Shield startup so cancellation cannot lose a newly created child handle.
                    process = await asyncio.shield(spawn)
                    output = await _exchange(process, data)
            except TimeoutError:
                raise FeedbackImageTimeout("Screenshot processing timed out. Crop it and retry.") from None
        finally:
            await _finish_child(spawn)
    if len(output) <= _HEADER.size:
        raise FeedbackImageError("invalid")
    marker, width, height = _HEADER.unpack_from(output)
    if marker != b"PNG1":
        raise FeedbackImageError("invalid")
    _dimensions(width, height)
    png = output[_HEADER.size:]
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise FeedbackImageError("invalid")
    return NormalizedFeedbackImage(png, width, height, hashlib.sha256(png).hexdigest())


def _main() -> int:
    try:
        data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        png, width, height = _normalize_pixels(data)
        sys.stdout.buffer.write(_HEADER.pack(b"PNG1", width, height))
        sys.stdout.buffer.write(png)
        sys.stdout.buffer.flush()
        return 0
    except FeedbackImageError as exc:
        return 10 + _ERROR_CODES.index(exc.code)
    except Exception:
        # Do not print a traceback containing data, paths, metadata or native decoder errors.
        return 10 + _ERROR_CODES.index("invalid")


if __name__ == "__main__":
    raise SystemExit(_main())
