import pytest

from geolysis_engine import combine_settlement_stage_movements


def test_standard_settlement_stages_sum_without_excavation_rebound():
    result = combine_settlement_stage_movements(
        immediate_settlement_mm=3.0,
        primary_settlement_mm=18.0,
        secondary_settlement_mm=2.5,
    )
    assert result["total_settlement_mm"] == pytest.approx(23.5)
    assert result["excavation_rebound_mm"] == 0.0
    assert result["post_excavation_recompression_mm"] == 0.0


def test_excavation_rebound_and_post_excavation_recompression_are_signed_and_summed():
    result = combine_settlement_stage_movements(
        immediate_settlement_mm=2.0,
        excavation_rebound_mm=-7.5,
        post_excavation_recompression_mm=11.0,
        secondary_settlement_mm=0.5,
    )
    assert result["total_settlement_mm"] == pytest.approx(6.0)


def test_stage_summary_rejects_double_counting_primary_and_recompression():
    with pytest.raises(ValueError, match="互斥計算路徑"):
        combine_settlement_stage_movements(
            primary_settlement_mm=10.0,
            post_excavation_recompression_mm=8.0,
        )


@pytest.mark.parametrize("kwargs", [
    {"immediate_settlement_mm": -1.0},
    {"primary_settlement_mm": -1.0},
    {"secondary_settlement_mm": -1.0},
    {"post_excavation_recompression_mm": -1.0},
    {"excavation_rebound_mm": 1.0},
])
def test_stage_summary_rejects_inconsistent_movement_signs(kwargs):
    with pytest.raises(ValueError):
        combine_settlement_stage_movements(**kwargs)
