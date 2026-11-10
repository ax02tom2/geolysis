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
    classify_uscs_aashto,
    hoek_brown_parameters,
    bearing_capacity,
    bearing_capacity_slope_base_corrections,
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


def test_aashto_group_index_matches_m145_example_6_4_1():
    # AASHTO M 145-91 (2021), §6.4.1: F=55, LL=40, PI=25 -> A-6, GI=10.
    result = classify_uscs_aashto(
        p4=98, p10=95, p40=90, p200=55,
        ll=40, pl=15, d10=None, d30=None, d60=None,
    )
    assert result["AASHTO"] == "A-6"
    assert result["GI"] == 10


def test_hoek_brown_2002_high_ucs_modulus_branch():
    # Hoek, Carranza-Torres & Corkum (2002), Eq. 11b:
    # for sigma_ci > 100 MPa, Em=(1-D/2)*10^((GSI-10)/40) GPa.
    result = hoek_brown_parameters(
        gsi=60, mi=10, sigma_ci_mpa=150, disturbance=0.5,
        application="general", sigma3_custom_mpa=10,
    )
    expected = (1 - 0.5 / 2) * 10 ** ((60 - 10) / 40)
    assert result["Em_gpa"] == pytest.approx(expected, rel=1e-12)


def test_usace_2025_slope_base_factors_match_table_5_3_equations():
    phi = 30.0
    alpha_b = 10.0
    alpha_g = 15.0
    B = 2.0
    dg = 1.0
    base = bearing_capacity(
        theory="Meyerhof", c_kpa=10, phi_deg=phi,
        gamma_moist=18, gamma_sub=9, B=B, L=4, Df=1,
        water_depth=5,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base, c_kpa=10, phi_deg=phi,
        base_inclination_deg=alpha_b,
        ground_inclination_deg=alpha_g,
        slope_distance_m=dg,
        adjacent_slope_fs=1.5,
    )
    tan_phi = math.tan(math.radians(phi))
    bq = (1 - (alpha_b / 57.0) * tan_phi) ** 2
    bc = bq - (1 - bq) / (base["Nc"] * tan_phi)
    gq0 = (1 - math.tan(math.radians(alpha_g))) ** 2
    gc0 = gq0 - (1 - gq0) / (base["Nc"] * tan_phi)
    recovery = min(1.0, dg / (5.0 * B))
    gq = min(1.0, gq0 + (1 - gq0) * recovery)
    gc = min(1.0, gc0 + (1 - gc0) * recovery)
    assert result["base_factor_q"] == pytest.approx(bq)
    assert result["base_factor_c"] == pytest.approx(bc)
    assert result["base_factor_gamma"] == pytest.approx(bq)
    assert result["ground_factor_q"] == pytest.approx(gq)
    assert result["ground_factor_c"] == pytest.approx(gc)
    assert result["ground_factor_gamma"] == pytest.approx(gq)


def test_usace_2025_drained_depth_factors_use_effective_width_after_eccentricity():
    # USACE EM 1110-1-1905 (2025), Table 5-2 uses Df/B' for Meyerhof-based
    # drained depth factors. This differs from the legacy 1992 Df/B branch
    # when the footing has eccentricity.
    phi = 5.0
    B = 2.0
    B_eff = 1.6
    Df = 1.0
    base = bearing_capacity(
        theory="Meyerhof", c_kpa=10, phi_deg=phi,
        gamma_moist=18, gamma_sub=9, B=B, L=4, Df=Df,
        water_depth=5, eccentricity_B=0.2,
    )
    corrected = bearing_capacity_slope_base_corrections(
        base_result=base, c_kpa=10, phi_deg=phi,
    )
    flow_n = math.tan(math.radians(45 + phi / 2)) ** 2
    expected_dq = 1 + 0.1 * math.sqrt(flow_n) * Df / B_eff
    expected_dc = 1 + 0.2 * math.sqrt(flow_n) * Df / B_eff
    assert corrected["B_effective"] == pytest.approx(B_eff)
    assert corrected["dq"] == pytest.approx(expected_dq)
    assert corrected["dg"] == pytest.approx(expected_dq)
    assert corrected["dc"] == pytest.approx(expected_dc)


def test_usace_2025_groundwater_correction_matches_equation_5_19():
    # USACE EM 1110-1-1905 (2025), Eq. 5-19:
    # gamma' = gamma_t * min[0.45 + 0.55*max(Dw-Df,0)/B, 1].
    base = bearing_capacity(
        theory="Meyerhof", c_kpa=10, phi_deg=30,
        gamma_moist=18, gamma_sub=9, gamma_below=20,
        B=2, L=4, Df=1, water_depth=2,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base, c_kpa=10, phi_deg=30,
    )
    expected_factor = 0.45 + 0.55 * (2 - 1) / 2
    assert result["gamma_effective_2025_factor"] == pytest.approx(expected_factor)
    assert result["gamma_effective"] == pytest.approx(20 * expected_factor)
    assert result["gamma_effective_method"].endswith("Eq. 5-19")


def test_slope_correction_accepts_case_insensitive_meyerhof_alias():
    base = bearing_capacity(
        theory="meyerhof", c_kpa=10, phi_deg=30,
        gamma_moist=18, gamma_sub=9, B=2, L=4, Df=1,
        water_depth=5,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base, c_kpa=10, phi_deg=30,
    )
    assert result["theory"] == "meyerhof"
