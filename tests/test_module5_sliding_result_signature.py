"""Regression tests for Module 5 sliding-result freshness gates."""
import pytest

from geolysis_ui.module5 import _sliding_result_signature


BASE = ("static", 1000.0, 100.0, 50.0)


def signature(**overrides):
    values = {
        "footing_depth_m": 1.5,
        "footing_length_m": 3.0,
        "base_inclination_deg": 0.0,
        "interface_parameters_confirmed": True,
        "base_pressure_reference_kN": 120.0,
        "uplift_pressure_confirmed": True,
        "uplift_pressure_ready": True,
        "footing_area_matches_base": True,
        "footing_units_match": True,
        "seismic_earth_pressure_ready": True,
    }
    values.update(overrides)
    return _sliding_result_signature(BASE, **values)


@pytest.mark.parametrize(
    "changed",
    [
        {"footing_depth_m": 2.0},
        {"footing_length_m": 4.0},
        {"base_pressure_reference_kN": 121.0},
        {"base_inclination_deg": 10.0},
        {"interface_parameters_confirmed": False},
        {"uplift_pressure_confirmed": False},
        {"uplift_pressure_ready": False},
        {"footing_area_matches_base": False},
        {"footing_units_match": False},
        {"seismic_earth_pressure_ready": False},
    ],
)
def test_sliding_signature_changes_when_any_readiness_gate_changes(changed):
    assert signature(**changed) != signature()


def test_sliding_signature_preserves_numerical_input_signature():
    assert signature()[: len(BASE)] == BASE
