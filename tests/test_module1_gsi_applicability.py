"""Module 1 GSI=75 applicability-boundary regression tests."""
import pytest

from geolysis_ui.module1 import _gsi_sensitivity_values
from geolysis_engine import hoek_brown_structure_applicability


def test_intact_massive_gsi_70_to_80_uses_only_applicable_sensitivity_endpoints():
    assert _gsi_sensitivity_values("A", 70, 80) == [70, 75]
    assert hoek_brown_structure_applicability(gsi=75, structure_code="A")["applicable"] is True


def test_intact_massive_gsi_range_entirely_above_75_has_no_hoek_brown_sensitivity_range():
    assert _gsi_sensitivity_values("A", 76, 80) == []


def test_blocky_rock_sensitivity_range_is_not_capped_at_75():
    assert _gsi_sensitivity_values("B", 75, 85) == [75, 85]


def test_invalid_gsi_range_is_rejected():
    with pytest.raises(ValueError, match="GSI 初判下限"):
        _gsi_sensitivity_values("A", 81, 70)
