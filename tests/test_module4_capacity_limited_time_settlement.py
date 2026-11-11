"""Module 4 capacity-limited pressure and time-rate input regression."""
import math
import pytest

from geolysis_engine import (
    boussinesq_rectangular_center_factor,
    consolidation_allowable_pressure,
    consolidation_settlement_1d,
    consolidation_time_rate,
    consolidation_time_rate_layers,
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



def test_multilayer_time_rate_matches_single_layer_time_rate():
    layers = [{"Layer": "A", "Thickness_m": 4.0, "Settlement_mm": 25.0}]
    parameters = [{"Layer": "A", "Cv_m2_per_day": 0.02, "Drainage": "double", "C_alpha": 0.0}]
    result = consolidation_time_rate_layers(layer_results=layers, layer_time_parameters=parameters,
        target_degree_percent=90.0, elapsed_days=100.0)
    single = consolidation_time_rate(primary_settlement_mm=25.0, layer_thickness_m=4.0,
        cv_m2_per_day=0.02, target_degree_percent=90.0, elapsed_days=100.0, drainage="double")
    assert result["time_to_target_days"] == pytest.approx(single["time_to_target_days"], rel=1e-6)
    assert result["primary_settlement_at_elapsed_mm"] == pytest.approx(single["primary_settlement_at_elapsed_mm"], rel=1e-9)
    assert result["average_degree_at_elapsed_percent"] == pytest.approx(single["degree_at_elapsed_percent"], rel=1e-9)


def test_multilayer_time_rate_integrates_layer_responses_at_common_elapsed_time():
    layers = [{"Layer": 1, "Thickness_m": 4.0, "Settlement_mm": 20.0},
              {"Layer": 2, "Thickness_m": 2.0, "Settlement_mm": 10.0}]
    parameters = [{"Layer": 1, "Cv_m2_per_day": 0.005, "Drainage": "double"},
                  {"Layer": 2, "Cv_m2_per_day": 0.02, "Drainage": "single"}]
    elapsed = 180.0
    result = consolidation_time_rate_layers(layer_results=layers, layer_time_parameters=parameters,
        target_degree_percent=90.0, elapsed_days=elapsed)
    layer_1 = consolidation_time_rate(primary_settlement_mm=20.0, layer_thickness_m=4.0,
        cv_m2_per_day=0.005, target_degree_percent=90.0, elapsed_days=elapsed, drainage="double")
    layer_2 = consolidation_time_rate(primary_settlement_mm=10.0, layer_thickness_m=2.0,
        cv_m2_per_day=0.02, target_degree_percent=90.0, elapsed_days=elapsed, drainage="single")
    expected_primary = layer_1["primary_settlement_at_elapsed_mm"] + layer_2["primary_settlement_at_elapsed_mm"]
    expected_degree = 100.0 * expected_primary / 30.0
    assert result["primary_settlement_at_elapsed_mm"] == pytest.approx(expected_primary)
    assert result["average_degree_at_elapsed_percent"] == pytest.approx(expected_degree)
    assert result["time_to_target_days"] > 0


def test_multilayer_time_rate_calculates_secondary_compression_per_layer():
    layers = [{"Layer": "Clay-A", "Thickness_m": 2.0, "Settlement_mm": 10.0},
              {"Layer": "Clay-B", "Thickness_m": 3.0, "Settlement_mm": 15.0}]
    parameters = [
        {"Layer": "Clay-A", "Cv_m2_per_day": 0.01, "Drainage": "double", "C_alpha": 0.01, "e_p": 0.8, "t1_days": 100.0},
        {"Layer": "Clay-B", "Cv_m2_per_day": 0.02, "Drainage": "single", "C_alpha": 0.02, "e_p": 1.0, "t1_days": 500.0},
    ]
    result = consolidation_time_rate_layers(layer_results=layers, layer_time_parameters=parameters,
        target_degree_percent=90.0, elapsed_days=1000.0)
    expected_a = 0.01 * 2.0 / 1.8 * math.log10(1000.0 / 100.0) * 1000.0
    expected_b = 0.02 * 3.0 / 2.0 * math.log10(1000.0 / 500.0) * 1000.0
    assert result["layer_results"][0]["secondary_settlement_at_elapsed_mm"] == pytest.approx(expected_a)
    assert result["layer_results"][1]["secondary_settlement_at_elapsed_mm"] == pytest.approx(expected_b)
    assert result["secondary_settlement_at_elapsed_mm"] == pytest.approx(expected_a + expected_b)


def test_multilayer_time_rate_estimates_secondary_start_at_usace_994_percent_when_blank():
    layers = [{"Layer": 1, "Thickness_m": 4.0, "Settlement_mm": 20.0}]
    parameters = [{"Layer": 1, "Cv_m2_per_day": 0.01, "Drainage": "double", "C_alpha": 0.01, "e_p": 0.9}]
    result = consolidation_time_rate_layers(layer_results=layers, layer_time_parameters=parameters,
        target_degree_percent=90.0, elapsed_days=1000.0)
    layer = result["layer_results"][0]
    assert layer["t1_source"] == "USACE U=99.4% 近似估算"
    assert layer["t1_days"] == pytest.approx(2.0 * 2.0**2 / 0.01)
    assert layer["secondary_settlement_at_elapsed_mm"] > 0


@pytest.mark.parametrize("parameters", [
    [{"Layer": 1, "Drainage": "double"}],
    [{"Layer": 1, "Cv_m2_per_day": 0.01}],
    [{"Layer": 2, "Cv_m2_per_day": 0.01, "Drainage": "double"}],
])
def test_multilayer_time_rate_requires_complete_matching_layer_parameters(parameters):
    with pytest.raises(ValueError):
        consolidation_time_rate_layers(layer_results=[{"Layer": 1, "Thickness_m": 2.0, "Settlement_mm": 10.0}],
            layer_time_parameters=parameters, elapsed_days=100.0)


def test_multilayer_time_rate_rejects_drainage_path_larger_than_layer():
    with pytest.raises(ValueError, match="Hdr"):
        consolidation_time_rate_layers(layer_results=[{"Layer": 1, "Thickness_m": 2.0, "Settlement_mm": 10.0}],
            layer_time_parameters=[{"Layer": 1, "Cv_m2_per_day": 0.01, "Hdr_m": 2.5}], elapsed_days=100.0)
