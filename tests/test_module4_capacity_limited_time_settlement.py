"""Module 4 capacity-limited pressure and time-rate input regression."""
import pytest

from geolysis_engine import (
    boussinesq_rectangular_center_factor,
    consolidation_allowable_pressure,
    consolidation_settlement_1d,
)


def test_primary_settlement_is_recomputed_when_capacity_caps_net_pressure():
    stress_factor = boussinesq_rectangular_center_factor(2.0, 3.0, 3.0)
    params = {
        "footing_pressure_factor": stress_factor,
        "layer_thickness_m": 5.0,
        "initial_void_ratio": 0.8,
        "compression_index": 0.30,
        "recompression_index": 0.05,
        "initial_effective_stress_kpa": 100.0,
        "preconsolidation_stress_kpa": 150.0,
    }
    settlement_limit = 25.0
    allowable = consolidation_allowable_pressure(
        target_settlement_mm=settlement_limit,
        **params,
    )
    qa_settlement = allowable["qa_primary_consolidation_kpa"]
    assert qa_settlement > 0

    # A separate bearing-capacity cap controls at half the settlement-based
    # pressure. Time-rate and secondary compression must use this actual
    # pressure's primary settlement, not the 25-mm target used to find qa.
    qa_final = 0.5 * qa_settlement
    actual = consolidation_settlement_1d(
        layer_thickness_m=params["layer_thickness_m"],
        initial_void_ratio=params["initial_void_ratio"],
        compression_index=params["compression_index"],
        recompression_index=params["recompression_index"],
        initial_effective_stress_kpa=params["initial_effective_stress_kpa"],
        preconsolidation_stress_kpa=params["preconsolidation_stress_kpa"],
        stress_increase_kpa=qa_final * stress_factor,
    )
    assert qa_final < qa_settlement
    assert 0.0 < actual["settlement_mm"] < settlement_limit
