"""Secondary compression physical-input validation regressions."""
import pytest

from geolysis_engine import secondary_compression_settlement


def test_secondary_compression_matches_usace_equation_7_47():
    result = secondary_compression_settlement(
        layer_thickness_m=3.0,
        secondary_compression_index=0.02,
        void_ratio_at_primary_end=0.8,
        time_start_days=100.0,
        time_end_days=1000.0,
    )
    expected_mm = 0.02 * 3.0 / 1.8 * 1.0 * 1000.0
    assert result["secondary_settlement_mm"] == pytest.approx(expected_mm)


@pytest.mark.parametrize("void_ratio", [-0.5, -0.001])
def test_secondary_compression_rejects_negative_void_ratio(void_ratio):
    with pytest.raises(ValueError, match="ep 不可為負值"):
        secondary_compression_settlement(
            layer_thickness_m=3.0,
            secondary_compression_index=0.02,
            void_ratio_at_primary_end=void_ratio,
            time_start_days=100.0,
            time_end_days=1000.0,
        )
