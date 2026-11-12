"""Foundation geometry classification helpers."""

from ._common import _finite


def usace_footing_type(*, footing_width_m, footing_length_m):
    """Classify footing geometry using USACE EM 1110-1-1905 (2025).

    Rectangular/isolated footings have L/B <= 10. Strip/continuous footings
    have L/B > 10. The caller's calculation method remains responsible for
    rejecting invalid dimensions such as L < B.
    """
    width = _finite("基礎短邊 B", footing_width_m)
    length = _finite("基礎長邊 L", footing_length_m)
    if width <= 0 or length <= 0:
        raise ValueError("基礎短邊 B 與長邊 L 必須大於 0")
    return "continuous" if length / width > 10.0 else "isolated"
