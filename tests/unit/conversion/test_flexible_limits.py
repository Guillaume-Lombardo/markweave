"""Image resizing and explicit size-limit decisions."""

import io
import zipfile
from dataclasses import replace
from pathlib import PurePosixPath

import pytest
from PIL import Image

from markweave.config import ConversionLimitSettings
from markweave.conversion.archive import ArchiveLimits, prepare_archive
from markweave.conversion.errors import ConversionError
from markweave.conversion.images import ImageLimits, normalize_conversion_image
from markweave.conversion.size_policy import (
    ConversionSizeError,
    SizeLimit,
    require_size_confirmation,
)

pytestmark = pytest.mark.unit

IMAGE_LIMITS = ImageLimits(20_000, 60, 100, 4_000, 100, 64)


def raster(size: tuple[int, int], encoding: str = "PNG") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", size, "blue").save(stream, format=encoding)
    return stream.getvalue()


@pytest.mark.parametrize(
    ("size", "pixels", "expected"),
    [
        ((120, 80), 4_000, (60, 40)),
        ((40, 80), 800, (20, 40)),
        ((120, 80), 600, (30, 20)),
        ((40, 20), 4_000, (40, 20)),
        ((60, 1), 2, (2, 1)),
        ((1, 60), 2, (1, 2)),
    ],
)
def test_resize_dimensions(size, pixels, expected) -> None:
    source = raster(size)
    path = PurePosixPath("assets/photo.png")
    limits = replace(IMAGE_LIMITS, max_pixels=pixels)
    result = normalize_conversion_image(path, source, limits, "resize")
    assert result == normalize_conversion_image(path, source, limits, "resize")
    with Image.open(io.BytesIO(result.content)) as image:
        assert image.size == expected
    if size == expected:
        assert result.warning is None
    else:
        assert result.warning == (
            f"Image 'assets/photo.png' resized from {size[0]}\u00d7{size[1]} "
            f"to {expected[0]}\u00d7{expected[1]}."
        )


@pytest.mark.parametrize(
    "format_name, suffix", [("JPEG", "jpg"), ("GIF", "gif"), ("WEBP", "webp")]
)
def test_resized_image_keeps_its_encoding(format_name: str, suffix: str) -> None:
    source = raster((120, 80), format_name)
    path = PurePosixPath(f"photo.{suffix}")
    result = normalize_conversion_image(path, source, IMAGE_LIMITS, "resize")
    with Image.open(io.BytesIO(result.content)) as image:
        assert image.format == format_name
        assert image.size == (60, 40)


def test_reject_policy_and_source_byte_limit() -> None:
    path = PurePosixPath("photo.png")
    source = raster((120, 80))
    with pytest.raises(ConversionError, match="exceeds configured limits"):
        normalize_conversion_image(path, source, IMAGE_LIMITS, "reject")
    with pytest.raises(ConversionError, match="exceeds configured limits"):
        normalize_conversion_image(
            path, source, replace(IMAGE_LIMITS, max_source_bytes=1), "resize"
        )
    with pytest.raises(ConversionError, match="invalid image"):
        normalize_conversion_image(path, b"invalid", IMAGE_LIMITS, "resize")


def test_header_ceiling_is_checked_before_verification_and_decode(mocker) -> None:
    source = raster((120, 80))
    mocker.patch.object(Image, "MAX_IMAGE_PIXELS", 8_000)
    verify = mocker.patch("PIL.PngImagePlugin.PngImageFile.verify")
    load = mocker.patch("PIL.PngImagePlugin.PngImageFile.load")
    with (
        pytest.warns(Image.DecompressionBombWarning),
        pytest.raises(ConversionError, match="hard decoding limit"),
    ):
        normalize_conversion_image(
            PurePosixPath("photo.png"), source, IMAGE_LIMITS, "resize"
        )
    verify.assert_not_called()
    load.assert_not_called()


@pytest.mark.parametrize(
    ("actual", "hard", "confirmed", "override", "confirmation_required"),
    [
        (10, 40, False, False, None),
        (10, 40, True, False, None),
        (11, 40, False, False, True),
        (11, 40, True, True, None),
        (40, 40, True, True, None),
        (41, 40, False, False, False),
        (41, 40, True, False, False),
        (11, 10, True, False, False),
    ],
)
def test_size_decision(
    actual, hard, confirmed, override, confirmation_required
) -> None:
    limit = SizeLimit("upload", actual, 10, hard)
    if confirmation_required is None:
        assert require_size_confirmation((limit,), confirmed=confirmed) is override
    else:
        with pytest.raises(ConversionSizeError) as raised:
            require_size_confirmation((limit,), confirmed=confirmed)
        assert raised.value.confirmation_required is confirmation_required
        assert raised.value.limit == limit


def test_hard_total_rejection_wins_over_upload_confirmation() -> None:
    upload = SizeLimit("upload", 11, 10, 40)
    unpacked = SizeLimit("decompressed", 101, 50, 100)
    with pytest.raises(ConversionSizeError) as raised:
        require_size_confirmation((upload, unpacked), confirmed=False)
    assert raised.value.limit == unpacked
    assert not raised.value.confirmation_required


def test_override_defaults_and_admin_disable() -> None:
    fields = {
        "conversion_upload_max_bytes": 100,
        "conversion_max_decompressed_bytes": 200,
    }
    defaults = ConversionLimitSettings.model_validate(
        {**fields, "conversion_hard_max_decompressed_bytes": ""}
    )
    assert defaults.effective_conversion_upload_hard_max_bytes == 400
    assert defaults.effective_conversion_hard_max_decompressed_bytes == 800
    disabled = ConversionLimitSettings.model_validate(
        {**fields, "conversion_large_archive_override": False}
    )
    assert disabled.effective_conversion_upload_hard_max_bytes == 100
    assert disabled.effective_conversion_hard_max_decompressed_bytes == 200
    with pytest.raises(ValueError, match="hard ceilings"):
        ConversionLimitSettings.model_validate(
            {**fields, "conversion_upload_hard_max_bytes": 99}
        )


def test_confirmed_extraction_keeps_member_and_hard_total_limits() -> None:
    limits = ArchiveLimits(
        250,
        10,
        80,
        100,
        200,
        80,
        10,
        hard_archive_bytes=500,
        hard_total_uncompressed_bytes=140,
    )

    def archive_with(markdown: int, other: int) -> bytes:
        result = io.BytesIO()
        with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("document.md", b"x" * markdown)
            archive.writestr("other.md", b"y" * other)
        return result.getvalue()

    for markdown, other in ((81, 1), (80, 61)):
        with pytest.raises(ConversionError, match="exceeds configured limits"):
            prepare_archive(
                archive_with(markdown, other),
                limits.for_confirmed_archive(True),
                IMAGE_LIMITS,
            )
    source = archive_with(70, 70)
    with pytest.raises(ConversionError, match="exceeds configured limits"):
        prepare_archive(source, limits.for_confirmed_archive(False), IMAGE_LIMITS)
    assert (
        prepare_archive(
            source, limits.for_confirmed_archive(True), IMAGE_LIMITS
        ).markdown
        == "x" * 70
    )


@pytest.mark.parametrize("policy", ["resize", "reject"])
def test_configured_decode_ceiling_applies_under_either_policy(policy, mocker) -> None:
    source = raster((120, 80))
    limits = replace(IMAGE_LIMITS, max_decode_pixels=8_000)
    verify = mocker.patch("PIL.PngImagePlugin.PngImageFile.verify")
    load = mocker.patch("PIL.PngImagePlugin.PngImageFile.load")
    with pytest.raises(ConversionError, match="hard decoding limit"):
        normalize_conversion_image(PurePosixPath("photo.png"), source, limits, policy)
    verify.assert_not_called()
    load.assert_not_called()


def test_exif_rotation_keeps_display_aspect_ratio_and_source_limit() -> None:
    source = io.BytesIO()
    image = Image.new("RGB", (100, 50), "blue")
    exif = image.getexif()
    exif[274] = 6
    image.save(source, format="JPEG", exif=exif)
    limits = replace(IMAGE_LIMITS, max_pixels=5_000)
    normalized = normalize_conversion_image(
        PurePosixPath("photo.jpg"), source.getvalue(), limits, "resize"
    )
    with Image.open(io.BytesIO(normalized.content)) as raster_image:
        assert raster_image.size == (30, 60)
        assert not raster_image.getexif()
