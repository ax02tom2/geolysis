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
    consolidation_time_rate,
    classify_uscs_aashto,
    hoek_brown_parameters,
    bearing_capacity,
    bearing_capacity_in_situ,
    bearing_pressure_safety_check,
    bearing_capacity_slope_base_corrections,
    layered_bearing_capacity_punching,
    layered_bearing_capacity_profile,
    seismic_bearing_capacity_residual_pore_pressure,
    foundation_sliding_factor_of_safety,
    bishop_simplified_factor_of_safety,
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


def test_layered_bearing_punching_matches_usace_equations_5_17_and_5_18():
    isolated = layered_bearing_capacity_punching(
        q_ult_strong_kpa=300, q_ult_weak_kpa=100,
        strong_layer_thickness_m=1, footing_width_m=2,
        footing_length_m=4, footing_type="isolated",
    )
    continuous = layered_bearing_capacity_punching(
        q_ult_strong_kpa=300, q_ult_weak_kpa=100,
        strong_layer_thickness_m=1, footing_width_m=2,
        footing_length_m=4, footing_type="continuous",
    )
    assert isolated["load_spread_factor"] == pytest.approx((3 * 5) / (2 * 4))
    assert isolated["punching_capacity_kpa"] == pytest.approx(187.5)
    assert isolated["qult_kpa"] == pytest.approx(187.5)
    assert continuous["load_spread_factor"] == pytest.approx(3 / 2)
    assert continuous["punching_capacity_kpa"] == pytest.approx(150.0)
    assert continuous["qult_kpa"] == pytest.approx(150.0)


def test_residual_pore_pressure_bearing_reduction_matches_usace_equations_9_3_and_9_4():
    result = seismic_bearing_capacity_residual_pore_pressure(
        footing_type="spread",
        effective_unit_weight_kn_m3=18,
        effective_width_m=2,
        bearing_factor_ngamma=20,
        residual_excess_pore_pressure_ratio=0.25,
        shape_depth_inclination_factor=0.8,
    )
    expected = 0.4 * (1 - 0.25) * 18 * 2 * 20 * 0.8
    assert result["qu_seismic_kpa"] == pytest.approx(expected)
    assert result["pore_pressure_resistance_factor"] == pytest.approx(0.75)


def test_drained_sliding_matches_usace_equation_5_29():
    result = foundation_sliding_factor_of_safety(
        vertical_load_kN=1000,
        uplift_kN=100,
        horizontal_load_kN=100,
        area_m2=10,
        friction_angle_deg=30,
        cohesion_kpa=10,
        adhesion_ratio=0.5,
        active_force_kN=20,
        passive_force_kN=30,
        fs_required=2.0,
    )
    resistance = (1000 - 100) * math.tan(math.radians(30)) + 0.5 * 10 * 10
    driving = 100 + 20 - 30
    assert result["resisting_force_kN"] == pytest.approx(resistance)
    assert result["driving_force_kN"] == pytest.approx(driving)
    assert result["FS_sliding"] == pytest.approx(resistance / driving)


def test_bishop_simplified_matches_independent_usace_appendix_f_iteration():
    # USACE EM 1110-2-1902 (2003), Appendix F, Eqs. F-1/F-2.
    # Independently iterated reference result for this three-slice dry case.
    slices = [
        {"width_m": 1, "weight_kN": 100, "base_angle_deg": 10,
         "cohesion_kpa": 10, "friction_angle_deg": 25, "pore_pressure_kpa": 0},
        {"width_m": 1, "weight_kN": 120, "base_angle_deg": 20,
         "cohesion_kpa": 10, "friction_angle_deg": 25, "pore_pressure_kpa": 0},
        {"width_m": 1, "weight_kN": 100, "base_angle_deg": 10,
         "cohesion_kpa": 10, "friction_angle_deg": 25, "pore_pressure_kpa": 0},
    ]
    result = bishop_simplified_factor_of_safety(slices=slices)
    assert result["converged"]
    assert result["FS"] == pytest.approx(2.3295012105169772, abs=1e-8)


def test_uscs_five_and_twelve_percent_fines_require_dual_symbols():
    # ASTM D2487: coarse-grained soils with 5–12% fines use dual symbols.
    # Sand is poorly graded (Cu=10, Cc=0.9); fines plot as CL.
    for fines in (5.0, 12.0):
        result = classify_uscs_aashto(
            p4=80, p10=70, p40=60, p200=fines,
            ll=35, pl=20, d10=0.1, d30=0.3, d60=1.0,
        )
        assert result["USCS"] == "SP-SC"


def test_uscs_more_than_twelve_percent_fines_uses_single_fines_symbol():
    # ASTM D2487: >12% fines changes the coarse-soil symbol to SC.
    result = classify_uscs_aashto(
        p4=80, p10=70, p40=60, p200=12.01,
        ll=35, pl=20, d10=0.1, d30=0.3, d60=1.0,
    )
    assert result["USCS"] == "SC"


def test_uscs_cl_ml_borderline_fines_use_dual_symbol_in_coarse_soil():
    # ASTM D2487: CL-ML fines in coarse-grained soil require GC-GM / SC-SM.
    # LL=25 gives A-line PI=3.65; PI=6 lies in the borderline CL-ML zone.
    result = classify_uscs_aashto(
        p4=80, p10=70, p40=60, p200=13,
        ll=25, pl=19, d10=0.1, d30=0.3, d60=1.0,
    )
    assert result["USCS"] == "SC-SM"


def test_aashto_a7_subgroup_boundary_uses_pi_equal_to_ll_minus_thirty_as_a7_5():
    # AASHTO M 145: A-7-5 when PI <= LL-30; A-7-6 when PI > LL-30.
    result = classify_uscs_aashto(
        p4=90, p10=80, p40=70, p200=40,
        ll=60, pl=30,
    )
    assert result["AASHTO"] == "A-7-5"


@pytest.mark.parametrize(
    ("rod_length_m", "expected_factor"),
    [(2.99, 0.75), (3.0, 0.80), (4.0, 0.85),
     (6.0, 0.95), (10.0, 1.00), (30.0, 1.00)],
)
def test_spt_rod_length_factor_boundaries_match_usace_2025_table_4_6(
    rod_length_m, expected_factor
):
    # USACE EM 1110-1-1905 (2025), Table 4-6.
    from geolysis_engine import rod_factor

    assert rod_factor(rod_length_m) == pytest.approx(expected_factor)


def test_spt_dilatancy_correction_matches_usace_2025_equation_4_7():
    # USACE EM 1110-1-1905 (2025), Eq. 4-7:
    # apply only after CN normalization and only when (N1)60 > 15.
    result = spt_correct(
        20, 60, 1.0, 1.0, 10.0, 101.3,
        "Liao & Whitman", 2.0,
        soil_behavior="cohesionless", apply_dilatancy=True,
    )
    assert result["N1_60"] == pytest.approx(20.0)
    assert result["N1_60_final"] == pytest.approx(17.5)
    assert result["dilatancy_applied"] is True


def test_spt_dilatancy_correction_does_not_change_values_at_or_below_fifteen():
    # Eq. 4-7 is only applied when the normalized N-value exceeds 15 bpf.
    result = spt_correct(
        15, 60, 1.0, 1.0, 10.0, 101.3,
        "Liao & Whitman", 2.0,
        soil_behavior="cohesionless", apply_dilatancy=True,
    )
    assert result["N1_60"] == pytest.approx(15.0)
    assert result["N1_60_final"] == pytest.approx(15.0)
    assert result["dilatancy_applied"] is False


def test_aashto_m145_example_6_4_2_group_index_has_no_upper_cap():
    # AASHTO M 145-91 (2021), §6.4.2:
    # F=80, LL=90, PI=50 -> GI=46.3, reported as 46.
    result = classify_uscs_aashto(
        p4=95, p10=90, p40=85, p200=80,
        ll=90, pl=40,
    )
    assert result["AASHTO"] == "A-7-5"
    assert result["GI"] == 46


def test_aashto_m145_example_6_4_3_negative_group_index_is_reported_as_zero():
    # AASHTO M 145-91 (2021), §6.4.3:
    # F=60, LL=25, PI=1 -> raw GI=-1.0, reported as 0.
    result = classify_uscs_aashto(
        p4=95, p10=90, p40=80, p200=60,
        ll=25, pl=24,
    )
    assert result["AASHTO"] == "A-4"
    assert result["GI"] == 0


def test_aashto_m145_example_6_4_4_a2_7_uses_only_pi_group_index_term():
    # AASHTO M 145-91 (2021), §6.4.4:
    # F=30, LL=50, PI=30 -> A-2-7, GI=0.01(30-15)(30-10)=3.
    result = classify_uscs_aashto(
        p4=90, p10=80, p40=70, p200=30,
        ll=50, pl=20,
    )
    assert result["AASHTO"] == "A-2-7"
    assert result["GI"] == 3


@pytest.mark.parametrize(
    ("degree", "expected_tv"),
    [
        (70.0, 0.403),
        (80.0, 0.567),
        (90.0, 0.848),
        (93.1, 1.000),
        (95.0, 1.163),
        (98.0, 1.500),
        (99.4, 2.000),
    ],
)
def test_consolidation_time_factor_matches_usace_2025_figure_7_16(degree, expected_tv):
    # USACE EM 1110-1-1905 (31 Jul 2025), Figure 7-16.
    # For H=4 m, double drainage gives Hdr=2 m; Cv=0.01 m²/day.
    result = consolidation_time_rate(
        primary_settlement_mm=100.0,
        layer_thickness_m=4.0,
        cv_m2_per_day=0.01,
        target_degree_percent=degree,
        drainage="double",
    )
    assert result["time_factor_target"] == pytest.approx(expected_tv, abs=0.001)
    assert result["drainage_path_m"] == pytest.approx(2.0)
    assert result["time_to_target_days"] == pytest.approx(expected_tv * 400.0, abs=0.4)


def test_usace_2025_table_5_3_load_inclination_uses_atan_h_over_v_not_legacy_beta():
    # USACE EM 1110-1-1905 (2025), Table 5-3, Meyerhof-based drained factors:
    # beta=atan(H/V), ic=iq=(1-beta/90)^2, ig=(1-beta/phi')^2.
    phi = 30.0
    base = bearing_capacity(
        theory="Meyerhof", c_kpa=10, phi_deg=phi,
        gamma_moist=18, gamma_sub=9, B=2, L=4, Df=1,
        water_depth=5, load_angle=25.0,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base, c_kpa=10, phi_deg=phi,
        horizontal_load=300, vertical_load=1000,
    )
    beta = math.degrees(math.atan2(300, 1000))
    iq = (1 - beta / 90.0) ** 2
    ig = (1 - beta / phi) ** 2
    assert result["load_inclination_beta_2025_deg"] == pytest.approx(beta)
    assert result["load_factor_c_2025"] == pytest.approx(iq)
    assert result["load_factor_q_2025"] == pytest.approx(iq)
    assert result["load_factor_gamma_2025"] == pytest.approx(ig)
    assert result["term_c"] == pytest.approx(10 * result["Nc"] * result["sc"] * result["dc"] * iq)
    assert result["term_q"] == pytest.approx(result["q_surcharge"] * result["Nq"] * result["sq"] * result["dq"] * iq)
    assert result["term_gamma"] == pytest.approx(
        0.5 * result["B_effective"] * result["gamma_effective"] * result["Ngamma"]
        * result["sg"] * result["dg"] * ig
    )


def test_usace_2025_table_5_4_undrained_load_inclination_uses_h_over_v():
    # USACE EM 1110-1-1905 (2025), Table 5-4:
    # Meyerhof ic = 1 - 1.3 H/V; surcharge-term correction factors are unity.
    base = bearing_capacity(
        theory="Meyerhof", c_kpa=80, phi_deg=0,
        gamma_moist=18, gamma_sub=9, B=2, L=4, Df=1,
        water_depth=5, load_angle=25.0,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base, c_kpa=80, phi_deg=0,
        horizontal_load=300, vertical_load=1000,
    )
    ic = 1.0 - 1.3 * 0.3
    assert result["load_factor_c_2025"] == pytest.approx(ic)
    assert result["load_factor_q_2025"] == pytest.approx(1.0)
    assert result["term_c"] == pytest.approx(
        80 * result["Nc"] * result["sc"] * result["dc"] * ic
    )
    assert result["term_q"] == pytest.approx(result["q_surcharge"] * result["Nq"])
    assert result["term_gamma"] == pytest.approx(0.0)

def test_usace_2025_appendix_b1_undrained_isolated_footing():
    # USACE EM 1110-1-1905 (31 Jul 2025), Appendix B, Example B-1,
    # Table B-1a/b (printed pp. 296-298).
    # Published case: B=L=7 ft, Df=2 ft, gamma=0.120 kcf,
    # su=0.5 ksf, q0=0.24 ksf, Nc=5.14, sc=1.20, dc=1.06.
    # The manual rounds dc to 1.06 before reporting qult=3.51 ksf.
    # This test retains full precision in the engine and allows for that
    # intermediate rounding in the published worked example.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    width = 7.0 * ft_to_m
    embedment = 2.0 * ft_to_m
    gamma = 0.120 * kcf_to_kn_m3
    su = 0.5 * ksf_to_kpa

    base = bearing_capacity(
        theory="Meyerhof",
        c_kpa=su,
        phi_deg=0.0,
        gamma_moist=gamma,
        gamma_sub=9.0,
        gamma_below=gamma,
        B=width,
        L=width,
        Df=embedment,
        water_depth=5.0,
        fs=3.0,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base,
        c_kpa=su,
        phi_deg=0.0,
        horizontal_load=0.0,
        vertical_load=1.0,
    )

    expected_dc = 1.0 + 0.2 * (2.0 / 7.0)
    expected_q0 = 0.24 * ksf_to_kpa
    expected_qult = (1.2 * expected_dc * 0.5 * 5.14 + 0.24) * ksf_to_kpa

    assert result["Nc"] == pytest.approx(5.14)
    assert result["sc"] == pytest.approx(1.20)
    assert result["dc"] == pytest.approx(expected_dc)
    assert result["q_surcharge"] == pytest.approx(expected_q0, abs=0.01)
    assert result["load_factor_c_2025"] == pytest.approx(1.0)
    assert result["load_factor_q_2025"] == pytest.approx(1.0)
    assert result["load_factor_gamma_2025"] is None
    assert result["term_gamma"] == pytest.approx(0.0)
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(
        expected_qult / ksf_to_kpa, abs=1e-8
    )
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(3.50, abs=0.01)
    assert result["qa_gross_direct_FS"] / ksf_to_kpa == pytest.approx(
        (expected_qult / 3.0) / ksf_to_kpa, abs=1e-8
    )

def test_usace_2025_appendix_b3a_drained_isolated_footing():
    # USACE EM 1110-1-1905 (31 Jul 2025), Appendix B, Example B-3,
    # Table B-3a (printed pp. 303-306).
    # Published rounded result: qult=32.15 ksf. The engine retains full
    # precision in N, Nq, Ngamma and correction factors, so its exact
    # equation result is checked separately from the rounded table value.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    width = 7.0 * ft_to_m
    embedment = 2.0 * ft_to_m
    gamma = 0.135 * kcf_to_kn_m3
    water_depth = 13.0 * ft_to_m
    phi = 34.0

    base = bearing_capacity(
        theory="Meyerhof",
        c_kpa=0.0,
        phi_deg=phi,
        gamma_moist=gamma,
        gamma_sub=9.0,
        gamma_below=gamma,
        B=width,
        L=width,
        Df=embedment,
        water_depth=water_depth,
        fs=3.0,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base,
        c_kpa=0.0,
        phi_deg=phi,
        horizontal_load=0.0,
        vertical_load=1.0,
    )

    phi_rad = math.radians(phi)
    flow_n = math.tan(math.radians(45.0) + phi_rad / 2.0) ** 2
    nq = flow_n * math.exp(math.pi * math.tan(phi_rad))
    ngamma = (nq - 1.0) * math.tan(1.4 * phi_rad)
    q0 = 0.27 * ksf_to_kpa
    sq = 1.0 + 0.1 * flow_n
    dq = 1.0 + 0.1 * math.sqrt(flow_n) * (2.0 / 7.0)
    sg = sq
    dgamma = dq
    expected_qult_kpa = (
        q0 * nq * sq * dq
        + 0.5 * width * gamma * ngamma * sg * dgamma
    )

    assert result["Nq"] == pytest.approx(nq, rel=1e-12)
    assert result["Ngamma"] == pytest.approx(ngamma, rel=1e-12)
    assert result["sq"] == pytest.approx(sq, rel=1e-12)
    assert result["dq"] == pytest.approx(dq, rel=1e-12)
    assert result["sg"] == pytest.approx(sg, rel=1e-12)
    assert result["dg"] == pytest.approx(dgamma, rel=1e-12)
    assert result["gamma_effective_2025_factor"] == pytest.approx(1.0)
    assert result["qu_gross"] == pytest.approx(expected_qult_kpa, rel=1e-8)
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(32.33, abs=0.01)
    # The manual reports 32.15 ksf after rounding its intermediate values.
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(32.15, abs=0.20)

def test_usace_2025_appendix_b3b_undrained_punch_through():
    # USACE EM 1110-1-1905 (31 Jul 2025), Appendix B, Example B-3,
    # Table B-3b (printed pp. 307-309).
    # Published USACE result: weak-layer qult,2=3.54 ksf,
    # strong-layer thickness Hs=6 ft, spread ratio=3.45,
    # punch-through capacity=12.21 ksf (rounded).
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    weak_qult = 3.54 * ksf_to_kpa
    strong_qult = 32.15 * ksf_to_kpa
    width = 7.0 * ft_to_m
    thickness = 6.0 * ft_to_m

    result = layered_bearing_capacity_punching(
        q_ult_strong_kpa=strong_qult,
        q_ult_weak_kpa=weak_qult,
        strong_layer_thickness_m=thickness,
        footing_width_m=width,
        footing_length_m=width,
        footing_type="isolated",
    )

    expected_spread = ((7.0 + 6.0) * (7.0 + 6.0)) / (7.0 * 7.0)
    expected_punch_kpa = expected_spread * weak_qult
    assert result["load_spread_factor"] == pytest.approx(expected_spread)
    assert result["punching_capacity_kpa"] == pytest.approx(expected_punch_kpa)
    assert result["qult_kpa"] == pytest.approx(expected_punch_kpa)
    assert result["qult_kpa"] / ksf_to_kpa == pytest.approx(12.21, abs=0.02)
    assert result["controlling_mode"] == "強上層穿刺至弱下層控制"

def test_usace_2025_appendix_b2_undrained_continuous_footing():
    # USACE EM 1110-1-1905 (31 Jul 2025), Appendix B, Example B-2,
    # Table B-2a/b (printed pp. 299-302).
    # The manual treats a continuous footing per unit length: B=2 ft,
    # L is not applicable, Df=2 ft, gamma=0.120 kcf, su=0.5 ksf.
    # L=B is supplied only as the engine's finite-dimension placeholder;
    # footing_type='continuous' must use the strip limit sc=1, not sc=1.2.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    width = 2.0 * ft_to_m
    embedment = 2.0 * ft_to_m
    gamma = 0.120 * kcf_to_kn_m3
    su = 0.5 * ksf_to_kpa

    base = bearing_capacity(
        theory="Meyerhof",
        c_kpa=su,
        phi_deg=0.0,
        gamma_moist=gamma,
        gamma_sub=9.0,
        gamma_below=gamma,
        B=width,
        L=1.0 * ft_to_m,  # finite positive placeholder; continuous footing has no design L
        Df=embedment,
        water_depth=5.0,
        fs=3.0,
        footing_type="continuous",
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base,
        c_kpa=su,
        phi_deg=0.0,
        horizontal_load=0.0,
        vertical_load=1.0,
    )

    expected_dc = 1.0 + 0.2 * (2.0 / 2.0)
    expected_qult = (1.0 * expected_dc * 0.5 * 5.14 + 0.24) * ksf_to_kpa
    assert result["footing_type"] == "continuous"
    assert result["sc"] == pytest.approx(1.0)
    assert result["dc"] == pytest.approx(1.2)
    assert result["q_surcharge"] / ksf_to_kpa == pytest.approx(0.24, abs=1e-8)
    assert result["qu_gross"] == pytest.approx(expected_qult, rel=1e-8)
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(3.32, abs=0.01)

@pytest.mark.parametrize("theory", ["Terzaghi", "Meyerhof", "Hansen", "Vesic"])
def test_continuous_footing_uses_strip_limit_shape_factors_for_all_theories(theory):
    result = bearing_capacity(
        theory=theory,
        c_kpa=10.0,
        phi_deg=30.0,
        gamma_moist=18.0,
        gamma_sub=9.0,
        B=2.0,
        L=2.0,
        Df=1.0,
        water_depth=5.0,
        footing_type="continuous",
    )
    assert result["sc"] == pytest.approx(1.0)
    assert result["sq"] == pytest.approx(1.0)
    assert result["sg"] == pytest.approx(1.0)

@pytest.mark.parametrize("water_depth_ft", [6.0, 12.0])
def test_usace_2025_appendix_b4_undrained_dewatering_resistance(water_depth_ft):
    # USACE EM 1110-1-1905 (31 Jul 2025), Appendix B, Example B-4,
    # Tables B-4a/b/c (printed pp. 311-314).
    # The undrained resistance remains 5.78 ksf for both groundwater
    # levels; groundwater buoyancy changes the applied-pressure demand
    # qeq, which is outside this capacity-only solver.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    width = 7.0 * ft_to_m
    embedment = 2.0 * ft_to_m
    gamma = 0.113 * kcf_to_kn_m3
    su = 0.85 * ksf_to_kpa

    base = bearing_capacity(
        theory="Meyerhof",
        c_kpa=su,
        phi_deg=0.0,
        gamma_moist=gamma,
        gamma_sub=9.0,
        gamma_below=gamma,
        B=width,
        L=width,
        Df=embedment,
        water_depth=water_depth_ft * ft_to_m,
        fs=3.0,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base,
        c_kpa=su,
        phi_deg=0.0,
        horizontal_load=0.0,
        vertical_load=1.0,
    )

    expected_q0 = 0.226 * ksf_to_kpa
    expected_dc = 1.0 + 0.2 * (2.0 / 7.0)
    expected_qult = (1.2 * expected_dc * 0.85 * 5.14 + 0.226) * ksf_to_kpa
    assert result["q_surcharge"] == pytest.approx(expected_q0, abs=0.02)
    assert result["qu_gross"] == pytest.approx(expected_qult, rel=1e-8)
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(5.78, abs=0.02)

def test_usace_2025_appendix_b6a_drained_footing_water_table_in_shear_zone():
    # USACE EM 1110-1-1905 (31 Jul 2025), Appendix B, Example B-6,
    # Table B-6a/c (printed pp. 323-326).
    # Published USACE result: qult=18.8 ksf; gamma'/gamma=0.83.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    width = 8.0 * ft_to_m
    embedment = 2.5 * ft_to_m
    gamma = 0.120 * kcf_to_kn_m3
    water_depth = 8.0 * ft_to_m
    phi = 31.0

    base = bearing_capacity(
        theory="Meyerhof",
        c_kpa=0.0,
        phi_deg=phi,
        gamma_moist=gamma,
        gamma_sub=9.0,
        gamma_below=gamma,
        B=width,
        L=width,
        Df=embedment,
        water_depth=water_depth,
        fs=3.0,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base,
        c_kpa=0.0,
        phi_deg=phi,
        horizontal_load=0.0,
        vertical_load=1.0,
    )

    phi_rad = math.radians(phi)
    flow_n = math.tan(math.radians(45.0) + phi_rad / 2.0) ** 2
    nq = flow_n * math.exp(math.pi * math.tan(phi_rad))
    ngamma = (nq - 1.0) * math.tan(1.4 * phi_rad)
    gamma_ratio = 0.45 + 0.55 * ((8.0 - 2.5) / 8.0)
    q0 = 0.30 * ksf_to_kpa
    shape = 1.0 + 0.1 * flow_n
    depth = 1.0 + 0.1 * math.sqrt(flow_n) * (2.5 / 8.0)
    expected_qult = (
        q0 * nq * shape * depth
        + 0.5 * width * gamma * gamma_ratio * ngamma * shape * depth
    )

    assert result["gamma_effective_2025_factor"] == pytest.approx(gamma_ratio)
    assert result["sq"] == pytest.approx(shape)
    assert result["dq"] == pytest.approx(depth)
    assert result["sg"] == pytest.approx(shape)
    assert result["dg"] == pytest.approx(depth)
    assert result["qu_gross"] == pytest.approx(expected_qult, rel=1e-8)
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(18.8, abs=0.03)


def test_usace_2025_appendix_b6b_punch_through_does_not_control():
    # USACE EM 1110-1-1905 (31 Jul 2025), Appendix B, Example B-6,
    # Table B-6b/c (printed pp. 327-329).
    # Published weak-layer qult,2=2.92 ksf, Hs=13 ft, spread ratio=6.89,
    # punch-through capacity=20.12 ksf. The upper drained capacity (18.8 ksf)
    # remains the controlling resistance.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    width = 8.0 * ft_to_m
    strong_h = 13.0 * ft_to_m
    weak_qult = 2.92 * ksf_to_kpa
    upper_qult = 18.8 * ksf_to_kpa

    result = layered_bearing_capacity_punching(
        q_ult_strong_kpa=upper_qult,
        q_ult_weak_kpa=weak_qult,
        strong_layer_thickness_m=strong_h,
        footing_width_m=width,
        footing_length_m=width,
        footing_type="isolated",
    )

    expected_spread = ((8.0 + 13.0) ** 2) / (8.0 * 8.0)
    expected_punch = expected_spread * weak_qult
    assert result["load_spread_factor"] == pytest.approx(expected_spread)
    assert result["punching_capacity_kpa"] == pytest.approx(expected_punch)
    assert result["punching_capacity_kpa"] / ksf_to_kpa == pytest.approx(20.12, abs=0.03)
    assert result["qult_kpa"] == pytest.approx(upper_qult)
    assert result["controlling_mode"] == "上層一般承載力控制"

def test_layered_profile_passes_continuous_footing_type_to_each_layer():
    # Regression: the profile-level helper must use the strip limit for every
    # layer, and must not require a finite L/B ratio for a continuous footing.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    width = 2.0 * ft_to_m
    result = layered_bearing_capacity_profile(
        layers=[
            {
                "thickness_m": 2.0 * ft_to_m,
                "c_kpa": 0.5 * ksf_to_kpa,
                "phi_deg": 0.0,
                "gamma_moist_kn_m3": 0.120 * kcf_to_kn_m3,
                "gamma_sub_kn_m3": 9.0,
                "gamma_below_kn_m3": 0.120 * kcf_to_kn_m3,
            },
            {
                "thickness_m": 4.0 * ft_to_m,
                "c_kpa": 0.8 * ksf_to_kpa,
                "phi_deg": 0.0,
                "gamma_below_kn_m3": 0.120 * kcf_to_kn_m3,
            },
        ],
        footing_width_m=width,
        footing_length_m=1.0 * ft_to_m,
        footing_depth_m=2.0 * ft_to_m,
        water_depth_m=5.0,
        footing_type="continuous",
    )
    expected_top_qult = (1.2 * 0.5 * 5.14 + 0.24) * ksf_to_kpa
    assert result["qult_kpa"] == pytest.approx(expected_top_qult, rel=1e-8)
    assert result["controlling_layer"] == 1
    assert result["controlling_mode"] == "上層一般承載力"

@pytest.mark.parametrize(
    "test_type,measurements,expected_ksf",
    [
        ("SPT", [12.0, 12.0, 15.0, 14.0], 21.9),
        ("CPT", [200.0, 200.0, 320.0, 200.0], 31.0),
        ("PMT", [17.0], 21.2),
    ],
)
def test_usace_2025_appendix_b7_in_situ_bearing_methods(test_type, measurements, expected_ksf):
    # USACE EM 1110-1-1905 (31 Jul 2025), Appendix B, Example B-7,
    # Table B-7b/c (printed pp. 334-336), Eq. 5-25 and Table 5-5.
    # The manual's rounded qult values are 21.9 ksf (SPT), 31.0 ksf (CPT),
    # and 21.2 ksf (PMT).
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    width = 8.0 * ft_to_m
    embedment = 2.5 * ft_to_m
    gamma = 0.125 * kcf_to_kn_m3
    values = (
        [v * ksf_to_kpa for v in measurements]
        if test_type in ("CPT", "PMT")
        else measurements
    )
    result = bearing_capacity_in_situ(
        test_type=test_type,
        measurements=values,
        drainage="drained",
        B=width,
        L=width,
        Df=embedment,
        gamma_moist=gamma,
        gamma_sub=9.0,
        water_depth=20.0 * ft_to_m,
        fs=3.0,
    )
    assert result["flow_number"] == pytest.approx(3.0)
    assert result["measurement_count"] == len(measurements)
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(expected_ksf, abs=0.15)
    assert result["qa_gross_direct_FS"] == pytest.approx(result["qu_gross"] / 3.0)


def test_usace_2025_in_situ_bearing_continuous_footing_shape_factor():
    result = bearing_capacity_in_situ(
        test_type="SPT",
        measurements=[12.0, 12.0, 15.0, 14.0],
        drainage="drained",
        B=2.0,
        L=1.0,
        Df=0.5,
        gamma_moist=18.0,
        gamma_sub=9.0,
        water_depth=10.0,
        footing_type="continuous",
    )
    assert result["shape_factor"] == pytest.approx(1.0)

def test_usace_2025_appendix_b5_undrained_pmt_bearing_capacity():
    # USACE EM 1110-1-1905 (31 Jul 2025), Appendix B, Example B-5,
    # Table B-5b/e (printed pp. 317-321), Eq. 5-26 and Table 5-5.
    # PMT net limit pressure pne=15.8 ksf, k=0.70 (undrained),
    # sc=1.20, dc=1.06, q0=0.31 ksf; manual qult=14.38 ksf.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    result = bearing_capacity_in_situ(
        test_type="PMT",
        measurements=[15.8 * ksf_to_kpa],
        drainage="undrained",
        B=8.0 * ft_to_m,
        L=8.0 * ft_to_m,
        Df=2.5 * ft_to_m,
        gamma_moist=0.125 * kcf_to_kn_m3,
        gamma_sub=9.0,
        water_depth=20.0 * ft_to_m,
        fs=3.0,
    )
    assert result["k"] == pytest.approx(0.70)
    assert result["shape_factor"] == pytest.approx(1.20)
    assert result["depth_factor"] == pytest.approx(1.0625)
    assert result["q_surcharge_kpa"] / ksf_to_kpa == pytest.approx(0.3125, abs=1e-8)
    # The engine retains full precision; the manual rounds dc to 1.06.
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(14.38, abs=0.05)

def test_usace_2025_equations_5_2_to_5_8_and_5_23_eccentric_uplift_check():
    # Independently calculate the manual equations: A'=B'L', qeq=V/A'-uD,
    # FS=qult/qeq. V includes Q+Wf; groundwater lies 1.0 m above footing base.
    result = bearing_pressure_safety_check(
        ultimate_bearing_kpa=800.0,
        vertical_load_kN=1200.0,
        footing_width_m=2.0,
        footing_length_m=3.0,
        footing_depth_m=1.5,
        water_depth_m=0.5,
        eccentricity_B_m=0.1,
        eccentricity_L_m=0.2,
        required_fs=3.0,
    )
    b_eff = 2.0 - 2 * 0.1
    l_eff = 3.0 - 2 * 0.2
    qeq = 1200.0 / (b_eff * l_eff) - 9.81 * (1.5 - 0.5)
    assert result["B_effective_m"] == pytest.approx(b_eff)
    assert result["L_effective_m"] == pytest.approx(l_eff)
    assert result["effective_area_m2"] == pytest.approx(b_eff * l_eff)
    assert result["water_uplift_pressure_kpa"] == pytest.approx(9.81)
    assert result["qeq_gross_kpa"] == pytest.approx(qeq)
    assert result["FS_bearing"] == pytest.approx(800.0 / qeq)
    assert result["passes_middle_third"] is True
    assert result["passes_all_checks"] is True


def test_usace_2025_continuous_footing_qeq_uses_line_load_and_effective_width():
    result = bearing_pressure_safety_check(
        ultimate_bearing_kpa=900.0,
        vertical_load_kN=500.0,  # kN/m for a continuous footing
        footing_width_m=2.0,
        footing_length_m=1.0,   # unused finite length for strip footing
        footing_depth_m=1.5,
        water_depth_m=2.0,
        eccentricity_B_m=0.1,
        footing_type="continuous",
    )
    assert result["B_effective_m"] == pytest.approx(1.8)
    assert result["qeq_gross_kpa"] == pytest.approx(500.0 / 1.8)
    assert result["passes_middle_third"] is True


def test_usace_2025_bearing_check_flags_middle_third_and_zero_effective_pressure():
    eccentric = bearing_pressure_safety_check(
        ultimate_bearing_kpa=500.0, vertical_load_kN=100.0,
        footing_width_m=2.0, footing_length_m=3.0,
        footing_depth_m=0.0, water_depth_m=0.0,
        eccentricity_B_m=0.34,
    )
    assert eccentric["FS_bearing"] is not None
    assert eccentric["passes_middle_third"] is False
    assert eccentric["passes_all_checks"] is False
    uplift = bearing_pressure_safety_check(
        ultimate_bearing_kpa=500.0, vertical_load_kN=10.0,
        footing_width_m=2.0, footing_length_m=3.0,
        footing_depth_m=2.0, water_depth_m=0.0,
    )
    assert uplift["qeq_gross_kpa"] < 0
    assert uplift["FS_bearing"] is None
    assert uplift["passes_all_checks"] is False

