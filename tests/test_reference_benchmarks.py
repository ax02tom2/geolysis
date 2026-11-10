"""Independent reference benchmarks transcribed from cited engineering standards.

These tests intentionally compare outputs to published equations/tables rather than
only checking internal consistency or directional trends.
"""
import math
import pytest

from geolysis_engine import (
    spt_correct,
    burland_burbidge_2025_settlement,
    boussinesq_rectangular_center_factor,
    consolidation_settlement_layers,
)


def test_spt_corrections_match_usace_2025_equations_4_4_to_4_7():
    # EM 1110-1-1905 (2025), Eqs. 4-4a/4-4b, 4-5/4-6 and Table 4-6.
    result = spt_correct(
        20, 80, 1.05, 1.10, 5.0, 50.0,
        "Liao & Whitman", 2.0,
    )
    expected_n60 = 20 * (80 / 60) * 1.05 * 1.10 * 0.85
    expected_cn = min(2.0, math.sqrt(101.3 / 50.0))
    assert result["N60"] == pytest.approx(expected_n60, abs=1e-10)
    assert result["CN"] == pytest.approx(expected_cn, abs=1e-10)
    assert result["N1_60"] == pytest.approx(expected_n60 * expected_cn, abs=1e-10)


def test_boussinesq_square_center_influence_matches_usace_table_6_2():
    # EM 1110-1-1905 (2025), Table 6-2: square footing, B/z = 1,
    # Boussinesq influence factor I_sigma = 0.3360.
    factor = boussinesq_rectangular_center_factor(1.0, 1.0, 1.0)
    assert factor == pytest.approx(0.3360, abs=2e-4)


def test_two_to_one_stress_factor_matches_usace_equation_6_12():
    # EM 1110-1-1905 (2025), Eq. 6-12:
    # I_sigma = B*L / ((B+z)*(L+z)).
    result = consolidation_settlement_layers(
        layers=[{
            "Layer": 1, "Depth_center_m": 2.0, "Thickness_m": 1.0,
            "e0": 0.8, "Cc": 0.3, "Cr": 0.05,
            "Sigma0_kPa": 100.0, "SigmaP_kPa": 150.0,
        }],
        footing_width_m=2.0,
        footing_length_m=4.0,
        net_pressure_kpa=100.0,
        stress_method="2:1",
    )
    assert result["layer_results"][0]["Stress_factor"] == pytest.approx(1 / 3)


def test_burland_burbidge_nc_settlement_matches_usace_2025_equations_7_27_to_7_34():
    # Hand calculation from EM 1110-1-1905 (2025), Eqs. 7-27 to 7-34:
    # B=L=2 m, N60=20, q=100 kPa, sigma'0=100 kPa, Hs > Zi, t=3 years,
    # static loading. C1=1, C2=1, C3=1.3.
    result = burland_burbidge_2025_settlement(
        n60_average=20.0,
        width_m=2.0,
        length_m=2.0,
        gross_pressure_kpa=100.0,
        initial_effective_stress_kpa=100.0,
        preconsolidation_stress_kpa=100.0,
        granular_layer_thickness_m=10.0,
        years=3.0,
        load_type="static",
    )
    assert result["influence_depth_m"] == pytest.approx(1.6265279, abs=1e-6)
    assert result["C1_shape"] == pytest.approx(1.0)
    assert result["C2_layer"] == pytest.approx(1.0)
    assert result["C3_time"] == pytest.approx(1.3)
    assert result["settlement_mm"] == pytest.approx(23.3171, abs=0.002)
