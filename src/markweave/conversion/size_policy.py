"""Size decisions for explicitly confirmed forward conversions."""

from dataclasses import asdict, dataclass
from typing import Literal

Dimension = Literal["upload", "decompressed"]


@dataclass(frozen=True, slots=True)
class SizeLimit:
    dimension: Dimension
    actual_bytes: int
    soft_limit_bytes: int
    hard_limit_bytes: int

    def audit_fields(self) -> dict[str, str | int]:
        return asdict(self)

    def message(self) -> str:
        subject = "Upload" if self.dimension == "upload" else "Uncompressed archive"
        return (
            f"{subject} is {self.actual_bytes} bytes. The standard limit is "
            f"{self.soft_limit_bytes} bytes and the hard limit is {self.hard_limit_bytes} bytes."
        )


class ConversionSizeError(ValueError):
    def __init__(self, limit: SizeLimit, *, confirmation_required: bool) -> None:
        super().__init__(limit.message())
        self.limit = limit
        self.confirmation_required = confirmation_required


def require_size_confirmation(
    limits: tuple[SizeLimit, ...], *, confirmed: bool
) -> bool:
    """Return whether the request used an override, or reject it."""

    for limit in limits:
        if limit.actual_bytes > limit.hard_limit_bytes:
            raise ConversionSizeError(limit, confirmation_required=False)
    for limit in limits:
        if limit.actual_bytes > limit.soft_limit_bytes:
            if not confirmed:
                raise ConversionSizeError(limit, confirmation_required=True)
            return True
    return False
