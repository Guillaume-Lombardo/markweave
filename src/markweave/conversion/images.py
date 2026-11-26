"""Bounded normalization of untrusted local document images."""

from __future__ import annotations

import io
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal, Never
from xml.etree import ElementTree

from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException
from PIL import Image, ImageOps, UnidentifiedImageError
from tinycss2 import parse_declaration_list
from tinycss2.ast import (
    CurlyBracketsBlock,
    Declaration,
    FunctionBlock,
    Node,
    ParenthesesBlock,
    ParseError,
    SquareBracketsBlock,
    URLToken,
)

from markweave.conversion.errors import ConversionError, validation_error
from markweave.conversion.raster_headers import gif_canvas, webp_dimensions

_SVG_NAMESPACE = "http://www.w3.org/2000/svg"
_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
_XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
_MAX_SAFE_SVG_DEPTH = 64
_MAX_SAFE_CSS_DEPTH = 64
_MAX_SAFE_CSS_NODES = 10_000
_FORBIDDEN_XML = re.compile(rb"(?is)<!\s*(?:doctype|entity)\b")
_LENGTH = re.compile(r"^(?:\d+(?:\.\d+)?|\.\d+)(?:px)?$")
_URL = re.compile(r"(?is)url\(\s*(['\"]?)(.*?)\1\s*\)")
_VIEW_BOX_VALUES = 4
_RASTER_FORMATS = {
    ".gif": frozenset({"GIF"}),
    ".jpeg": frozenset({"JPEG"}),
    ".jpg": frozenset({"JPEG"}),
    ".png": frozenset({"PNG"}),
    ".webp": frozenset({"WEBP"}),
}
_RASTER_MEDIA_TYPES = {
    "GIF": "image/gif",
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
SUPPORTED_IMAGE_SUFFIXES = frozenset((*_RASTER_FORMATS, ".svg"))
SvgRenderer = Callable[[bytes, int, int], bytes]


@dataclass(frozen=True)
class ImageLimits:
    """Configured bounds for image decoding and normalization."""

    max_source_bytes: int
    max_width_pixels: int
    max_height_pixels: int
    max_pixels: int
    max_svg_elements: int
    max_svg_depth: int
    max_decode_pixels: int | None = None

    def __post_init__(self) -> None:
        for value in (
            self.max_source_bytes,
            self.max_width_pixels,
            self.max_height_pixels,
            self.max_pixels,
            self.max_svg_elements,
            self.max_svg_depth,
        ):
            if type(value) is not int or value <= 0:
                raise ValueError("Image limits must be positive integers")
        if self.max_decode_pixels is not None and self.max_decode_pixels <= 0:
            raise ValueError("Image decoding limit must be positive")
        if self.max_svg_depth > _MAX_SAFE_SVG_DEPTH:
            raise ValueError(f"SVG nesting depth cannot exceed {_MAX_SAFE_SVG_DEPTH}")


def _reject_image(message: str = "Document contains an invalid image.") -> Never:
    raise validation_error(message)


def _check_dimensions(width: int, height: int, limits: ImageLimits) -> None:
    if (
        width <= 0
        or height <= 0
        or width > limits.max_width_pixels
        or height > limits.max_height_pixels
        or width * height > limits.max_pixels
    ):
        _reject_image("Document image exceeds configured limits.")


def _fit_dimensions(width: int, height: int, limits: ImageLimits) -> tuple[int, int]:
    scale = min(
        1.0,
        limits.max_width_pixels / width,
        limits.max_height_pixels / height,
        math.sqrt(limits.max_pixels / (width * height)),
    )
    target_width = max(1, int(width * scale))
    target_height = max(1, int(height * scale))
    # Rounding the shorter side up to one pixel can exceed the area budget.
    return min(target_width, limits.max_pixels // target_height or 1), min(
        target_height, limits.max_pixels
    )


@dataclass(frozen=True, slots=True)
class NormalizedImage:
    content: bytes
    media_type: str = "image/png"
    warning: str | None = None


def _check_decode_dimensions(width: int, height: int, limits: ImageLimits) -> None:
    if (
        width <= 0
        or height <= 0
        or any(
            ceiling is not None and width * height > ceiling
            for ceiling in (limits.max_decode_pixels, Image.MAX_IMAGE_PIXELS)
        )
    ):
        _reject_image("Document image exceeds the hard decoding limit.")


def _check_allocating_headers(
    source: bytes, suffix: str, limits: ImageLimits, *, strict: bool = False
) -> None:
    if suffix == ".gif":
        dimensions = (gif_canvas(source),)
    elif suffix == ".webp":
        dimensions = webp_dimensions(source)
    else:
        return
    for width, height in dimensions:
        _check_decode_dimensions(width, height, limits)
        if strict:
            _check_dimensions(width, height, limits)


def _normalized_png(image: Image.Image, limits: ImageLimits) -> bytes:
    _check_dimensions(*image.size, limits)
    if getattr(image, "n_frames", 1) != 1:
        _reject_image("Animated images are not supported.")
    image.load()
    transposed = ImageOps.exif_transpose(image)
    _check_dimensions(*transposed.size, limits)
    has_transparency = "A" in transposed.getbands() or "transparency" in transposed.info
    mode = "RGBA" if has_transparency else "RGB"
    normalized = transposed.convert(mode)
    output = io.BytesIO()
    normalized.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def _normalize_raster(source: bytes, suffix: str, limits: ImageLimits) -> bytes:
    _check_allocating_headers(source, suffix, limits, strict=True)
    try:
        with Image.open(
            io.BytesIO(source), formats=sorted(_RASTER_FORMATS[suffix])
        ) as probe:
            image_format = probe.format
            if image_format not in _RASTER_FORMATS[suffix]:
                _reject_image()
            _check_decode_dimensions(*probe.size, limits)
            _check_dimensions(*probe.size, limits)
            probe.verify()
        with Image.open(
            io.BytesIO(source), formats=sorted(_RASTER_FORMATS[suffix])
        ) as image:
            return _normalized_png(image, limits)
    except ConversionError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        TypeError,
        ValueError,
    ):
        _reject_image()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _has_external_css_reference(value: str) -> bool:
    return any(
        not match.group(2).strip().startswith("#") for match in _URL.finditer(value)
    )


def _is_local_css_url(value: str) -> bool:
    return value.strip().strip("'\"").strip().startswith("#")


def _function_has_local_css_url(token: FunctionBlock) -> bool:
    try:
        value = "".join(argument.serialize() for argument in token.arguments)
    except RecursionError:
        return False
    return _is_local_css_url(value)


def _css_tokens_are_safe(tokens: list[Node]) -> bool:
    block_types = (CurlyBracketsBlock, ParenthesesBlock, SquareBracketsBlock)
    pending = [(tokens, 1)]
    node_count = 0
    while pending:
        current, depth = pending.pop()
        for token in current:
            node_count += 1
            if (
                node_count > _MAX_SAFE_CSS_NODES
                or isinstance(token, ParseError)
                or (isinstance(token, URLToken) and not _is_local_css_url(token.value))
            ):
                return False
            if isinstance(token, FunctionBlock):
                if token.lower_name == "url":
                    if not _function_has_local_css_url(token):
                        return False
                    continue
                nested = token.arguments
            elif isinstance(token, block_types):
                nested = token.content
            else:
                continue
            if depth >= _MAX_SAFE_CSS_DEPTH:
                return False
            pending.append((nested, depth + 1))
    return True


def _sanitize_inline_style(value: str) -> str:
    try:
        declarations = parse_declaration_list(
            value, skip_comments=True, skip_whitespace=True
        )
        safe = [
            declaration.serialize()
            for declaration in declarations
            if isinstance(declaration, Declaration)
            and _css_tokens_are_safe(declaration.value)
        ]
    except RecursionError:
        return ""
    return ";".join(safe)


def _sanitize_svg_tree(root: ElementTree.Element, limits: ImageLimits) -> bytes:
    if root.tag != f"{{{_SVG_NAMESPACE}}}svg":
        _reject_image()
    forbidden_elements = {
        "foreignObject",
        "script",
        "style",
    }
    element_count = 1
    pending = [(root, 1)]
    while pending:
        parent, depth = pending.pop()
        children = list(parent)
        element_count += len(children)
        if element_count > limits.max_svg_elements:
            _reject_image("Document image exceeds configured limits.")
        for child in list(parent):
            if (
                not isinstance(child.tag, str)
                or not child.tag.startswith(f"{{{_SVG_NAMESPACE}}}")
                or _local_name(child.tag) in forbidden_elements
            ):
                parent.remove(child)
                continue
            href = child.attrib.get("href") or child.attrib.get(_XLINK_HREF)
            if href is not None and not href.strip().startswith("#"):
                parent.remove(child)
                continue
            child_depth = depth + 1
            if child_depth > limits.max_svg_depth:
                _reject_image("Document image exceeds configured limits.")
            pending.append((child, child_depth))
        for name, value in tuple(parent.attrib.items()):
            local = _local_name(name).casefold()
            if local == "style":
                sanitized_style = _sanitize_inline_style(value)
                if sanitized_style:
                    parent.attrib[name] = sanitized_style
                else:
                    del parent.attrib[name]
                continue
            if (
                local.startswith("on")
                or name == _XML_BASE
                or (local in {"href", "src"} and not value.strip().startswith("#"))
                or "\\" in value
                or _has_external_css_reference(value)
            ):
                del parent.attrib[name]
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def _svg_dimension(root: ElementTree.Element, name: str, fallback: float) -> float:
    value = root.attrib.get(name)
    if value is None:
        return fallback
    stripped = value.strip()
    if not _LENGTH.fullmatch(stripped):
        _reject_image()
    return float(stripped.removesuffix("px"))


def _svg_dimensions(root: ElementTree.Element) -> tuple[int, int]:
    view_box = root.attrib.get("viewBox", "").replace(",", " ").split()
    fallback_width = fallback_height = math.nan
    if view_box:
        if len(view_box) != _VIEW_BOX_VALUES:
            _reject_image()
        try:
            values = tuple(float(value) for value in view_box)
        except ValueError:
            _reject_image()
        if not all(math.isfinite(value) for value in values):
            _reject_image()
        fallback_width, fallback_height = values[2:]
    width = _svg_dimension(root, "width", fallback_width)
    height = _svg_dimension(root, "height", fallback_height)
    if not math.isfinite(width) or not math.isfinite(height):
        _reject_image()
    return math.ceil(width), math.ceil(height)


def render_svg_with_cairo(source: bytes, width: int, height: int) -> bytes:
    """Rasterize sanitized SVG through the locally installed Cairo engine."""

    try:
        from cairosvg import svg2png  # noqa: PLC0415 - optional native Cairo boundary

        return svg2png(
            bytestring=source,
            output_width=width,
            output_height=height,
            unsafe=False,
        )
    except ImportError, OSError, TypeError, ValueError:
        _reject_image("Document image could not be rasterized.")


def _normalize_svg(source: bytes, limits: ImageLimits, renderer: SvgRenderer) -> bytes:
    if _FORBIDDEN_XML.search(source):
        _reject_image()
    try:
        root = DefusedElementTree.fromstring(source)
    except DefusedXmlException, ElementTree.ParseError, ValueError:
        _reject_image()
    width, height = _svg_dimensions(root)
    _check_dimensions(width, height, limits)
    sanitized = _sanitize_svg_tree(root, limits)
    try:
        rendered = renderer(sanitized, width, height)
        with Image.open(io.BytesIO(rendered)) as image:
            return _normalized_png(image, limits)
    except ConversionError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        TypeError,
        ValueError,
    ):
        _reject_image()


def normalize_image(
    path: PurePosixPath,
    source: bytes,
    limits: ImageLimits,
    svg_renderer: SvgRenderer = render_svg_with_cairo,
) -> bytes:
    """Validate and normalize one supported local image to metadata-free PNG."""

    suffix = path.suffix.casefold()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        _reject_image("Document contains an unsupported image type.")
    if type(source) is not bytes or not source or len(source) > limits.max_source_bytes:
        _reject_image("Document image exceeds configured limits.")
    if suffix == ".svg":
        return _normalize_svg(source, limits, svg_renderer)
    return _normalize_raster(source, suffix, limits)


def normalize_conversion_image(
    path: PurePosixPath,
    source: bytes,
    limits: ImageLimits,
    policy: Literal["resize", "reject"],
) -> NormalizedImage:
    """Keep the original raster encoding when resizing an oversized input."""

    suffix = path.suffix.casefold()
    if policy == "reject" or suffix not in _RASTER_FORMATS:
        return NormalizedImage(normalize_image(path, source, limits))
    if not source or len(source) > limits.max_source_bytes:
        _reject_image("Document image exceeds configured limits.")
    _check_allocating_headers(source, suffix, limits)
    formats = sorted(_RASTER_FORMATS[suffix])
    try:
        with Image.open(io.BytesIO(source), formats=formats) as probe:
            _check_decode_dimensions(*probe.size, limits)
            probe.verify()
        with Image.open(io.BytesIO(source), formats=formats) as image:
            return _resize_raster(path, image, limits)
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        TypeError,
        ValueError,
    ):
        _reject_image()


def _resize_raster(
    path: PurePosixPath, image: Image.Image, limits: ImageLimits
) -> NormalizedImage:
    _check_decode_dimensions(*image.size, limits)
    if getattr(image, "is_animated", False):
        _reject_image("Animated images are not supported.")
    image_format = image.format
    if image_format is None:
        _reject_image()
    original_size = image.size
    ImageOps.exif_transpose(image, in_place=True)
    width, height = image.size
    target = _fit_dimensions(width, height, limits)
    if (
        target == image.size
        and _fit_dimensions(*original_size, limits) == original_size
    ):
        return NormalizedImage(_encode_raster(image, "PNG"))
    if target == image.size:
        # The source orientation exceeds its dimension budget. Apply that same
        # scale after EXIF orientation so the displayed image stays proportional.
        original_width, original_height = _fit_dimensions(*original_size, limits)
        target = (original_height, original_width)
    new_width, new_height = target
    return NormalizedImage(
        _encode_raster(image, image_format, target),
        _RASTER_MEDIA_TYPES[image_format],
        f"Image {path.as_posix()!r} resized from {width}\u00d7{height} "
        f"to {new_width}\u00d7{new_height}.",
    )


def _encode_raster(
    image: Image.Image, image_format: str, size: tuple[int, int] | None = None
) -> bytes:
    has_transparency = "A" in image.getbands() or "transparency" in image.info
    mode = "RGBA" if has_transparency and image_format != "JPEG" else "RGB"
    normalized = image.convert(mode)
    if size is not None:
        normalized = normalized.resize(size, Image.Resampling.LANCZOS)
    # A fresh image drops inherited EXIF, ICC, comments and text chunks.
    normalized.info.clear()
    output = io.BytesIO()
    options = {"compress_level": 9, "optimize": False} if image_format == "PNG" else {}
    normalized.save(output, format=image_format, **options)
    return output.getvalue()


def validate_resized_raster(
    path: PurePosixPath, source: bytes, media_type: str, limits: ImageLimits
) -> None:
    """Recheck bounded raster format and dimensions at the document boundary."""
    suffix = path.suffix.casefold()
    formats = _RASTER_FORMATS.get(suffix, frozenset())
    _check_allocating_headers(source, suffix, limits)
    try:
        with Image.open(io.BytesIO(source), formats=list(formats)) as image:
            if _RASTER_MEDIA_TYPES.get(image.format or "") != media_type:
                _reject_image()
            _check_decode_dimensions(*image.size, limits)
            _check_dimensions(*image.size, limits)
            if getattr(image, "is_animated", False):
                _reject_image()
            image.load()
    except Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError:
        _reject_image()


def validate_normalized_png(source: bytes, limits: ImageLimits) -> None:
    """Defensively prove that manifest bytes are bounded normalized PNG output."""

    if type(source) is not bytes or not source:
        _reject_image()
    try:
        with Image.open(io.BytesIO(source), formats=["PNG"]) as image:
            if image.info:
                _reject_image()
            normalized = _normalized_png(image, limits)
    except ConversionError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        TypeError,
        ValueError,
    ):
        _reject_image()
    if normalized != source:
        _reject_image()
