"""Inspect canvas dimensions for formats whose decoders allocate on open."""

from __future__ import annotations

import struct
from collections.abc import Iterator

from markweave.conversion.errors import ConversionError, validation_error

_GIF_SCREEN = struct.Struct("<HHB")
_GIF_FRAME = struct.Struct("<HHHHB")
_GIF_HEADER_BYTES = 13
_GIF_IMAGE_DESCRIPTOR = 0x2C
_GIF_EXTENSION = 0x21
_GIF_APPLICATION_EXTENSION = 0xFF
_WEBP_HEADER_BYTES = 12
_WEBP_CANVAS_BYTES = 10
_VP8_HEADER_BYTES = 10
_VP8L_HEADER_BYTES = 5
_VP8L_SIGNATURE = 0x2F
_WEBP_CHUNK_HEADER = struct.Struct("<4sI")
_WEBP_FLAG_ANIMATED = 0x02
_VP8_DIMENSION_MASK = (1 << 14) - 1


def gif_canvas(data: bytes) -> tuple[int, int]:
    """Read the logical screen and first frame extent without opening Pillow."""
    if data[:6] not in {b"GIF87a", b"GIF89a"} or len(data) < _GIF_HEADER_BYTES:
        raise _invalid_image()
    width, height, flags = _GIF_SCREEN.unpack_from(data, 6)
    offset = _GIF_HEADER_BYTES
    if flags & 0x80:
        offset += 3 << ((flags & 7) + 1)
    while offset < len(data):
        marker = data[offset]
        if marker == _GIF_IMAGE_DESCRIPTOR:
            if offset + 1 + _GIF_FRAME.size > len(data):
                break
            x, y, frame_width, frame_height, _ = _GIF_FRAME.unpack_from(
                data, offset + 1
            )
            return max(width, x + frame_width), max(height, y + frame_height)
        if marker != _GIF_EXTENSION:
            break
        offset = _skip_gif_extension(data, offset)
    raise _invalid_image()


def _skip_gif_extension(data: bytes, marker_offset: int) -> int:
    offset = marker_offset + 2
    if offset >= len(data) or data[offset] == 0:
        raise _invalid_image()
    first_end = offset + 1 + data[offset]
    if (
        data[marker_offset + 1] == _GIF_APPLICATION_EXTENSION
        and data.startswith(b"NETSCAPE2.0", offset + 1, first_end)
        and (first_end >= len(data) or data[first_end] == 0)
    ):
        raise _invalid_image()
    while offset < len(data):
        length = data[offset]
        offset += length + 1
        if length == 0:
            break
    return offset


def webp_dimensions(data: bytes) -> Iterator[tuple[int, int]]:
    """Read RIFF WebP canvas and static frame headers as specified by RFC 9649."""
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise _invalid_image()
    end = int.from_bytes(data[4:8], "little") + 8
    if end != len(data) or end < _WEBP_HEADER_BYTES:
        raise _invalid_image()
    frame_seen = False
    offset = _WEBP_HEADER_BYTES
    while offset + _WEBP_CHUNK_HEADER.size <= end:
        kind, length = _WEBP_CHUNK_HEADER.unpack_from(data, offset)
        start = offset + _WEBP_CHUNK_HEADER.size
        offset = start + length + (length % 2)
        if offset > end:
            raise _invalid_image()
        if kind in {b"ANIM", b"ANMF"}:
            raise validation_error("Animated images are not supported.")
        if kind == b"VP8X":
            yield _webp_canvas(data[start : start + min(length, 10)])
        if kind in {b"VP8 ", b"VP8L"}:
            if frame_seen:
                raise _invalid_image()
            frame_seen = True
            yield _webp_frame(kind, data[start : start + min(length, 10)])
    if not frame_seen or offset != end:
        raise _invalid_image()


def _webp_canvas(header: bytes) -> tuple[int, int]:
    if len(header) != _WEBP_CANVAS_BYTES:
        raise _invalid_image()
    if header[0] & _WEBP_FLAG_ANIMATED:
        raise validation_error("Animated images are not supported.")
    return int.from_bytes(header[4:7], "little") + 1, int.from_bytes(
        header[7:10], "little"
    ) + 1


def _webp_frame(kind: bytes, header: bytes) -> tuple[int, int]:
    if kind == b"VP8L":
        if len(header) < _VP8L_HEADER_BYTES or header[0] != _VP8L_SIGNATURE:
            raise _invalid_image()
        bits = int.from_bytes(header[1:5], "little")
        return (bits & _VP8_DIMENSION_MASK) + 1, (
            (bits >> 14) & _VP8_DIMENSION_MASK
        ) + 1
    if len(header) < _VP8_HEADER_BYTES or header[3:6] != b"\x9d\x01\x2a":
        raise _invalid_image()
    width, height = struct.unpack_from("<HH", header, 6)
    return width & _VP8_DIMENSION_MASK, height & _VP8_DIMENSION_MASK


def _invalid_image() -> ConversionError:
    return validation_error("Document contains an invalid image.")
