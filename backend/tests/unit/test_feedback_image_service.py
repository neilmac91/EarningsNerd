"""Untrusted screenshots cannot retain metadata or outlive the isolated decoder permit."""
from __future__ import annotations

import asyncio
import hashlib
import io
import struct
import sys
from types import SimpleNamespace
import zlib

from PIL import Image, PngImagePlugin
import pytest

from app.services import feedback_image_service as service


def _image_bytes(format_name: str = "PNG", *, mode: str = "RGB") -> bytes:
    output = io.BytesIO()
    with Image.new(mode, (24, 12), (25, 80, 160, 120) if mode == "RGBA" else (25, 80, 160)) as image:
        image.save(output, format=format_name)
    return output.getvalue()


def _png_header(width: int, height: int) -> bytes:
    # Deliberately incomplete pixels: the size guard must run before decoding or verify().
    data = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)

    def chunk(kind, payload):
        body = kind + payload
        return struct.pack("!I", len(payload)) + body + struct.pack("!I", zlib.crc32(body))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", data)
            + chunk(b"IDAT", zlib.compress(b"\0\0\0\0")) + chunk(b"IEND", b""))


async def _cleanup_children(children):
    """A failing assertion or an intentional mutation must not leave the test child alive."""
    for child in children:
        if child.returncode is None:
            child.kill()
        await child.communicate()


@pytest.mark.parametrize("format_name", ["PNG", "JPEG", "WEBP"])
def test_pixels_remain_readable_and_format_is_always_png(format_name):
    original = _image_bytes(format_name)
    png, width, height = service._normalize_pixels(original)
    with Image.open(io.BytesIO(original)) as source, Image.open(io.BytesIO(png)) as result:
        assert result.format == "PNG"
        assert (width, height) == source.size == result.size
        assert result.convert("RGB").tobytes() == source.convert("RGB").tobytes()
        assert not result.info


def test_normalization_preserves_alpha_and_removes_private_metadata():
    text = PngImagePlugin.PngInfo()
    text.add_text("Description", "private account screenshot")
    text.add_itxt("Comment", "confidential financial details")
    exif = Image.Exif()
    exif[270] = "private camera description"
    output = io.BytesIO()
    with Image.new("RGBA", (24, 12), (20, 40, 70, 110)) as image:
        image.save(output, "PNG", pnginfo=text, exif=exif, icc_profile=b"private profile")
    png, width, height = service._normalize_pixels(output.getvalue())
    with Image.open(io.BytesIO(png)) as result:
        assert result.size == (width, height) == (24, 12)
        assert result.getpixel((0, 0)) == (20, 40, 70, 110)
        assert not result.info and not result.getexif()
    assert b"private" not in png and b"confidential" not in png


def test_palette_transparency_and_exif_orientation_are_applied_before_metadata_is_removed():
    output = io.BytesIO()
    with Image.new("P", (6, 3), 1) as image:
        image.putpalette([255, 0, 0, 0, 255, 0] + [0] * (768 - 6))
        image.putpixel((0, 0), 0)
        image.save(output, "PNG", transparency=0)
    png, _, _ = service._normalize_pixels(output.getvalue())
    with Image.open(io.BytesIO(png)) as result:
        assert result.getpixel((0, 0)) == (255, 0, 0, 0)
        assert result.getpixel((1, 0)) == (0, 255, 0, 255)
        assert not result.info

    output = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private description"
    with Image.new("RGB", (6, 3), (0, 255, 0)) as image:
        image.save(output, "JPEG", exif=exif)
    png, width, height = service._normalize_pixels(output.getvalue())
    with Image.open(io.BytesIO(png)) as result:
        assert result.size == (width, height) == (3, 6)
        assert not result.getexif() and not result.info


@pytest.mark.parametrize("width,height", [(4001, 4000), (8193, 1), (1, 8193)])
def test_pixel_and_dimension_limits_precede_pixel_decoding(width, height):
    with pytest.raises(service.FeedbackImageError) as error:
        service._normalize_pixels(_png_header(width, height))
    assert error.value.code == "dimensions"


@pytest.mark.parametrize("format_name", ["PNG", "WEBP"])
def test_animated_files_are_rejected_instead_of_silently_taking_first_frame(format_name):
    output = io.BytesIO()
    with Image.new("RGB", (10, 10), "red") as first, Image.new("RGB", (10, 10), "blue") as second:
        first.save(output, format_name, save_all=True, append_images=[second], duration=100, loop=0)
    with pytest.raises(service.FeedbackImageError) as error:
        service._normalize_pixels(output.getvalue())
    assert error.value.code == "animation"


@pytest.mark.parametrize("data,code", [
    (b"<svg><text>private text</text></svg>", "invalid"),
    (b"\x89PNG\r\n\x1a\nprivate broken image", "invalid"),
    (_image_bytes("BMP"), "format"),
    (_image_bytes("GIF"), "format"),
    (_image_bytes()[:-20], "invalid"),
])
def test_actual_image_content_is_validated_and_errors_do_not_echo_it(data, code):
    with pytest.raises(service.FeedbackImageError) as error:
        service._normalize_pixels(data)
    assert error.value.code == code
    assert "private" not in str(error.value)


def test_encoded_output_is_bounded_while_encoding(monkeypatch):
    monkeypatch.setattr(service, "MAX_OUTPUT_BYTES", 32)
    with pytest.raises(service.FeedbackImageError) as error:
        service._normalize_pixels(_image_bytes())
    assert error.value.code == "output_size"


@pytest.mark.asyncio
async def test_real_worker_normalizes_without_environment_or_application_imports(monkeypatch):
    original = _image_bytes(mode="RGBA")
    create = asyncio.create_subprocess_exec
    children = []

    async def record(*args, **kwargs):
        assert kwargs["env"] == {}
        assert kwargs["stderr"] == asyncio.subprocess.DEVNULL
        assert args[1:3] == ("-I", "-B")
        child = await create(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", record)
    result = await service.normalize_feedback_image(original)
    assert result.content_type == "image/png"
    assert (result.width, result.height) == (24, 12)
    assert result.sha256 == hashlib.sha256(result.data).hexdigest()
    assert len(children) == 1 and children[0].returncode == 0
    with Image.open(io.BytesIO(result.data)) as image:
        assert image.getpixel((0, 0)) == (25, 80, 160, 120)


@pytest.mark.asyncio
async def test_input_size_is_rejected_without_launching_worker(monkeypatch):
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("Oversize input launched a decoder")

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", forbidden)
    for data in (b"", b"x" * (service.MAX_INPUT_BYTES + 1)):
        with pytest.raises(service.FeedbackImageError) as error:
            await service.normalize_feedback_image(data)
        assert error.value.code == "input_size"


@pytest.mark.asyncio
async def test_worker_error_codes_remain_content_free():
    with pytest.raises(service.FeedbackImageError) as error:
        await service.normalize_feedback_image(b"private invalid screenshot contents")
    assert error.value.code == "invalid" and "private" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_request", [False, True])
async def test_native_decoder_is_killed_and_reaped_before_permit_is_released(monkeypatch, tmp_path, cancel_request):
    ready = tmp_path / "decoder-ready"
    script = (
        "import pathlib,sys,threading,time; "
        "threading.Thread(target=lambda:time.sleep(60)).start(); "
        "pathlib.Path(sys.argv[1]).write_text('ready'); sys.stdin.buffer.read(); time.sleep(60)"
    )
    original_command = service._command
    monkeypatch.setattr(service, "_command", lambda: (sys.executable, "-c", script, str(ready)))
    children = []
    deadlines = []
    create = asyncio.create_subprocess_exec

    async def record(*args, **kwargs):
        child = await create(*args, **kwargs)
        children.append(child)
        return child

    def capture_timeout(seconds):
        assert seconds == service.DECODE_TIMEOUT_SECONDS
        deadline = asyncio.timeout(None)
        deadlines.append(deadline)
        return deadline

    monkeypatch.setattr(service, "asyncio", SimpleNamespace(
        **{**vars(asyncio), "create_subprocess_exec": record, "timeout": capture_timeout},
    ))
    task = asyncio.create_task(service.normalize_feedback_image(_image_bytes()))
    try:
        async with asyncio.timeout(10):
            while not ready.exists():
                await asyncio.sleep(0.005)
        assert children[0].returncode is None
        with pytest.raises(service.FeedbackImageBusy):
            await service.normalize_feedback_image(_image_bytes())
        assert len(children) == 1
        if cancel_request:
            task.cancel()
        else:
            deadlines[0].reschedule(asyncio.get_running_loop().time())
        with pytest.raises(asyncio.CancelledError if cancel_request else service.FeedbackImageTimeout):
            async with asyncio.timeout(10):
                await task
        assert children[0].returncode is not None and children[0].returncode < 0
        assert await children[0].wait() == children[0].returncode
        assert deadlines[0].expired() is (not cancel_request)
        monkeypatch.setattr(service, "_command", original_command)
        result = await service.normalize_feedback_image(_image_bytes())
        assert result.content_type == "image/png" and len(children) == 2
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await _cleanup_children(children)


@pytest.mark.asyncio
async def test_cancellation_during_startup_keeps_handle_and_permit_through_repeated_cancellation(monkeypatch):
    create = asyncio.create_subprocess_exec
    started = asyncio.Event()
    release = asyncio.Event()
    children = []
    monkeypatch.setattr(service, "_command", lambda: (
        sys.executable, "-c", "import sys,time; sys.stdin.buffer.read(); time.sleep(60)",
    ))

    async def delayed_handle(*args, **kwargs):
        child = await create(*args, **kwargs)
        children.append(child)
        started.set()
        await release.wait()
        return child

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", delayed_handle)
    task = asyncio.create_task(service.normalize_feedback_image(_image_bytes()))
    try:
        async with asyncio.timeout(10):
            await started.wait()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        with pytest.raises(service.FeedbackImageBusy):
            await service.normalize_feedback_image(_image_bytes())
        release.set()
        with pytest.raises(asyncio.CancelledError):
            async with asyncio.timeout(10):
                await task
        assert children[0].returncode is not None and children[0].returncode < 0
        assert await children[0].wait() == children[0].returncode
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await _cleanup_children(children)


@pytest.mark.asyncio
async def test_broken_worker_cannot_emit_unbounded_output(monkeypatch):
    create = asyncio.create_subprocess_exec
    children = []
    script = (
        "import sys,time; sys.stdin.buffer.read(); "
        f"sys.stdout.buffer.write(b'x' * {service.MAX_OUTPUT_BYTES + service._HEADER.size + 1}); "
        "sys.stdout.buffer.flush(); time.sleep(60)"
    )
    monkeypatch.setattr(service, "_command", lambda: (sys.executable, "-c", script))

    async def record(*args, **kwargs):
        child = await create(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", record)
    try:
        with pytest.raises(service.FeedbackImageError) as error:
            async with asyncio.timeout(10):
                await service.normalize_feedback_image(_image_bytes())
        assert error.value.code == "invalid"
        assert children[0].returncode is not None and children[0].returncode < 0
    finally:
        await _cleanup_children(children)
