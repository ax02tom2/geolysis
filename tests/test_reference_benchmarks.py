"""Independent reference benchmarks transcribed from cited engineering standards.

These tests intentionally compare outputs to published equations/tables rather than
only checking internal consistency or directional trends.
"""
import math
import pytest

from geolysis_engine import (
    spt_correct,
    spt_profile,
    burland_burbidge_2025_settlement,
    burland_burbidge_average_n60_from_ground_profile,
    burland_burbidge_average_n60_from_profile,
    boussinesq_rectangular_center_factor,
    consolidation_settlement_layers,
    consolidation_time_rate,
    classify_uscs_aashto,
    hoek_brown_parameters,
    hoek_brown_structure_applicability,
    bearing_capacity,
    bearing_capacity_in_situ,
    layered_bearing_capacity_in_situ_profile,
    bearing_pressure_safety_check,
    bearing_capacity_slope_base_corrections,
    layered_bearing_capacity_punching,
    layered_bearing_capacity_profile,
    seismic_bearing_capacity_residual_pore_pressure,
    seismic_bearing_capacity_residual_pore_pressure_cases,
    seismic_foundation_eccentricity_cases,
    foundation_sliding_factor_of_safety,
    foundation_sliding_pseudostatic_cases,
    developed_rankine_sliding_earth_pressures,
    seismic_uplift_stability_cases,
    bishop_simplified_factor_of_safety,
    usace_settlement_design_pressure,
    dmt_settlement_2025,
    dmt_modulus_settlement_2025,
    schmertmann_cpt_settlement_2025,
    menard_rousseau_pmt_settlement_2025,
    usace_footing_type,
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
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
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

def test_usace_2025_middle_third_boundary_is_strictly_inside():
    result = bearing_pressure_safety_check(
        ultimate_bearing_kpa=800.0, vertical_load_kN=1200.0,
        footing_width_m=2.0, footing_length_m=3.0,
        footing_depth_m=0.0, water_depth_m=0.0,
        eccentricity_B_m=2.0 / 6.0,
    )
    assert result["passes_middle_third"] is False
    assert result["passes_all_checks"] is False

def test_usace_in_situ_layered_profile_spread_and_control():
    # Independently calculate layer resistances from Table 5-5, then apply
    # Eq. 5-17. B=2 m, L=3 m, Hs=1.5 m gives spread=(3.5*4.5)/(2*3)=2.625.
    result = layered_bearing_capacity_in_situ_profile(
        layers=[
            {"thickness_m":1.5,"test_type":"SPT","drainage":"drained","measurements":[20,22,18]},
            {"thickness_m":2.0,"test_type":"SPT","drainage":"undrained","measurements":[4,5,4]},
        ],
        footing_width_m=2.0,footing_length_m=3.0,
        footing_depth_m=0.0,water_depth_m=10.0,
        gamma_moist_kn_m3=18.0,gamma_sub_kn_m3=9.0,
    )
    top_mean=(20*22*18)**(1/3)
    weak_mean=(4*5*4)**(1/3)
    top_qult=0.6*(1+0.3*2/3)*(top_mean*2*47.88025898)
    weak_qult=0.35*(1+0.2*2/3)*(weak_mean*2*47.88025898)
    spread=((2.0+1.5)*(3.0+1.5))/(2.0*3.0)
    assert result["layers"][0]["qult_kpa"] == pytest.approx(top_qult)
    assert result["layers"][1]["qult_kpa"] == pytest.approx(weak_qult)
    assert result["candidates"][-1]["spread_factor"] == pytest.approx(spread)
    assert result["qult_kpa"] == pytest.approx(min(top_qult,spread*weak_qult))
    assert result["controlling_mode"] == "原位試驗弱層穿刺控制"


def test_usace_in_situ_layered_profile_continuous_strip_spread():
    result = layered_bearing_capacity_in_situ_profile(
        layers=[
            {"thickness_m":2.0,"test_type":"PMT","drainage":"drained","measurements":[200,220]},
            {"thickness_m":2.0,"test_type":"PMT","drainage":"undrained","measurements":[15,16]},
        ],
        footing_width_m=2.0,footing_length_m=1.0,
        footing_depth_m=0.0,water_depth_m=10.0,
        gamma_moist_kn_m3=18.0,gamma_sub_kn_m3=9.0,
        footing_type="continuous",
    )
    assert result["candidates"][-1]["spread_factor"] == pytest.approx(2.0)
    assert result["punching_depth_range_m"] == pytest.approx((2.0,8.0))


def test_usace_in_situ_layered_profile_shallow_weak_layer_directly_controls():
    result = layered_bearing_capacity_in_situ_profile(
        layers=[
            {"thickness_m":0.5,"test_type":"SPT","drainage":"drained","measurements":[20,20]},
            {"thickness_m":1.0,"test_type":"SPT","drainage":"undrained","measurements":[3,3]},
        ],
        footing_width_m=2.0,footing_length_m=3.0,
        footing_depth_m=0.0,water_depth_m=10.0,
        gamma_moist_kn_m3=18.0,gamma_sub_kn_m3=9.0,
    )
    assert result["controlling_mode"] == "剪力區弱層直接控制"
    assert result["controlling_layer"] == 2
    assert result["candidates"][-1]["spread_factor"] == pytest.approx(1.0)

def test_usace_in_situ_layered_profile_rejects_drained_weak_layer_punching():
    with pytest.raises(ValueError, match="weak clay|undrained"):
        layered_bearing_capacity_in_situ_profile(
            layers=[
                {"thickness_m":1.5,"test_type":"SPT","drainage":"drained","measurements":[20,20]},
                {"thickness_m":2.0,"test_type":"CPT","drainage":"drained","measurements":[50,55]},
            ],
            footing_width_m=2.0,footing_length_m=3.0,
            footing_depth_m=0.0,water_depth_m=10.0,
            gamma_moist_kn_m3=18.0,gamma_sub_kn_m3=9.0,
        )




def test_usace_2025_settlement_pressure_uses_lower_of_qeq_and_qult_over_fs():
    # USACE EM 1110-1-1905 (2025), §7-2 and settlement procedures:
    # use gross q/qeq, capped by qult/FS.
    governed = usace_settlement_design_pressure(
        gross_equivalent_pressure_kpa=240.0,
        ultimate_bearing_kpa=600.0,
        factor_of_safety=3.0,
    )
    assert governed["capacity_pressure_limit_kpa"] == pytest.approx(200.0)
    assert governed["design_pressure_kpa"] == pytest.approx(200.0)
    assert governed["capacity_limit_governs"] is True

    load_governs = usace_settlement_design_pressure(
        gross_equivalent_pressure_kpa=150.0,
        ultimate_bearing_kpa=600.0,
        factor_of_safety=3.0,
    )
    assert load_governs["design_pressure_kpa"] == pytest.approx(150.0)
    assert load_governs["capacity_limit_governs"] is False


@pytest.mark.parametrize(
    "q,qult,fs",
    [(0.0, 500.0, 3.0), (100.0, 0.0, 3.0), (100.0, 500.0, 1.0)],
)
def test_usace_2025_settlement_pressure_rejects_invalid_inputs(q, qult, fs):
    with pytest.raises(ValueError):
        usace_settlement_design_pressure(
            gross_equivalent_pressure_kpa=q,
            ultimate_bearing_kpa=qult,
            factor_of_safety=fs,
        )



def test_burland_burbidge_imports_module3_n60_and_converts_depth_from_ground():
    profile = [
        {"Depth_m": 0.5, "N60": 18.0},   # above footing base: excluded
        {"Depth_m": 1.5, "N60": 20.0},   # 0.5 m below base: included
        {"Depth_m": 2.0, "N60": 25.0},   # 1.0 m below base: included
        {"Depth_m": 2.5, "N60": None},   # refusal / partial penetration: excluded
        {"Depth_m": 3.5, "N60": 40.0},   # outside influence depth: excluded
    ]
    result = burland_burbidge_average_n60_from_ground_profile(
        profile,
        foundation_depth_m=1.0,
        width_m=2.0,
        granular_layer_thickness_m=5.0,
    )
    assert result["foundation_depth_m"] == pytest.approx(1.0)
    assert result["selected_count"] == 2
    assert result["N60_average"] == pytest.approx(22.5)
    assert result["selected_profile"] == [(0.5, 20.0, 20.0), (1.0, 25.0, 25.0)]


def test_burland_burbidge_module3_link_rejects_profile_without_usable_below_base_n60():
    with pytest.raises(ValueError, match="沒有可用的 N60"):
        burland_burbidge_average_n60_from_ground_profile(
            [{"Depth_m": 0.5, "N60": 20.0}, {"Depth_m": 2.0, "N60": None}],
            foundation_depth_m=1.0,
            width_m=2.0,
            granular_layer_thickness_m=5.0,
        )



def test_usace_seismic_residual_pore_pressure_allows_shape_depth_factor_product_above_one():
    result = seismic_bearing_capacity_residual_pore_pressure(
        footing_type="spread",
        effective_unit_weight_kn_m3=18.0,
        effective_width_m=2.0,
        bearing_factor_ngamma=20.0,
        residual_excess_pore_pressure_ratio=0.2,
        shape_depth_inclination_factor=1.25,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    assert result["other_correction_product"] == pytest.approx(1.25)
    assert result["qu_seismic_kpa"] == pytest.approx(0.4 * 0.8 * 18.0 * 2.0 * 20.0 * 1.25)


def test_usace_seismic_residual_pore_pressure_rejects_nonpositive_factor_product():
    with pytest.raises(ValueError, match="修正係數乘積"):
        seismic_bearing_capacity_residual_pore_pressure(
            footing_type="strip",
            effective_unit_weight_kn_m3=18.0,
            effective_width_m=2.0,
            bearing_factor_ngamma=20.0,
            residual_excess_pore_pressure_ratio=0.2,
            shape_depth_inclination_factor=0.0,
            non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
        )



def test_usace_seismic_pore_pressure_cases_auto_apply_table_factors_and_control_envelope():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0,
        horizontal_load_kN=0.0,
        kh=0.2,
        kv=0.1,
        footing_type="spread",
        residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0,
        phi_deg=30.0,
        gamma_moist=18.5,
        gamma_sub=9.5,
        gamma_below=18.5,
        B=2.0,
        L=3.0,
        Df=1.5,
        water_depth=5.0,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    assert len(result["cases"]) == 4
    assert {case["horizontal_earthquake_sign"] for case in result["cases"]} == {-1, 1}
    controlling = result["governing_case"]
    beta = math.degrees(math.atan2(200.0, 900.0))
    flow_n = math.tan(math.radians(60.0)) ** 2
    shape = 1.0 + 0.1 * flow_n * (2.0 / 3.0)
    depth = 1.0 + 0.1 * math.sqrt(flow_n) * (1.5 / 2.0)
    inclination = (1.0 - beta / 30.0) ** 2
    gamma_effective = 18.5
    nq = math.exp(math.pi * math.tan(math.radians(30.0))) * flow_n
    ngamma = (nq - 1.0) * math.tan(math.radians(42.0))
    expected = 0.4 * (1.0 - 0.2) * gamma_effective * 2.0 * ngamma * shape * depth * inclination
    assert controlling["vertical_sign"] == "向下減少"
    assert controlling["load_inclination_beta_deg"] == pytest.approx(beta)
    assert controlling["shape_s_gamma"] == pytest.approx(shape)
    assert controlling["depth_d_gamma"] == pytest.approx(depth)
    assert controlling["inclination_i_gamma"] == pytest.approx(inclination)
    assert controlling["qu_seismic_kpa"] == pytest.approx(expected)


def test_usace_seismic_pore_pressure_cases_rejects_cohesive_or_undrained_soil():
    with pytest.raises(ValueError, match="砂狀排水土"):
        seismic_bearing_capacity_residual_pore_pressure_cases(
            vertical_load_kN=1000.0,horizontal_load_kN=0.0,kh=0.2,kv=0.0,
            footing_type="spread",residual_excess_pore_pressure_ratio=0.2,
            c_kpa=5.0,phi_deg=30.0,gamma_moist=18.5,gamma_sub=9.5,
            gamma_below=18.5,B=2.0,L=3.0,Df=1.5,water_depth=5.0,
        )



def test_usace_2025_appendix_b5a_undrained_strength_based_bearing_capacity():
    # Appendix B, Example B-5, Table B-5a (printed pp. 317-318).
    # 8 ft square footing, Df=2.5 ft, gamma=0.125 kcf, su=3.2 ksf.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    strong_base = bearing_capacity(
        theory="Meyerhof",
        c_kpa=3.2 * ksf_to_kpa,
        phi_deg=0.0,
        gamma_moist=0.125 * kcf_to_kn_m3,
        gamma_sub=9.0,
        gamma_below=0.125 * kcf_to_kn_m3,
        B=8.0 * ft_to_m,
        L=8.0 * ft_to_m,
        Df=2.5 * ft_to_m,
        water_depth=20.0 * ft_to_m,
        fs=3.0,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=strong_base,
        c_kpa=3.2 * ksf_to_kpa,
        phi_deg=0.0,
        horizontal_load=0.0,
        vertical_load=1.0,
    )
    assert result["sc"] == pytest.approx(1.2)
    assert result["dc"] == pytest.approx(1.0625)
    # Full precision uses dc=1.0625 and q0=0.3125; the manual rounds these
    # intermediate values to 1.06 and 0.31 before reporting qult=21.23 ksf (rounding difference about 0.054 ksf).
    expected_full_precision = 1.2 * 1.0625 * 3.2 * 5.14 + 0.3125
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(expected_full_precision, abs=1e-8)
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(21.23, abs=0.06)


def test_usace_2025_appendix_b5c_undrained_punch_through_bearing_capacity():
    # Appendix B, Example B-5, Table B-5c (printed pp. 319-320).
    # Strong Layer 1 su=3.2 ksf; weak Layer 2 su=0.6 ksf; Hs=8.5 ft.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    common = dict(
        theory="Meyerhof",
        phi_deg=0.0,
        gamma_moist=0.125 * kcf_to_kn_m3,
        gamma_sub=9.0,
        gamma_below=0.125 * kcf_to_kn_m3,
        B=8.0 * ft_to_m,
        L=8.0 * ft_to_m,
        Df=2.5 * ft_to_m,
        water_depth=20.0 * ft_to_m,
        fs=3.0,
    )
    strong_base = bearing_capacity(c_kpa=3.2 * ksf_to_kpa, **common)
    weak_base = bearing_capacity(c_kpa=0.6 * ksf_to_kpa, **common)
    strong = bearing_capacity_slope_base_corrections(
        base_result=strong_base,c_kpa=3.2 * ksf_to_kpa,phi_deg=0.0,
        horizontal_load=0.0,vertical_load=1.0)
    weak = bearing_capacity_slope_base_corrections(
        base_result=weak_base,c_kpa=0.6 * ksf_to_kpa,phi_deg=0.0,
        horizontal_load=0.0,vertical_load=1.0)
    result = layered_bearing_capacity_punching(
        q_ult_strong_kpa=strong["qu_gross"],
        q_ult_weak_kpa=weak["qu_gross"],
        strong_layer_thickness_m=8.5 * ft_to_m,
        footing_width_m=8.0 * ft_to_m,
        footing_length_m=8.0 * ft_to_m,
        footing_type="isolated",
    )
    assert weak["qu_gross"] / ksf_to_kpa == pytest.approx(4.23, abs=0.05)
    assert result["load_spread_factor"] == pytest.approx(4.25, abs=0.02)
    assert result["qult_kpa"] / ksf_to_kpa == pytest.approx(17.98, abs=0.10)
    assert result["controlling_mode"] == "強上層穿刺至弱下層控制"
    qeq_ksf = (300.0 + 24.0) / 64.0
    assert result["qult_kpa"] / ksf_to_kpa / qeq_ksf == pytest.approx(3.6, abs=0.1)


def test_usace_2025_appendix_b7a_drained_meyerhof_bearing_capacity():
    # Appendix B, Example B-7, Table B-7a (printed pp. 330-333).
    # 8 ft square footing, Df=2.5 ft, phi'=32 deg, gamma=0.125 kcf, no groundwater.
    ft_to_m = 0.3048
    ksf_to_kpa = 47.88025898
    kcf_to_kn_m3 = 157.087463
    base = bearing_capacity(
        theory="Meyerhof",
        c_kpa=0.0,
        phi_deg=32.0,
        gamma_moist=0.125 * kcf_to_kn_m3,
        gamma_sub=0.125 * kcf_to_kn_m3,
        gamma_below=0.125 * kcf_to_kn_m3,
        B=8.0 * ft_to_m,
        L=8.0 * ft_to_m,
        Df=2.5 * ft_to_m,
        water_depth=20.0 * ft_to_m,
        fs=3.0,
    )
    result = bearing_capacity_slope_base_corrections(
        base_result=base,
        c_kpa=0.0,
        phi_deg=32.0,
        horizontal_load=0.0,
        vertical_load=1.0,
    )
    assert result["N_flow"] == pytest.approx(3.26, abs=0.01)
    assert result["sq"] == pytest.approx(1.33, abs=0.01)
    assert result["dq"] == pytest.approx(1.06, abs=0.01)
    assert result["Ngamma"] == pytest.approx(21.9, abs=0.2)
    assert result["sg"] == pytest.approx(1.33, abs=0.01)
    assert result["dg"] == pytest.approx(1.06, abs=0.01)
    assert result["qu_gross"] / ksf_to_kpa == pytest.approx(25.5, abs=0.2)

    demand = bearing_pressure_safety_check(
        ultimate_bearing_kpa=result["qu_gross"],
        vertical_load_kN=424.0 * 4.448221615,
        footing_width_m=8.0 * ft_to_m,
        footing_length_m=8.0 * ft_to_m,
        footing_depth_m=2.5 * ft_to_m,
        water_depth_m=20.0 * ft_to_m,
        required_fs=3.0,
    )
    assert demand["qeq_gross_kpa"] / ksf_to_kpa == pytest.approx(6.63, abs=0.02)
    assert demand["FS_bearing"] == pytest.approx(3.8, abs=0.1)



def test_usace_2025_appendix_c7e_burland_burbidge_settlement_and_pressure_cap():
    # Appendix C, Example C-7, Table C-7e (printed pp. 386-387).
    # B=L=8 ft, N60 values 12/15/14 -> Nbar=14, q=3.31 tsf,
    # mean initial stress=0.35 tsf, preconsolidation stress=3.88 tsf,
    # Zi=Hs=6.13 ft, t=50 years; published settlement=1.2 in.
    ft_to_m = 0.3048
    tsf_to_kpa = 95.7605
    pressure = usace_settlement_design_pressure(
        gross_equivalent_pressure_kpa=3.31 * tsf_to_kpa,
        ultimate_bearing_kpa=25.5 * tsf_to_kpa,
        factor_of_safety=3.0,
    )
    assert pressure["capacity_pressure_limit_kpa"] / tsf_to_kpa == pytest.approx(8.5)
    assert pressure["design_pressure_kpa"] / tsf_to_kpa == pytest.approx(3.31)
    assert pressure["capacity_limit_governs"] is False

    result = burland_burbidge_2025_settlement(
        n60_average=14.0,
        width_m=8.0 * ft_to_m,
        length_m=8.0 * ft_to_m,
        gross_pressure_kpa=pressure["design_pressure_kpa"],
        initial_effective_stress_kpa=0.35 * tsf_to_kpa,
        preconsolidation_stress_kpa=3.88 * tsf_to_kpa,
        granular_layer_thickness_m=6.13 * ft_to_m,
        years=50.0,
        load_type="static",
        overconsolidated=True,
    )
    assert result["influence_depth_m"] == pytest.approx(6.13 * ft_to_m, abs=0.01)
    assert result["C1_shape"] == pytest.approx(1.0)
    assert result["C2_layer"] == pytest.approx(1.0)
    assert result["C3_time"] == pytest.approx(1.54, abs=0.01)
    assert result["regime"] == "超固結且未超過先期固結壓力"
    assert result["settlement_mm"] == pytest.approx(1.2 * 25.4, abs=0.6)



def test_usace_2025_dmt_settlement_converts_readings_and_sums_incremental_layers():
    # USACE EM 1110-1-1905 Eqs. 3-41, 4-13 to 4-15 and 7-10.
    # 4 m profile deliberately extends beyond the 2B minimum. USACE
    # Table 7-4 requires continuing when deeper layers still contribute.
    layers = [
        {"Layer": i + 1, "thickness_m": 0.2, "p0_bar": 2.0,
         "p1_bar": 3.0, "u0_bar": 0.5, "sigma_v0_eff_bar": 1.0}
        for i in range(20)
    ]
    result = dmt_settlement_2025(
        layers=layers, footing_width_m=1.0, footing_length_m=1.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
        ultimate_bearing_kpa=450.0, factor_of_safety=3.0,
    )
    first = result["layer_results"][0]
    expected_id = (3.0 - 2.0) / (2.0 - 0.5)
    expected_kd = (2.0 - 0.5) / 1.0
    expected_ed = 34.7 * (3.0 - 2.0)
    expected_rm = max(0.85, 0.14 + 0.15 * (expected_id - 0.6)
                      + (2.5 - (0.14 + 0.15 * (expected_id - 0.6)))
                      * math.log10(expected_kd))
    expected_mdmt = expected_rm * expected_ed * 100.0
    assert first["ID"] == pytest.approx(expected_id)
    assert first["KD"] == pytest.approx(expected_kd)
    assert first["ED_bar"] == pytest.approx(expected_ed)
    assert first["RM"] == pytest.approx(expected_rm)
    assert first["MDMT_kPa"] == pytest.approx(expected_mdmt)
    assert result["gross_pressure_used_kpa"] == pytest.approx(150.0)
    assert result["capacity_limit_governs"] is True
    assert result["net_pressure_increment_kpa"] == pytest.approx(100.0)
    expected_settlement = sum(
        boussinesq_rectangular_center_factor(1.0, 1.0, row["Depth_center_m"])
        * 100.0 / expected_mdmt * 0.2 * 1000.0
        for row in result["layer_results"]
    )
    assert result["settlement_mm"] == pytest.approx(expected_settlement)
    assert len(result["layer_results"]) == 20
    assert result["profile_depth_used_m"] == pytest.approx(4.0)
    assert result["profile_ends_at_minimum_depth"] is False


def test_usace_2025_dmt_settlement_rejects_incomplete_profile_and_bad_readings():
    short = [
        {"thickness_m": 0.2, "p0_bar": 2.0, "p1_bar": 3.0,
         "u0_bar": 0.5, "sigma_v0_eff_bar": 1.0}
    ]
    with pytest.raises(ValueError, match="不可外插"):
        dmt_settlement_2025(
            layers=short, footing_width_m=1.0, footing_length_m=1.0,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
        )
    bad = [
        {"thickness_m": 0.2, "p0_bar": 2.0, "p1_bar": 1.9,
         "u0_bar": 0.5, "sigma_v0_eff_bar": 1.0}
        for _ in range(10)
    ]
    with pytest.raises(ValueError, match="DMT 第 1 層"):
        dmt_settlement_2025(
            layers=bad, footing_width_m=1.0, footing_length_m=1.0,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
        )



def test_usace_2025_dmt_strip_footing_uses_infinite_strip_stress_solution():
    layers = [
        {"thickness_m": 0.2, "p0_bar": 2.0, "p1_bar": 3.0,
         "u0_bar": 0.5, "sigma_v0_eff_bar": 1.0}
        for _ in range(30)
    ]
    result = dmt_settlement_2025(
        layers=layers, footing_width_m=1.0, footing_length_m=10.1,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
        footing_type="continuous",
    )
    row = result["layer_results"][0]
    z = row["Depth_center_m"]
    a = 0.5
    expected = 2.0 / math.pi * (math.atan(a / z) + a * z / (a*a + z*z))
    assert row["Stress_factor_I_sigma"] == pytest.approx(expected)
    assert result["influence_depth_required_m"] == pytest.approx(6.0)
    assert result["profile_depth_used_m"] == pytest.approx(6.0)



def test_usace_2025_schmertmann_cpt_settlement_matches_equations_7_16_to_7_26():
    layers = [
        {"Layer": i + 1, "thickness_m": 0.25, "qc_kpa": 1000.0}
        for i in range(8)
    ]
    result = schmertmann_cpt_settlement_2025(
        layers=layers, footing_width_m=1.0, footing_length_m=1.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
        peak_effective_stress_kpa=100.0, years=50.0,
        ultimate_bearing_kpa=450.0, factor_of_safety=3.0,
        soil_applicability_confirmed=True,
    )
    qnet = 150.0 - 50.0
    expected_izp = 0.5 + 0.1 * math.sqrt(qnet / 100.0)
    expected_c1 = 1.0 - 0.5 * 50.0 / qnet
    expected_c2 = 1.0 + 0.2 * math.log10(50.0 / 0.1)
    assert result["gross_pressure_used_kpa"] == pytest.approx(150.0)
    assert result["Iz_peak"] == pytest.approx(expected_izp)
    assert result["C1_embedment"] == pytest.approx(expected_c1)
    assert result["C2_creep"] == pytest.approx(expected_c2)
    assert result["influence_depth_required_m"] == pytest.approx(2.0)
    assert result["capacity_limit_governs"] is True
    expected_sum = 0.0
    for row in result["layer_results"]:
        x = row["Depth_center_m"]
        iz = 0.1 + x * (2.0 * expected_izp - 0.2) if x <= 0.5 else (
            0.667 * expected_izp * (2.0 - x))
        expected_sum += iz * 0.25 / 2500.0
    expected_settlement = expected_c1 * expected_c2 * qnet * expected_sum * 1000.0
    assert result["settlement_mm"] == pytest.approx(expected_settlement)


def test_usace_2025_schmertmann_cpt_strip_influence_depth_and_profile_guard():
    layers = [
        {"thickness_m": 0.25, "qc_kpa": 1000.0}
        for _ in range(16)
    ]
    result = schmertmann_cpt_settlement_2025(
        layers=layers, footing_width_m=1.0, footing_length_m=10.1,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
        peak_effective_stress_kpa=100.0, footing_type="continuous",
        soil_applicability_confirmed=True,
    )
    assert result["influence_depth_required_m"] == pytest.approx(4.0)
    assert result["profile_depth_used_m"] == pytest.approx(4.0)
    assert result["layer_results"][0]["Es_kPa"] == pytest.approx(3500.0)
    with pytest.raises(ValueError, match="不可外插"):
        schmertmann_cpt_settlement_2025(
            layers=layers[:4], footing_width_m=1.0, footing_length_m=10.1,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
            peak_effective_stress_kpa=100.0, footing_type="continuous",
            soil_applicability_confirmed=True,
        )



@pytest.mark.parametrize(
    "application,disturbance,expected_phi,expected_c,expected_sigma_cm,expected_sigma_c_mass",
    [
        ("tunnel", 0.0, 47.16, 0.58, 7.80982, 2.24130),
        ("slope", 1.0, 27.61, 0.35, 2.83626, 0.47453),
    ],
)
def test_hoek_brown_2002_published_example_equivalent_mc_parameters(
    application, disturbance, expected_phi, expected_c,
    expected_sigma_cm, expected_sigma_c_mass
):
    # Hoek, Carranza-Torres & Corkum (2002), §7 example:
    # sigma_ci=50 MPa, mi=10, GSI=45, H=100 m, gamma=27 kN/m3.
    result = hoek_brown_parameters(
        gsi=45.0, mi=10.0, sigma_ci_mpa=50.0,
        disturbance=disturbance, application=application,
        gamma_rock_kn_m3=27.0, height_m=100.0,
    )
    assert result["phi_equiv_deg"] == pytest.approx(expected_phi, abs=0.02)
    assert result["c_equiv_mpa"] == pytest.approx(expected_c, abs=0.01)
    assert result["sigma_cm_mpa"] == pytest.approx(expected_sigma_cm, abs=1e-4)
    assert result["sigma_c_mass_mpa"] == pytest.approx(expected_sigma_c_mass, abs=1e-4)
    assert result["sigma_t_mass_mpa"] < 0.0

def test_usace_2025_menard_rousseau_pmt_settlement_equation_7_11():
    pmt = [
        {"group": "E1", "E0_kpa": 12000.0},
        {"group": "E2", "E0_kpa": 15000.0},
        {"group": "E345", "E0_kpa": 18000.0},
        {"group": "E678", "E0_kpa": 22000.0},
        {"group": "E916", "E0_kpa": 25000.0},
    ]
    result = menard_rousseau_pmt_settlement_2025(
        pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
        equivalent_net_limit_pressure_kpa=1500.0,
        yield_pressure_kpa=250.0,
        soil_type="sand", consolidation_state="normally_consolidated",
        round_footing=True, ultimate_bearing_kpa=450.0,
        deep_uniform_deposit_confirmed=True,
    )
    expected_ed = 4.0 / (
        1/12000.0 + 1/(0.85*15000.0) + 1/18000.0
        + 1/(2.5*22000.0) + 1/(2.5*25000.0)
    )
    assert result["E1_kpa"] == pytest.approx(12000.0)
    assert result["Ed_kpa"] == pytest.approx(expected_ed)
    assert result["Ec_kpa"] == pytest.approx(12000.0)
    assert result["alpha_d"] == pytest.approx(1/3)
    assert result["alpha_c"] == pytest.approx(1/3)
    assert result["gross_pressure_used_kpa"] == pytest.approx(150.0)
    assert result["capacity_limit_governs"] is True
    qnet = 50.0
    expected_dev = (2/(9*expected_ed))*qnet*0.6096*(1.0*2.0/0.6096)**(1/3)
    expected_sph = ((1/3)/(9*12000.0))*qnet*1.0*2.0
    assert result["deviatoric_settlement_mm"] == pytest.approx(expected_dev*1000)
    assert result["spherical_settlement_mm"] == pytest.approx(expected_sph*1000)
    assert result["settlement_mm"] == pytest.approx((expected_dev+expected_sph)*1000)


def test_usace_2025_menard_rousseau_pmt_rejects_out_of_table_alpha_and_soft_layer_claim():
    pmt = [
        {"group": group, "E0_kpa": value}
        for group, value in [
            ("E1", 12000.0), ("E2", 15000.0), ("E345", 18000.0),
            ("E678", 22000.0), ("E916", 25000.0),
        ]
    ]
    with pytest.raises(ValueError, match="深層且相對均質"):
        menard_rousseau_pmt_settlement_2025(
            pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
            equivalent_net_limit_pressure_kpa=2000.0,
        yield_pressure_kpa=250.0,
            round_footing=True,
        )
    with pytest.raises(ValueError, match="E/pne 適用範圍"):
        menard_rousseau_pmt_settlement_2025(
            pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
            equivalent_net_limit_pressure_kpa=100.0,
        yield_pressure_kpa=250.0,
            soil_type="sand", consolidation_state="normally_consolidated",
            round_footing=True, deep_uniform_deposit_confirmed=True,
        )



def test_usace_2025_menard_rousseau_pmt_soft_layer_eq_7_12():
    pmt = [
        {"group": "E1", "E0_kpa": 12000.0},
        {"group": "E2", "E0_kpa": 15000.0},
        {"group": "E345", "E0_kpa": 18000.0},
        {"group": "E678", "E0_kpa": 22000.0},
        {"group": "E916", "E0_kpa": 25000.0},
    ]
    soft = [
        {"Layer": "soft-1", "depth_center_m": 1.0, "thickness_m": 0.5,
         "E_L_kpa": 5000.0, "pne_kpa": 600.0}
    ]
    result = menard_rousseau_pmt_settlement_2025(
        pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
        equivalent_net_limit_pressure_kpa=1500.0,
        yield_pressure_kpa=250.0,
        soil_type="sand", consolidation_state="normally_consolidated",
        round_footing=True, soft_layers=soft, soft_layer_profile_reviewed=True,
    )
    Ed = result["Ed_kpa"]
    alphaL = 1.0 / 3.0
    Iz = boussinesq_rectangular_center_factor(2.0, 2.0, 1.0)
    expected = alphaL * (1.0/5000.0 - 1.0/Ed) * Iz * 100.0 * 0.5 * 1000.0
    assert result["soft_layer_settlement_mm"] == pytest.approx(expected)
    assert result["soft_layer_results"][0]["I_sigma"] == pytest.approx(Iz)
    assert result["settlement_mm"] == pytest.approx(
        result["deviatoric_settlement_mm"]
        + result["spherical_settlement_mm"]
        + expected
    )


def test_usace_2025_menard_rousseau_pmt_soft_layer_extends_beyond_2b_while_stress_is_significant():
    pmt = [
        {"group": group, "E0_kpa": value}
        for group, value in [
            ("E1", 12000.0), ("E2", 15000.0), ("E345", 18000.0),
            ("E678", 22000.0), ("E916", 25000.0),
        ]
    ]
    # For a 2 m square footing, the entire layer is below 2B.
    # At its centre (z=4.1 m), Boussinesq I_sigma remains > 0.10,
    # so USACE's significant-stress depth check requires it to be included.
    soft_layer = {"depth_center_m": 4.1, "thickness_m": 0.1,
                  "E_L_kpa": 5000.0, "pne_kpa": 600.0}
    result = menard_rousseau_pmt_settlement_2025(
        pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
        equivalent_net_limit_pressure_kpa=1500.0,
        yield_pressure_kpa=250.0,
        soil_type="sand", consolidation_state="normally_consolidated",
        round_footing=True, soft_layers=[soft_layer],
        soft_layer_profile_reviewed=True,
    )
    expected_iz = boussinesq_rectangular_center_factor(2.0, 2.0, 4.1)
    assert soft_layer["depth_center_m"] - soft_layer["thickness_m"] / 2.0 > 4.0
    assert expected_iz > 0.10
    assert result["soft_layer_results"][0]["I_sigma"] == pytest.approx(expected_iz)
    assert result["soft_layer_settlement_mm"] > 0.0


def test_usace_2025_menard_rousseau_pmt_soft_layer_rejects_beyond_negligible_stress_depth():
    pmt = [
        {"group": group, "E0_kpa": value}
        for group, value in [
            ("E1", 12000.0), ("E2", 15000.0), ("E345", 18000.0),
            ("E678", 22000.0), ("E916", 25000.0),
        ]
    ]
    with pytest.raises(ValueError, match="I_sigma=.*<0.10"):
        menard_rousseau_pmt_settlement_2025(
            pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
            equivalent_net_limit_pressure_kpa=1500.0,
            yield_pressure_kpa=250.0,
            soil_type="sand", consolidation_state="normally_consolidated",
            round_footing=True,
            soft_layers=[{"depth_center_m": 5.0, "thickness_m": 0.5,
                          "E_L_kpa": 5000.0, "pne_kpa": 600.0}],
            soft_layer_profile_reviewed=True,
        )



def test_usace_2025_menard_pmt_weathered_clay_alpha_uses_table_7_6_range():
    pmt = [
        {"group": group, "E0_kpa": 12000.0}
        for group in ("E1", "E2", "E345", "E678", "E916")
    ]
    result = menard_rousseau_pmt_settlement_2025(
        pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
        equivalent_net_limit_pressure_kpa=1500.0,
        yield_pressure_kpa=250.0,
        soil_type="clay", consolidation_state="weathered_remolded",
        round_footing=True, deep_uniform_deposit_confirmed=True,
    )
    assert result["alpha_d"] == pytest.approx(0.5)
    assert result["alpha_c"] == pytest.approx(0.5)
    with pytest.raises(ValueError, match="weathered/remolded clay"):
        menard_rousseau_pmt_settlement_2025(
            pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
            equivalent_net_limit_pressure_kpa=1000.0,
        yield_pressure_kpa=250.0,
            soil_type="clay", consolidation_state="weathered_remolded",
            round_footing=True, deep_uniform_deposit_confirmed=True,
        )



def test_usace_2025_menard_pmt_rejects_design_pressure_above_yield_pressure():
    pmt = [
        {"group": group, "E0_kpa": 12000.0}
        for group in ("E1", "E2", "E345", "E678", "E916")
    ]
    with pytest.raises(ValueError, match="超過 PMT 屈服壓力 Py"):
        menard_rousseau_pmt_settlement_2025(
            pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
            gross_pressure_kpa=300.0, base_effective_stress_kpa=100.0,
            equivalent_net_limit_pressure_kpa=1500.0,
            yield_pressure_kpa=250.0,
            soil_type="sand", consolidation_state="normally_consolidated",
            round_footing=True, deep_uniform_deposit_confirmed=True,
        )




def test_usace_2025_menard_pmt_checks_applied_pressure_before_capacity_cap():
    pmt = [
        {"group": group, "E0_kpa": 12000.0}
        for group in ("E1", "E2", "E345", "E678", "E916")
    ]
    # q=300 kPa exceeds Py=250 kPa, even though qult/FS=150 kPa.
    # Table 7-5 Step 1 must check the applied pressure before Step 4's cap.
    with pytest.raises(ValueError, match="實際輸入 gross q／qeq=300.0 kPa 超過 PMT 屈服壓力"):
        menard_rousseau_pmt_settlement_2025(
            pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
            gross_pressure_kpa=300.0, base_effective_stress_kpa=100.0,
            equivalent_net_limit_pressure_kpa=1500.0,
            yield_pressure_kpa=250.0,
            soil_type="sand", consolidation_state="normally_consolidated",
            round_footing=True, ultimate_bearing_kpa=450.0,
            factor_of_safety=3.0, deep_uniform_deposit_confirmed=True,
        )


def test_usace_2025_appendix_c7b_dmt_modulus_settlement_table_rows():
    # Appendix C-7b, Table C-7a/C-7b (printed pp. 377-380).
    # The manual's row settlements sum to about 0.344 in; its printed total
    # says 0.034 in, a factor-of-ten arithmetic/transcription discrepancy.
    ft = 0.3048
    tsf = 95.7605
    data = [
        (0.7,0.7,769,.998),(1.3,.6,770,.984),(2.0,.7,920,.941),
        (2.6,.6,158,.882),(3.3,.7,717,.796),(3.9,.6,917,.718),
        (4.6,.7,898,.629),(5.2,.6,985,.559),(5.9,.7,2264,.486),
        (6.6,.7,2132,.423),(7.2,.6,2266,.377),(7.9,.7,1487,.331),
        (8.5,.6,1740,.297),(9.2,.7,1760,.263),(9.8,.6,2138,.238),
        (10.5,.7,2220,.212),(11.2,.7,2212,.190),(11.8,.6,2284,.174),
        (12.5,.7,2134,.158),(13.1,.6,2076,.145),(13.8,.7,2583,.132),
        (14.4,.6,2357,.123),(15.1,.7,2343,.113),(15.7,.6,1842,.105),
        (16.4,.7,1570,.097),
    ]
    layers = [
        {"Layer": i+1, "depth_center_m": (z-h/2.0)*ft, "thickness_m": h*ft,
         "MDMT_kpa": M*tsf, "I_sigma": Iz}
        for i,(z,h,M,Iz) in enumerate(data)
    ]
    result = dmt_modulus_settlement_2025(
        layers=layers,footing_width_m=8*ft,footing_length_m=8*ft,
        gross_pressure_kpa=3.31*tsf,base_effective_stress_kpa=.156*tsf,
        ultimate_bearing_kpa=25.5*47.88025898,factor_of_safety=3.0,
    )
    assert result["gross_pressure_used_kpa"] == pytest.approx(3.31*tsf)
    assert result["layer_results"][0]["Stress_factor_I_sigma"] == pytest.approx(.998)
    assert result["profile_depth_used_m"] >= 16*ft
    assert result["settlement_mm"] / 25.4 == pytest.approx(.3437,abs=.002)


def test_usace_2025_appendix_c7c_menard_rousseau_pmt_settlement():
    # Appendix C-7c, Table C-7a/C-7c (printed pp. 377, 381-382).
    ft = 0.3048
    tsf = 95.7605
    pmt = [
        {"group":"E1","E0_kpa":78*tsf},
        {"group":"E2","E0_kpa":78*tsf}, {"group":"E2","E0_kpa":238*tsf},
        {"group":"E345","E0_kpa":238*tsf}, {"group":"E345","E0_kpa":320*tsf}, {"group":"E345","E0_kpa":826*tsf},
        {"group":"E678","E0_kpa":1419*tsf}, {"group":"E678","E0_kpa":1065*tsf},
        {"group":"E916","E0_kpa":2508*tsf}, {"group":"E916","E0_kpa":1059*tsf}, {"group":"E916","E0_kpa":1128*tsf},
    ]
    result = menard_rousseau_pmt_settlement_2025(
        pmt_moduli=pmt,footing_width_m=8*ft,footing_length_m=8*ft,
        gross_pressure_kpa=3.31*tsf,base_effective_stress_kpa=.156*tsf,
        equivalent_net_limit_pressure_kpa=8.5*tsf,
        yield_pressure_kpa=3.31*tsf,
        soil_type="sand",consolidation_state="auto",
        lambda_d=1.1,lambda_c=1.1,deep_uniform_deposit_confirmed=True,
    )
    assert result["E1_kpa"]/tsf == pytest.approx(78.0)
    assert result["E2_kpa"]/tsf == pytest.approx(117.494,abs=.002)
    assert result["E345_kpa"]/tsf == pytest.approx(351.398,abs=.002)
    assert result["E678_kpa"]/tsf == pytest.approx(1216.775,abs=.002)
    assert result["E916_kpa"]/tsf == pytest.approx(1345.571,abs=.002)
    assert result["Ed_kpa"]/tsf == pytest.approx(152.060,abs=.002)
    assert result["alpha_d"] == pytest.approx(.5)
    assert result["alpha_c"] == pytest.approx(1/3)
    assert result["settlement_mm"]/25.4 == pytest.approx(.38,abs=.02)


def test_usace_2025_appendix_c7d_schmertmann_cpt_settlement_table_rows():
    # Appendix C-7d, Table C-7d (printed pp. 384-385).
    # The printed row values sum to Σ(Iz H/Es)=0.0194 ft^3/ton, not the
    # printed 0.0266; the row-by-row equation result is about 1.10 in,
    # not the printed final 1.5 in. We preserve the row data and equation.
    ft = 0.3048
    tsf = 95.7605
    data = [
        (1.5,100,.227),(1.0,100,.439),(1.5,160,.651),
        (3.5,100,.665),(2.0,300,.489),(3.0,160,.324),(3.5,200,.114),
    ]
    layers = [
        {"Layer":i+1,"thickness_m":H*ft,"qc_kpa":qc*tsf}
        for i,(H,qc,Iz) in enumerate(data)
    ]
    result = schmertmann_cpt_settlement_2025(
        layers=layers,footing_width_m=8*ft,footing_length_m=8*ft,
        gross_pressure_kpa=3.31*tsf,base_effective_stress_kpa=.156*tsf,
        peak_effective_stress_kpa=.40625*tsf,years=50.0,
        ultimate_bearing_kpa=25.5*2*47.88025898,factor_of_safety=3.0,
        soil_applicability_confirmed=True,
    )
    assert result["Iz_peak"] == pytest.approx(.779,abs=.001)
    assert result["C1_embedment"] == pytest.approx(.975,abs=.001)
    assert result["C2_creep"] == pytest.approx(1.539,abs=.001)
    assert result["layer_results"][0]["Iz_used"] == pytest.approx(.227,abs=.001)
    assert result["layer_results"][3]["Iz_used"] == pytest.approx(.665,abs=.001)
    assert result["settlement_mm"]/25.4 == pytest.approx(1.10,abs=.02)



def test_usace_2025_appendix_c5_menard_pmt_clay_soft_layer_settlement():
    # Appendix C-5, Table C-5 (printed pp. 364-367): 8-ft square footing.
    ft = 0.3048
    tsf = 95.7605
    pmt = [
        {"group":"E1","E0_kpa":225*tsf},
        {"group":"E2","E0_kpa":225*tsf},{"group":"E2","E0_kpa":292*tsf},
        *[{"group":"E345","E0_kpa":x*tsf} for x in (292,394,25,33,52,349,287)],
        *[{"group":"E678","E0_kpa":x*tsf} for x in (287,678,1071)],
        *[{"group":"E916","E0_kpa":x*tsf} for x in (1220,1724)],
    ]
    soft = [{
        "Layer":"C5-soft-clay", "depth_center_m":14*ft, "thickness_m":4*ft,
        "E_L_kpa":33.5*tsf, "pne_kpa":3.01*tsf, "I_sigma":0.129,
    }]
    result = menard_rousseau_pmt_settlement_2025(
        pmt_moduli=pmt,footing_width_m=8*ft,footing_length_m=8*ft,
        gross_pressure_kpa=2.53*tsf,base_effective_stress_kpa=.156*tsf,
        equivalent_net_limit_pressure_kpa=10.0*tsf,yield_pressure_kpa=2.53*tsf,
        soil_type="clay",consolidation_state="auto",
        lambda_d=1.1,lambda_c=1.1,soft_layers=soft,soft_layer_profile_reviewed=True,
    )
    assert result["E1_kpa"]/tsf == pytest.approx(225.0)
    assert result["E2_kpa"]/tsf == pytest.approx(254.16,abs=.02)
    assert result["E345_kpa"]/tsf == pytest.approx(68.73,abs=.02)
    assert result["E678_kpa"]/tsf == pytest.approx(509.08,abs=.02)
    assert result["E916_kpa"]/tsf == pytest.approx(1428.86,abs=.02)
    assert result["Ed_kpa"]/tsf == pytest.approx(162.02,abs=.02)
    assert result["alpha_d"] == pytest.approx(1.0)
    assert result["alpha_c"] == pytest.approx(1.0)
    assert result["soft_layer_results"][0]["alpha_L"] == pytest.approx(2/3)
    assert result["deviatoric_settlement_mm"]/25.4 == pytest.approx(.029*12,abs=.01)
    assert result["soft_layer_settlement_mm"]/25.4 == pytest.approx(.232,abs=.003)
    assert result["settlement_mm"]/25.4 == pytest.approx(.70,abs=.01)



def test_usace_2025_appendix_c6b_dmt_mixed_soil_profile():
    # Appendix C-6b, Table C-6a/C-6b (printed pp. 368-373).
    # The 46 displayed layer settlements sum to 0.812 in after table rounding.
    # Recalculation from unrounded inputs gives 0.8266 in; the printed
    # total of 0.081 in is therefore a factor-of-ten transcription error.
    ft = 0.3048
    tsf = 95.7605
    data = [
        (.7,.7,769,.998),(1.6,.9,770,.969),(2.3,.7,920,.914),(3.0,.7,158,.834),
        (3.6,.6,717,.757),(4.3,.7,917,.666),(4.9,.6,898,.593),(5.6,.7,985,.516),
        (6.2,.6,2264,.458),(6.9,.7,2132,.399),(7.5,.6,1559,.356),(8.2,.7,1457,.313),
        (8.9,.7,1115,.277),(9.5,.6,789,.250),(10.2,.7,858,.223),(10.8,.6,858,.202),
        (11.5,.7,459,.182),(12.1,.6,412,.167),(12.8,.7,1059,.151),(13.4,.6,517,.139),
        (14.1,.7,72,.127),(14.8,.7,58,.117),(15.4,.6,29,.109),(16.1,.7,39,.100),
        (16.7,.6,61,.094),(17.4,.7,48,.087),(18.0,.6,45,.081),(18.7,.7,70,.076),
        (19.4,.7,88,.071),(20.0,.6,115,.067),(20.7,.7,167,.062),(21.3,.6,138,.059),
        (22.0,.7,78,.056),(22.6,.6,190,.053),(23.3,.7,135,.050),(23.9,.6,199,.047),
        (24.6,.7,179,.045),(25.3,.7,40,.043),(25.9,.6,35,.041),(26.6,.7,122,.039),
        (27.2,.6,55,.037),(27.9,.7,39,.035),(28.5,.6,38,.034),(29.2,.7,31,.032),
        (29.8,.6,33,.031),(30.5,.7,32,.030),
    ]
    layers = [
        {"Layer":i+1,"depth_center_m":(z-H/2.0)*ft,"thickness_m":H*ft,
         "MDMT_kpa":M*tsf,"I_sigma":Iz}
        for i,(z,H,M,Iz) in enumerate(data)
    ]
    result = dmt_modulus_settlement_2025(
        layers=layers,footing_width_m=8*ft,footing_length_m=8*ft,
        gross_pressure_kpa=2.53*tsf,base_effective_stress_kpa=.15*tsf,
    )
    expected_in = sum((2.53-.15)*Iz*H/M*12 for z,H,M,Iz in data)
    displayed_layer_settlements_in = [
        .026,.032,.020,.104,.018,.014,.011,.010,.003,.004,
        .004,.004,.005,.005,.005,.004,.008,.007,.003,.005,
        .035,.040,.063,.050,.026,
        .035,.030,.021,.016,.010,.007,.007,.014,.005,.007,
        .004,.005,.021,.020,.006,.011,.018,.015,.020,.016,.018,
    ]
    assert len(result["layer_results"]) == len(data) == len(displayed_layer_settlements_in) == 46
    assert sum(displayed_layer_settlements_in) == pytest.approx(0.812, abs=1e-9)
    assert expected_in / 0.081 > 10.0
    assert result["layer_results"][0]["Stress_factor_I_sigma"] == pytest.approx(.998)
    assert result["profile_depth_used_m"] > 30*ft
    assert result["settlement_mm"]/25.4 == pytest.approx(expected_in,abs=1e-6)
    assert result["settlement_mm"]/25.4 == pytest.approx(.827,abs=.002)



def test_spt_field_corrections_apply_to_cohesive_soil_but_cn_does_not():
    # USACE EM 1110-1-1905 (2025), Eqs. 4-4a/4-4b and Table 4-6:
    # field procedure corrections apply to both soil behaviors; cohesive CB=1.
    result = spt_correct(
        12.0, 75.0, 1.15, 1.20, 5.0, 50.0,
        "Skempton", 2.0, soil_behavior="cohesive",
    )
    expected_n60 = 12.0 * (75.0 / 60.0) * 1.0 * 1.20 * 0.85
    assert result["CE"] == pytest.approx(1.25)
    assert result["CB_input"] == pytest.approx(1.15)
    assert result["CB"] == pytest.approx(1.0)
    assert result["CR"] == pytest.approx(0.85)
    assert result["CS"] == pytest.approx(1.20)
    assert result["N60"] == pytest.approx(expected_n60)
    assert result["CN"] == pytest.approx(1.0)
    assert result["N1_60"] == pytest.approx(expected_n60)


@pytest.mark.parametrize(
    ("method", "cap", "expected_cn"),
    [
        ("Liao & Whitman", 2.0, 2.0),
        ("Seed & Idriss", 2.0, 1.7),
        ("Skempton", 2.0, 1.6),
    ],
)
def test_spt_overburden_correction_methods_and_caps(method, cap, expected_cn):
    # Pa=101.3 kPa; sigma'v=25.325 kPa. L&W/Seed use sqrt(Pa/sigma');
    # Skempton uses 2/(1+sigma'/Pa). Seed & Idriss cap is 1.7.
    result = spt_correct(
        10.0, 60.0, 1.0, 1.0, 10.0, 25.325,
        method, cap, soil_behavior="cohesionless",
    )
    assert result["N60"] == pytest.approx(10.0)
    assert result["CN_raw"] == pytest.approx(
        2.0 if method != "Skempton" else 1.6
    )
    assert result["CN"] == pytest.approx(expected_cn)
    assert result["N1_60"] == pytest.approx(10.0 * expected_cn)


def test_spt_profile_uses_per_row_rod_length_and_preserves_refusal_rows():
    from geolysis_engine import spt_profile

    rows = [
        {"Depth_m": 3.0, "N": 50, "Effective_Stress_kPa": 101.3,
         "Refusal": "true", "Penetration_mm": 80},
        {"Depth_m": 2.0, "N": 10, "Effective_Stress_kPa": 101.3,
         "Rod_Length_m": 2.0, "Refusal": "false"},
    ]
    result = spt_profile(
        rows, energy_ratio_pct=60, borehole_factor=1.0,
        sampler_factor=1.0, rod_length_m=10.0,
        cn_method="Liao & Whitman", soil_behavior="cohesionless",
    )
    assert [row["Depth_m"] for row in result] == [2.0, 3.0]
    assert result[0]["CR"] == pytest.approx(0.75)
    assert result[0]["N60"] == pytest.approx(7.5)
    assert result[1]["N60"] is None
    assert "拒錘" in result[1]["Correction_status"]



@pytest.mark.parametrize("refusal_value", [
    "refusal", "partial penetration", "拒錘", "拒打", "拒貫", "部分貫入",
])
def test_spt_profile_accepts_common_refusal_field_terms(refusal_value):
    from geolysis_engine import spt_profile

    result = spt_profile(
        [{"Depth_m": 1.0, "N": 50, "Effective_Stress_kPa": 100.0,
          "Refusal": refusal_value, "Penetration_mm": 80}],
        energy_ratio_pct=60.0, borehole_factor=1.0, sampler_factor=1.0,
        rod_length_m=5.0, cn_method="Liao & Whitman",
    )
    assert len(result) == 1
    assert result[0]["N60"] is None
    assert result[0]["N1_60_final"] is None
    assert "拒錘" in result[0]["Correction_status"]


def test_spt_profile_does_not_accept_refusal_words_as_dilatancy_boolean():
    from geolysis_engine import spt_profile

    with pytest.raises(ValueError, match="Apply_Dilatancy"):
        spt_profile(
            [{"Depth_m": 1.0, "N": 20, "Effective_Stress_kPa": 100.0,
              "Soil_Behavior": "cohesionless", "Apply_Dilatancy": "拒錘"}],
            energy_ratio_pct=60.0, borehole_factor=1.0, sampler_factor=1.0,
            rod_length_m=5.0, cn_method="Liao & Whitman",
        )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"p4": 40, "p10": 25, "p40": 10, "p200": 2,
          "ll": 25, "pl": 20, "d10": 0.1, "d30": 0.3, "d60": 0.6}, "GW"),
        ({"p4": 40, "p10": 25, "p40": 10, "p200": 2,
          "ll": 25, "pl": 20, "d10": 0.1, "d30": 0.1, "d60": 0.6}, "GP"),
        ({"p4": 95, "p10": 80, "p40": 60, "p200": 2,
          "ll": 25, "pl": 20, "d10": 0.1, "d30": 0.3, "d60": 0.8}, "SW"),
        ({"p4": 95, "p10": 80, "p40": 60, "p200": 2,
          "ll": 25, "pl": 20, "d10": 0.1, "d30": 0.1, "d60": 0.8}, "SP"),
        ({"p4": 95, "p10": 80, "p40": 60, "p200": 20,
          "ll": 35, "pl": 30, "d10": 0.1, "d30": 0.3, "d60": 0.8}, "SM"),
        ({"p4": 95, "p10": 80, "p40": 60, "p200": 20,
          "ll": 35, "pl": 15, "d10": 0.1, "d30": 0.3, "d60": 0.8}, "SC"),
        ({"p4": 95, "p10": 90, "p40": 80, "p200": 70,
          "ll": 35, "pl": 15}, "CL"),
        ({"p4": 95, "p10": 90, "p40": 80, "p200": 70,
          "ll": 35, "pl": 31}, "ML"),
        ({"p4": 95, "p10": 90, "p40": 80, "p200": 70,
          "ll": 60, "pl": 30}, "CH"),
        ({"p4": 95, "p10": 90, "p40": 80, "p200": 70,
          "ll": 60, "pl": 55}, "MH"),
        ({"peat": True}, "PT"),
    ],
)
def test_uscs_major_group_symbols_match_astm_d2487_criteria(kwargs, expected):
    result = classify_uscs_aashto(**kwargs)
    assert result["USCS"] == expected


@pytest.mark.parametrize(
    ("fines", "p10", "p40", "ll", "pi", "expected"),
    [
        (10, 40, 20, 25, 5, "A-1-a"),
        (20, 60, 40, 30, 5, "A-1-b"),
        (5, 80, 60, 30, 0, "A-3"),
        (20, 80, 60, 35, 5, "A-2-4"),
        (20, 80, 60, 50, 5, "A-2-5"),
        (20, 80, 60, 35, 15, "A-2-6"),
        (20, 80, 60, 50, 20, "A-2-7"),
        (50, 80, 60, 35, 10, "A-4"),
        (50, 80, 60, 50, 10, "A-5"),
        (50, 80, 60, 35, 20, "A-6"),
        (50, 80, 60, 60, 20, "A-7-5"),
        (50, 80, 60, 60, 40, "A-7-6"),
    ],
)
def test_aashto_m145_group_boundaries(fines, p10, p40, ll, pi, expected):
    # AASHTO M 145 Table 1: representative group/subgroup limits.
    result = classify_uscs_aashto(
        p4=95, p10=p10, p40=p40, p200=fines,
        ll=ll, pl=ll-pi, np_flag=(pi == 0),
    )
    assert result["AASHTO"] == expected



@pytest.mark.parametrize(
    ("second_center", "expected_message"),
    [
        (1.60, "空缺"),
        (1.40, "重疊或順序錯誤"),
    ],
)
def test_usace_2025_dmt_direct_mdmt_profile_rejects_gaps_and_overlaps(
    second_center, expected_message
):
    # Each layer has H=1 m. First layer covers 0–1 m; the second must start at 1 m.
    layers = [
        {"Layer": 1, "depth_center_m": 0.5, "thickness_m": 1.0,
         "MDMT_kpa": 10000.0},
        {"Layer": 2, "depth_center_m": second_center, "thickness_m": 1.0,
         "MDMT_kpa": 12000.0},
    ]
    with pytest.raises(ValueError, match=expected_message):
        dmt_modulus_settlement_2025(
            layers=layers, footing_width_m=1.0, footing_length_m=1.0,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
        )


def test_usace_2025_dmt_direct_mdmt_profile_must_start_at_footing_base():
    layers = [
        {"Layer": i + 1, "depth_center_m": 0.6 + i,
         "thickness_m": 1.0, "MDMT_kpa": 10000.0}
        for i in range(2)
    ]
    with pytest.raises(ValueError, match="空缺"):
        dmt_modulus_settlement_2025(
            layers=layers, footing_width_m=1.0, footing_length_m=1.0,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
        )



@pytest.mark.parametrize("method", ["pmt", "cpt", "dmt_mdmt", "dmt_readings"])
def test_usace_2025_settlement_methods_reject_fs_not_greater_than_one(method):
    with pytest.raises(ValueError, match="FS 必須大於 1.0"):
        if method == "pmt":
            menard_rousseau_pmt_settlement_2025(
                pmt_moduli=[
                    {"group": group, "E0_kpa": 12000.0}
                    for group in ("E1", "E2", "E345", "E678", "E916")
                ],
                footing_width_m=2.0, footing_length_m=2.0,
                gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
                equivalent_net_limit_pressure_kpa=1100.0,
                yield_pressure_kpa=300.0, factor_of_safety=1.0,
                round_footing=True, deep_uniform_deposit_confirmed=True,
            )
        elif method == "cpt":
            schmertmann_cpt_settlement_2025(
                layers=[{"thickness_m": 1.0, "qc_kpa": 1000.0}],
                footing_width_m=1.0, footing_length_m=1.0,
                gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
                peak_effective_stress_kpa=100.0, factor_of_safety=1.0,
            )
        elif method == "dmt_mdmt":
            dmt_modulus_settlement_2025(
                layers=[{"thickness_m": 1.0, "depth_center_m": 0.5, "MDMT_kpa": 10000.0},
                        {"thickness_m": 1.0, "depth_center_m": 1.5, "MDMT_kpa": 10000.0}],
                footing_width_m=1.0, footing_length_m=1.0,
                gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
                factor_of_safety=1.0,
            )
        else:
            dmt_settlement_2025(
                layers=[{"thickness_m": 1.0, "p0_bar": 2.0, "p1_bar": 3.0, "u0_bar": 0.5, "sigma_v0_eff_bar": 1.0},
                        {"thickness_m": 1.0, "p0_bar": 2.0, "p1_bar": 3.0, "u0_bar": 0.5, "sigma_v0_eff_bar": 1.0}],
                footing_width_m=1.0, footing_length_m=1.0,
                gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
                factor_of_safety=1.0,
            )


def test_usace_settlement_pressure_reports_static_fs_compliance():
    compliant = usace_settlement_design_pressure(
        gross_equivalent_pressure_kpa=150.0,
        ultimate_bearing_kpa=600.0,
        factor_of_safety=3.0,
    )
    comparison_only = usace_settlement_design_pressure(
        gross_equivalent_pressure_kpa=150.0,
        ultimate_bearing_kpa=600.0,
        factor_of_safety=2.5,
    )
    assert compliant["minimum_usace_static_bearing_fs"] == pytest.approx(3.0)
    assert compliant["meets_usace_static_bearing_fs"] is True
    assert comparison_only["meets_usace_static_bearing_fs"] is False


def test_usace_2025_pmt_rejects_overlapping_soft_layer_intervals():
    pmt = [
        {"group": group, "E0_kpa": 12000.0}
        for group in ("E1", "E2", "E345", "E678", "E916")
    ]
    with pytest.raises(ValueError, match="軟弱層.*重疊"):
        menard_rousseau_pmt_settlement_2025(
            pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
            equivalent_net_limit_pressure_kpa=1100.0,
            yield_pressure_kpa=300.0, soil_type="sand",
            consolidation_state="normally_consolidated",
            round_footing=True, soft_layer_profile_reviewed=True,
            soft_layers=[
                {"Layer": 1, "thickness_m": 1.0, "depth_center_m": 1.5,
                 "E_L_kpa": 8000.0, "pne_kpa": 1000.0, "I_sigma": 0.5},
                {"Layer": 2, "thickness_m": 1.0, "depth_center_m": 1.8,
                 "E_L_kpa": 8000.0, "pne_kpa": 1000.0, "I_sigma": 0.5},
            ],
        )



def test_hoek_brown_2002_low_ucs_em_branch():
    # Hoek, Carranza-Torres & Corkum (2002), Eq. 11a:
    # Em=(1-D/2)*sqrt(sigma_ci/100)*10^((GSI-10)/40) GPa for sigma_ci<=100 MPa.
    gsi, mi, sigma_ci, D = 45.0, 10.0, 50.0, 0.5
    result = hoek_brown_parameters(
        gsi=gsi, mi=mi, sigma_ci_mpa=sigma_ci, disturbance=D,
        application="general", sigma3_custom_mpa=10.0,
    )
    expected = (1.0 - D / 2.0) * math.sqrt(sigma_ci / 100.0) * 10.0 ** ((gsi - 10.0) / 40.0)
    assert result["Em_gpa"] == pytest.approx(expected, rel=1e-12)


def test_hoek_brown_2002_em_formula_is_continuous_at_100_mpa():
    # Eq. 11a and 11b meet exactly at sigma_ci=100 MPa.
    gsi, D = 55.0, 0.4
    expected = (1.0 - D / 2.0) * 10.0 ** ((gsi - 10.0) / 40.0)
    result = hoek_brown_parameters(
        gsi=gsi, mi=12.0, sigma_ci_mpa=100.0, disturbance=D,
        application="general", sigma3_custom_mpa=5.0,
    )
    assert result["Em_gpa"] == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize(
    ("pi", "expected"),
    [(3.0, "ML"), (6.0, "CL-ML"), (8.0, "CL")],
)
def test_uscs_cl_ml_borderline_zone(pi, expected):
    result = classify_uscs_aashto(
        p4=95, p10=90, p40=80, p200=70,
        ll=25, pl=25-pi,
    )
    assert result["USCS"] == expected


@pytest.mark.parametrize(
    ("fines", "expected"),
    [(5.0, "SW-SM"), (12.0, "SW-SM"), (13.0, "SM")],
)
def test_uscs_fines_dual_symbol_cutoffs(fines, expected):
    result = classify_uscs_aashto(
        p4=95, p10=80, p40=60, p200=fines,
        ll=35, pl=30, d10=0.1, d30=0.3, d60=0.8,
    )
    assert result["USCS"] == expected


def test_uscs_organic_fines_requires_oven_dried_liquid_limit_confirmation():
    confirmed = classify_uscs_aashto(
        p4=95, p10=90, p40=80, p200=70,
        ll=40, pl=20, organic=True, ll_oven_dried=25,
    )
    not_confirmed = classify_uscs_aashto(
        p4=95, p10=90, p40=80, p200=70,
        ll=40, pl=20, organic=True, ll_oven_dried=32,
    )
    provisional = classify_uscs_aashto(
        p4=95, p10=90, p40=80, p200=70,
        ll=40, pl=20, organic=True,
    )
    assert confirmed["USCS"] == "OL"
    assert "符合" in confirmed["organic_note"]
    assert not_confirmed["USCS"] == "CL"
    assert "未達有機土判別條件" in not_confirmed["organic_note"]
    assert "暫定" in provisional["USCS"]



def test_hoek_brown_high_gsi_intact_massive_rock_is_not_applicable():
    boundary = hoek_brown_structure_applicability(gsi=75.0, structure_code="A")
    high = hoek_brown_structure_applicability(gsi=75.01, structure_code="A")
    assert boundary["applicable"] is True
    assert high["applicable"] is False
    assert "脆性剝落" in high["warning"]
    assert "不應使用 Hoek" in high["warning"]


def test_hoek_brown_high_gsi_blocky_rock_requires_brittle_failure_review():
    result = hoek_brown_structure_applicability(gsi=80.0, structure_code="B")
    assert result["applicable"] is True
    assert "脆性剝落" in result["warning"]
    assert "楔形" in result["warning"]


def test_hoek_brown_gsi_applicability_rejects_invalid_structure_code():
    with pytest.raises(ValueError, match="A–F"):
        hoek_brown_structure_applicability(gsi=50.0, structure_code="Z")



def test_burland_burbidge_fine_sand_dilatancy_corrects_raw_n60_before_mean():
    result = burland_burbidge_average_n60_from_profile(
        [
            {"Depth_below_base_m": 0.5, "N60": 25.0},
            {"Depth_below_base_m": 1.0, "N60": 10.0},
        ],
        width_m=1.0, granular_layer_thickness_m=5.0,
        fine_sand_saturated=True,
    )
    assert result["selected_profile"] == [
        (0.5, 25.0, 20.0),
        (1.0, 10.0, 10.0),
    ]
    assert result["N60_average"] == pytest.approx(15.0)
    assert "直接" not in result["adjustments"]
    assert "式 4-7" in result["adjustments"]


def test_burland_burbidge_gravel_adjustment_is_applied_per_test_before_mean():
    result = burland_burbidge_average_n60_from_profile(
        [
            {"Depth_below_base_m": 0.5, "N60": 10.0},
            {"Depth_below_base_m": 1.0, "N60": 20.0},
        ],
        width_m=1.0, granular_layer_thickness_m=5.0,
        gravel_adjustment=True,
    )
    assert result["selected_profile"] == [
        (0.5, 10.0, 12.5),
        (1.0, 20.0, 25.0),
    ]
    assert result["N60_average"] == pytest.approx(18.75)
    assert "×1.25" in result["adjustments"]


def test_burland_burbidge_cannot_apply_gravel_and_fine_sand_corrections_together():
    with pytest.raises(ValueError, match="不可同時套用"):
        burland_burbidge_average_n60_from_profile(
            [{"Depth_below_base_m": 0.5, "N60": 25.0}],
            width_m=1.0, granular_layer_thickness_m=5.0,
            gravel_adjustment=True, fine_sand_saturated=True,
        )



@pytest.mark.parametrize(
    ("ll", "pi", "expected"),
    [
        (20.0, 3.0, "ML"),
        (25.0, 3.9, "ML"),
        (20.0, 4.0, "CL-ML"),
        (25.0, 7.0, "CL-ML"),
        (25.0, 7.1, "CL"),
    ],
)
def test_uscs_astm_a_line_horizontal_lower_segment(ll, pi, expected):
    result = classify_uscs_aashto(
        p4=95, p10=90, p40=80, p200=70,
        ll=ll, pl=ll-pi,
    )
    assert result["USCS"] == expected
    assert result["A_line_PI"] == pytest.approx(4.0)


def test_uscs_astm_u_line_flags_points_above_or_left_for_retest():
    above = classify_uscs_aashto(
        p4=95, p10=90, p40=80, p200=70,
        ll=30.0, pl=10.0,
    )
    left = classify_uscs_aashto(
        p4=95, p10=90, p40=80, p200=70,
        ll=15.0, pl=11.0,
    )
    normal = classify_uscs_aashto(
        p4=95, p10=90, p40=80, p200=70,
        ll=30.0, pl=15.0,
    )
    assert above["plasticity_warning"] and "U-line" in above["plasticity_warning"]
    assert left["plasticity_warning"] and "左側" in left["plasticity_warning"]
    assert normal["plasticity_warning"] == ""
    assert above["U_line_PI"] == pytest.approx(19.8)



def test_uscs_peat_result_keeps_optional_plasticity_warning_fields():
    result = classify_uscs_aashto(peat=True)
    assert result["USCS"] == "PT"
    assert result["U_line_PI"] is None
    assert result["plasticity_warning"] == ""



def test_burland_burbidge_spt_profile_rejects_near_duplicate_depths():
    with pytest.raises(ValueError, match="不超過 1 mm"):
        burland_burbidge_average_n60_from_profile(
            [
                {"Depth_below_base_m": 0.5, "N60": 20.0},
                {"Depth_below_base_m": 0.5005, "N60": 22.0},
            ],
            width_m=1.0, granular_layer_thickness_m=5.0,
        )


def test_burland_burbidge_spt_profile_warns_when_only_one_point_influence_zone():
    result = burland_burbidge_average_n60_from_profile(
        [
            {"Depth_below_base_m": 0.5, "N60": 20.0},
            {"Depth_below_base_m": 1.5, "N60": 22.0},
        ],
        width_m=1.0, granular_layer_thickness_m=5.0,
    )
    assert result["selected_count"] == 1
    assert any("僅有 1 個有效" in warning for warning in result["data_quality_warnings"])


def test_burland_burbidge_spt_profile_warns_when_valid_data_do_not_reach_zi():
    result = burland_burbidge_average_n60_from_profile(
        [
            {"Depth_below_base_m": 0.5, "N60": 20.0},
            {"Depth_below_base_m": 0.9, "N60": 22.0},
        ],
        width_m=1.0, granular_layer_thickness_m=5.0,
    )
    assert result["profile_bottom_m"] == pytest.approx(0.9)
    assert any("未達影響深度" in warning for warning in result["data_quality_warnings"])



def test_usace_seismic_pore_pressure_method_requires_applicability_confirmations():
    with pytest.raises(ValueError, match="不液化／無循環剪力強度損失"):
        seismic_bearing_capacity_residual_pore_pressure(
            footing_type="spread", effective_unit_weight_kn_m3=18.0,
            effective_width_m=2.0, bearing_factor_ngamma=20.0,
            residual_excess_pore_pressure_ratio=0.2,
        )
    with pytest.raises(ValueError, match="部分剪力區模式必須提供"):
        seismic_bearing_capacity_residual_pore_pressure(
            footing_type="spread", effective_unit_weight_kn_m3=18.0,
            effective_width_m=2.0, bearing_factor_ngamma=20.0,
            residual_excess_pore_pressure_ratio=0.2,
            non_liquefiable_confirmed=True,
        )



@pytest.mark.parametrize(
    ("non_liquefiable_confirmed", "full_shear_zone_confirmed", "message"),
    [
        (False, True, "不液化／無循環剪力強度損失"),
        (True, False, "部分剪力區模式必須提供"),
    ],
)
def test_usace_seismic_cases_require_both_applicability_confirmations(
    non_liquefiable_confirmed, full_shear_zone_confirmed, message
):
    with pytest.raises(ValueError, match=message):
        seismic_bearing_capacity_residual_pore_pressure_cases(
            vertical_load_kN=1000.0, horizontal_load_kN=0.0,
            kh=0.2, kv=0.0, footing_type="spread",
            residual_excess_pore_pressure_ratio=0.2,
            c_kpa=0.0, phi_deg=30.0,
            gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
            B=2.0, L=3.0, Df=1.5, water_depth=5.0,
            non_liquefiable_confirmed=non_liquefiable_confirmed,
            full_shear_zone_confirmed=full_shear_zone_confirmed,
        )



def test_burland_loose_layer_depth_is_separate_from_total_granular_layer_thickness():
    result = burland_burbidge_average_n60_from_profile(
        [
            {"Depth_below_base_m": 0.5, "N60": 20.0},
            {"Depth_below_base_m": 1.0, "N60": 22.0},
            {"Depth_below_base_m": 3.0, "N60": 25.0},
        ],
        width_m=1.0, granular_layer_thickness_m=5.0,
        n_decreases_with_depth=True, loose_layer_thickness_m=0.8,
    )
    assert result["influence_depth_m"] == pytest.approx(0.8)
    assert result["selected_count"] == 1
    assert result["selected_profile"][0][0] == pytest.approx(0.5)


def test_burland_decreasing_n60_requires_separate_loose_layer_depth():
    with pytest.raises(ValueError, match="另輸入鬆弱層底深度"):
        burland_burbidge_average_n60_from_profile(
            [{"Depth_below_base_m": 0.5, "N60": 20.0}],
            width_m=1.0, granular_layer_thickness_m=5.0,
            n_decreases_with_depth=True,
        )


def test_burland_loose_layer_depth_cannot_exceed_total_granular_layer_thickness():
    with pytest.raises(ValueError, match="不得超過砂／礫層總厚度"):
        burland_burbidge_2025_settlement(
            n60_average=20.0, width_m=1.0, length_m=1.0,
            gross_pressure_kpa=150.0, initial_effective_stress_kpa=50.0,
            preconsolidation_stress_kpa=80.0,
            granular_layer_thickness_m=2.0,
            n_decreases_with_depth=True, loose_layer_thickness_m=2.5,
        )


def test_burland_settlement_uses_loose_layer_depth_for_zi_but_hs_for_c2():
    result = burland_burbidge_2025_settlement(
        n60_average=20.0, width_m=1.0, length_m=1.0,
        gross_pressure_kpa=150.0, initial_effective_stress_kpa=50.0,
        preconsolidation_stress_kpa=80.0,
        granular_layer_thickness_m=5.0,
        n_decreases_with_depth=True, loose_layer_thickness_m=0.8,
    )
    assert result["influence_depth_m"] == pytest.approx(0.8)
    assert result["C2_layer"] == pytest.approx(1.0)



@pytest.mark.parametrize(
    ("layer_ratio", "expected_c2"),
    [(0.5, 0.75), (1.0, 1.0), (1.5, 1.0), (2.0, 1.0)],
)
def test_burland_c2_only_reduces_when_granular_layer_is_thinner_than_zi(layer_ratio, expected_c2):
    zi_m = 1.43 * (1.0 / 0.3048) ** 0.7 * 0.3048
    result = burland_burbidge_2025_settlement(
        n60_average=20.0, width_m=1.0, length_m=1.0,
        gross_pressure_kpa=150.0, initial_effective_stress_kpa=50.0,
        preconsolidation_stress_kpa=80.0,
        granular_layer_thickness_m=layer_ratio * zi_m,
    )
    assert result["C2_layer"] == pytest.approx(expected_c2)



def test_spt_profile_applies_soil_behavior_and_dilatancy_per_depth():
    rows = [
        {"Depth_m": 1.0, "N": 20, "Effective_Stress_kPa": 100,
         "Soil_Behavior": "cohesionless", "Borehole_Factor": 1.05,
         "Apply_Dilatancy": False},
        {"Depth_m": 2.0, "N": 20, "Effective_Stress_kPa": 100,
         "Soil_Behavior": "cohesive", "Borehole_Factor": 1.15,
         "Apply_Dilatancy": False},
        {"Depth_m": 3.0, "N": 20, "Effective_Stress_kPa": 100,
         "Soil_Behavior": "cohesionless", "Apply_Dilatancy": True},
        {"Depth_m": 4.0, "N": 50, "Effective_Stress_kPa": 120,
         "Soil_Behavior": "cohesive", "Refusal": True},
    ]
    result = spt_profile(
        rows, energy_ratio_pct=60, borehole_factor=1.0,
        sampler_factor=1.0, rod_length_m=8.0,
        cn_method="Liao & Whitman", cn_cap=2.0,
        soil_behavior="cohesionless", apply_dilatancy=False,
    )
    sand, clay, dense_fines, refusal = result
    assert sand["CB"] == pytest.approx(1.05)
    assert sand["CN"] == pytest.approx(math.sqrt(101.3 / 100.0))
    assert sand["soil_behavior"] == "cohesionless"
    assert clay["CB"] == pytest.approx(1.0)
    assert clay["CB_input"] == pytest.approx(1.15)
    assert clay["CN"] == pytest.approx(1.0)
    assert clay["N1_60_final"] == pytest.approx(clay["N60"])
    assert dense_fines["dilatancy_applied"] is True
    assert dense_fines["N1_60_final"] == pytest.approx(
        15.0 + 0.5 * (dense_fines["N1_60"] - 15.0)
    )
    assert refusal["N60"] is None
    assert refusal["soil_behavior"] == "cohesive"


def test_spt_profile_rejects_invalid_layer_behavior_and_dilatancy_on_clay():
    base = {"Depth_m": 1.0, "N": 20, "Effective_Stress_kPa": 100}
    with pytest.raises(ValueError, match="Soil_Behavior"):
        spt_profile(
            [{**base, "Soil_Behavior": "sand"}],
            energy_ratio_pct=60, borehole_factor=1.0,
            sampler_factor=1.0, rod_length_m=8.0,
        )
    with pytest.raises(ValueError, match="膨脹修正"):
        spt_profile(
            [{**base, "Soil_Behavior": "cohesive", "Apply_Dilatancy": True}],
            energy_ratio_pct=60, borehole_factor=1.0,
            sampler_factor=1.0, rod_length_m=8.0,
        )


def test_spt_profile_uses_global_defaults_when_layer_overrides_are_blank():
    result = spt_profile(
        [{"Depth_m": 1.0, "N": 20, "Effective_Stress_kPa": 100,
          "Soil_Behavior": "", "Apply_Dilatancy": ""}],
        energy_ratio_pct=60, borehole_factor=1.15,
        sampler_factor=1.1, rod_length_m=8.0,
        soil_behavior="cohesive", apply_dilatancy=True,
    )[0]
    assert result["soil_behavior"] == "cohesive"
    assert result["CB"] == pytest.approx(1.0)
    assert result["CS"] == pytest.approx(1.1)
    assert result["CN"] == pytest.approx(1.0)
    assert result["dilatancy_applied"] is False



def test_burland_burbidge_applies_material_adjustments_per_spt_depth():
    profile = [
        {"Depth_below_base_m": 1.4, "N60": 12.0, "Burland_Material": "standard"},
        {"Depth_below_base_m": 0.5, "N60": 20.0, "Burland_Material": "fine_sand_silt_saturated"},
        {"Depth_below_base_m": 1.0, "N60": 24.0, "Burland_Material": "gravel_sandy_gravel"},
    ]
    result = burland_burbidge_average_n60_from_profile(
        profile, width_m=2.0, granular_layer_thickness_m=5.0,
    )
    assert result["selected_count"] == 3
    assert [row[0] for row in result["selected_profile"]] == pytest.approx([0.5, 1.0, 1.4])
    assert [row[2] for row in result["selected_profile"]] == pytest.approx([17.5, 30.0, 12.0])
    assert result["N60_average"] == pytest.approx((17.5 + 30.0 + 12.0) / 3.0)
    assert "飽和細砂／粉土" in result["selected_adjustments"][0]
    assert "礫土／砂礫土" in result["selected_adjustments"][1]
    assert "一般土層" in result["selected_adjustments"][2]


def test_burland_burbidge_row_material_requires_complete_labels_inside_zi():
    profile = [
        {"Depth_below_base_m": 0.5, "N60": 20.0, "Burland_Material": "standard"},
        {"Depth_below_base_m": 1.0, "N60": 24.0, "Burland_Material": ""},
    ]
    with pytest.raises(ValueError, match="未填 Burland_Material"):
        burland_burbidge_average_n60_from_profile(
            profile, width_m=1.0, granular_layer_thickness_m=5.0,
        )


def test_burland_burbidge_row_material_cannot_be_combined_with_global_adjustment():
    with pytest.raises(ValueError, match="關閉全剖面"):
        burland_burbidge_average_n60_from_profile(
            [{"Depth_below_base_m": 0.5, "N60": 20.0,
              "Burland_Material": "fine_sand_silt_saturated"}],
            width_m=1.0, granular_layer_thickness_m=5.0,
            fine_sand_saturated=True,
        )


def test_burland_burbidge_module3_link_preserves_row_material_tags():
    result = burland_burbidge_average_n60_from_ground_profile(
        [
            {"Depth_m": 1.0, "N60": 20.0, "Burland_Material": "fine_sand_silt_saturated"},
            {"Depth_m": 1.5, "N60": 24.0, "Burland_Material": "gravel_sandy_gravel"},
            {"Depth_m": 1.9, "N60": 12.0, "Burland_Material": "standard"},
        ],
        foundation_depth_m=0.5, width_m=2.0,
        granular_layer_thickness_m=5.0,
    )
    assert result["selected_count"] == 3
    assert [row[2] for row in result["selected_profile"]] == pytest.approx([17.5, 30.0, 12.0])



def test_usace_pmt_shape_factors_are_limited_to_figure_7_11():
    pmt = [
        {"group": group, "E0_kpa": value}
        for group, value in [
            ("E1", 12000.0), ("E2", 15000.0), ("E345", 18000.0),
            ("E678", 22000.0), ("E916", 25000.0),
        ]
    ]
    common = dict(
        pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=4.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
        equivalent_net_limit_pressure_kpa=1500.0, yield_pressure_kpa=250.0,
        soil_type="sand", consolidation_state="auto",
        deep_uniform_deposit_confirmed=True,
    )
    with pytest.raises(ValueError, match="Figure 7-11"):
        menard_rousseau_pmt_settlement_2025(
            **common, lambda_d=2.6, lambda_c=1.4,
        )
    with pytest.raises(ValueError, match="Figure 7-11"):
        menard_rousseau_pmt_settlement_2025(
            **common, lambda_d=1.1, lambda_c=1.6,
        )
    with pytest.raises(ValueError, match="λd 曲線高於 λc"):
        menard_rousseau_pmt_settlement_2025(
            **common, lambda_d=1.1, lambda_c=1.2,
        )



def test_schmertmann_cpt_requires_clean_young_normally_consolidated_sand_confirmation():
    layers = [{"thickness_m": 1.0, "qc_kpa": 8000.0},
              {"thickness_m": 1.0, "qc_kpa": 9000.0}]
    kwargs = dict(
        layers=layers, footing_width_m=1.0, footing_length_m=1.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
        peak_effective_stress_kpa=100.0,
    )
    with pytest.raises(ValueError, match="年輕（<100 年）、正常固結、潔淨矽砂"):
        schmertmann_cpt_settlement_2025(**kwargs)
    result = schmertmann_cpt_settlement_2025(
        **kwargs, soil_applicability_confirmed=True,
    )
    assert result["soil_applicability_confirmed"] is True



def test_usace_pmt_peat_requires_explicit_normally_consolidated_state():
    pmt = [
        {"group": group, "E0_kpa": value}
        for group, value in [
            ("E1", 12000.0), ("E2", 15000.0), ("E345", 18000.0),
            ("E678", 22000.0), ("E916", 25000.0),
        ]
    ]
    common = dict(
        pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
        equivalent_net_limit_pressure_kpa=1500.0, yield_pressure_kpa=250.0,
        soil_type="peat", round_footing=True,
        deep_uniform_deposit_confirmed=True,
    )
    with pytest.raises(ValueError, match="僅列正常固結泥炭"):
        menard_rousseau_pmt_settlement_2025(
            **common, consolidation_state="auto",
        )
    result = menard_rousseau_pmt_settlement_2025(
        **common, consolidation_state="normally_consolidated",
    )
    assert result["alpha_d"] == pytest.approx(1.0)
    assert result["alpha_c"] == pytest.approx(1.0)



@pytest.mark.parametrize(
    "rock_condition,expected_alpha",
    [
        ("extremely_fractured", 1.0/3.0),
        ("other", 0.5),
        ("slightly_fractured_or_extremely_weathered", 2.0/3.0),
    ],
)
def test_usace_pmt_rock_alpha_from_table_7_6(rock_condition, expected_alpha):
    pmt = [
        {"group": group, "E0_kpa": value}
        for group, value in [
            ("E1", 12000.0), ("E2", 15000.0), ("E345", 18000.0),
            ("E678", 22000.0), ("E916", 25000.0),
        ]
    ]
    result = menard_rousseau_pmt_settlement_2025(
        pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
        equivalent_net_limit_pressure_kpa=1500.0, yield_pressure_kpa=250.0,
        soil_type="rock", consolidation_state="auto",
        rock_condition=rock_condition, round_footing=True,
        deep_uniform_deposit_confirmed=True,
    )
    assert result["alpha_d"] == pytest.approx(expected_alpha)
    assert result["alpha_c"] == pytest.approx(expected_alpha)
    assert result["rock_condition"] == rock_condition


def test_usace_pmt_rock_requires_table_7_6_rock_classification():
    pmt = [
        {"group": group, "E0_kpa": value}
        for group, value in [
            ("E1", 12000.0), ("E2", 15000.0), ("E345", 18000.0),
            ("E678", 22000.0), ("E916", 25000.0),
        ]
    ]
    with pytest.raises(ValueError, match="岩石 PMT 須選"):
        menard_rousseau_pmt_settlement_2025(
            pmt_moduli=pmt, footing_width_m=2.0, footing_length_m=2.0,
            gross_pressure_kpa=200.0, base_effective_stress_kpa=100.0,
            equivalent_net_limit_pressure_kpa=1500.0, yield_pressure_kpa=250.0,
            soil_type="rock", round_footing=True,
            deep_uniform_deposit_confirmed=True,
        )



def test_usace_2025_appendix_c1_e_log_p_consolidation_settlement():
    # Appendix C-1, Table C-1 (printed pp. 339-341).
    ft = 0.3048
    tsf = 95.7605
    data = [
        (0.5,1.0,.15,.79,.44,1.0,.226,.024),
        (2.0,2.0,.24,.88,.40,.92,.226,.024),
        (4.0,2.0,.33,.97,.28,.63,.226,.024),
        (6.5,3.0,.40,1.04,.16,.36,.226,.024),
        (9.5,3.0,.49,5.89,.09,.20,.096,.012),
        (12.5,3.0,.59,5.99,.05,.12,.096,.012),
    ]
    # Table C-1 reports Cc/(1+e0)=0.113 for strata 1–4 and 0.048
    # for strata 5–6; with Cc=0.226/0.096, each gives e0=1.0.
    layers = [
        {"Layer":i+1,"Depth_center_m":z*ft,"Thickness_m":H*ft,
         "e0":1.0,"Cc":Cc,"Cr":Cr,"Sigma0_kPa":s0*tsf,
         "SigmaP_kPa":sp*tsf,"Stress_factor":Iz}
        for i,(z,H,s0,sp,ds,Iz,Cc,Cr) in enumerate(data)
    ]
    result = consolidation_settlement_layers(
        layers=layers,footing_width_m=7*ft,footing_length_m=7*ft,
        net_pressure_kpa=.438*tsf,stress_method="Boussinesq",
    )
    expected_ft = sum(
        H*((Cr/2.0)*math.log10((s0+.438*Iz)/s0) if s0+.438*Iz<=sp
           else (Cr/2.0)*math.log10(sp/s0)+(Cc/2.0)*math.log10((s0+.438*Iz)/sp))
        for z,H,s0,sp,ds,Iz,Cc,Cr in data
    )
    expected_layer_settlement_ft = [.0071,.0102,.0064,.0053,.0013,.0006]
    assert len(result["layer_results"]) == 6
    assert [row["Stress_factor"] for row in result["layer_results"]] == pytest.approx(
        [row[5] for row in data],abs=1e-9)
    # Verify the intermediate stress increments against the rounded Table C-1 rows.
    assert [row["Delta_sigma_kPa"]/tsf for row in result["layer_results"]] == pytest.approx(
        [row[4] for row in data],abs=.005)
    # Verify each published layer settlement, not only the final sum.
    assert [row["Settlement_mm"]/304.8 for row in result["layer_results"]] == pytest.approx(
        expected_layer_settlement_ft,abs=.00015)
    assert result["settlement_mm"]/304.8 == pytest.approx(expected_ft,abs=1e-9)
    assert result["settlement_mm"]/304.8 == pytest.approx(.03087,abs=.0001)
    assert result["settlement_mm"]/25.4 == pytest.approx(.37,abs=.01)


def test_usace_2025_appendix_c3c_consolidation_time_rate():
    # Appendix C-3c: U=70%, Tv=0.403, Hdr=25/2 ft, Cv=0.412 ft²/day.
    ft = 0.3048
    cv_m2_day = 0.412 * (0.3048**2)
    result = consolidation_time_rate(
        primary_settlement_mm=1.10*25.4,
        layer_thickness_m=25*ft,
        cv_m2_per_day=cv_m2_day,
        target_degree_percent=70.0,
        drainage="double",
    )
    assert result["time_factor_target"] == pytest.approx(.403,abs=.001)
    assert result["drainage_path_m"] == pytest.approx(12.5*ft)
    assert result["time_to_target_days"] == pytest.approx(152.8,abs=.5)


def test_consolidation_layer_stress_factor_must_be_between_zero_and_one():
    layers = [{
        "Depth_center_m": 1.0, "Thickness_m": 2.0, "e0": 0.8,
        "Cc": 0.3, "Cr": 0.05, "Sigma0_kPa": 100.0,
        "SigmaP_kPa": 150.0, "Stress_factor": 1.01,
    }]
    with pytest.raises(ValueError, match="Stress_factor 必須介於 0 與 1"):
        consolidation_settlement_layers(
            layers=layers, footing_width_m=2.0, footing_length_m=3.0,
            net_pressure_kpa=100.0,
        )



@pytest.mark.parametrize(
    ("angle_kwargs", "angle_name"),
    [
        ({"base_inclination_deg": 10.0}, "基底傾角"),
        ({"ground_inclination_deg": 10.0}, "地表坡角"),
    ],
)
def test_usace_seismic_pore_pressure_cases_reject_inclined_base_or_sloping_ground(
    angle_kwargs, angle_name
):
    # The current scalar Meyerhof inclination model does not resolve
    # reversed earthquake shear relative to an inclined base or slope.
    kwargs = dict(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        kh=0.2, kv=0.1, footing_type="spread",
        residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=5.0,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    kwargs.update(angle_kwargs)
    with pytest.raises(ValueError, match="僅支援水平基底與水平地表"):
        seismic_bearing_capacity_residual_pore_pressure_cases(**kwargs)



def test_usace_seismic_residual_cases_use_effective_seismic_weight_not_static_v():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=100.0,
        kh=0.2, kv=0.1, seismic_weight_kN=1200.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=5.0,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    assert result["seismic_weight_kN"] == pytest.approx(1200.0)
    assert [case["vertical_load_kN"] for case in result["cases"]] == pytest.approx([880.0, 1120.0, 880.0, 1120.0])
    assert [case["horizontal_load_kN"] for case in result["cases"]] == pytest.approx([140.0, 140.0, 340.0, 340.0])
    assert [case["horizontal_earthquake_sign"] for case in result["cases"]] == [-1, -1, 1, 1]
    assert result["governing_case"]["vertical_sign"] == "向下減少"


def test_usace_seismic_pore_pressure_cases_include_reversed_seismic_moment_and_vertical_signs():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=100.0,
        kh=0.2, kv=0.1, seismic_weight_kN=1200.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=5.0,
        eccentricity_B=0.05, seismic_moment_B_kNm=50.0,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    assert len(result["cases"]) == 4
    by_sign = {(case["horizontal_earthquake_sign"], case["vertical_load_kN"]): case
               for case in result["cases"]}
    # Static eB=0.05 m gives Mstatic=V*e=50 kN·m.
    plus = by_sign[(1, 880.0)]
    minus = by_sign[(-1, 880.0)]
    assert plus["moment_B_kNm"] == pytest.approx(100.0)
    assert minus["moment_B_kNm"] == pytest.approx(0.0)
    assert plus["eccentricity_B_m"] == pytest.approx(100.0 / 880.0)
    assert minus["eccentricity_B_m"] == pytest.approx(0.0)
    assert plus["B_effective_m"] == pytest.approx(2.0 - 2.0 * 100.0 / 880.0)
    assert plus["horizontal_load_kN"] == pytest.approx(340.0)
    assert minus["horizontal_load_kN"] == pytest.approx(140.0)
    assert result["governing_case"] in result["cases"]


def test_usace_seismic_moment_that_removes_compression_contact_blocks_capacity_output():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        kh=0.2, kv=0.1, seismic_weight_kN=1200.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=5.0,
        seismic_moment_B_kNm=1100.0,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    assert result["qu_seismic_governing_kpa"] is None
    assert any(case["qu_seismic_kpa"] is None for case in result["cases"])
    assert "有效基礎尺寸" in result["governing_case"]["zero_resistance_reason"]


def test_usace_seismic_strip_foundation_rejects_long_axis_seismic_moment():
    with pytest.raises(ValueError, match="連續條形基礎不支援長邊方向偏心或彎矩"):
        seismic_bearing_capacity_residual_pore_pressure_cases(
            vertical_load_kN=1000.0, horizontal_load_kN=0.0,
            kh=0.2, kv=0.0, footing_type="strip",
            residual_excess_pore_pressure_ratio=0.2,
            c_kpa=0.0, phi_deg=30.0,
            gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
            B=2.0, L=10.0, Df=1.5, water_depth=5.0,
            seismic_moment_L_kNm=10.0,
            non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
        )


def test_usace_seismic_moment_combinations_preserve_signed_static_biaxial_eccentricity():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=50.0,
        kh=0.1, kv=0.05, seismic_weight_kN=1000.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.15,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=4.0, Df=1.0, water_depth=5.0,
        eccentricity_B=0.02, eccentricity_L=0.02,
        seismic_moment_B_kNm=20.0, seismic_moment_L_kNm=20.0,
        static_moment_B_sign=-1, static_moment_L_sign=1,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    by_sign = {case["horizontal_earthquake_sign"]: case for case in result["cases"]
               if case["vertical_load_kN"] == pytest.approx(950.0)}
    assert by_sign[1]["moment_B_kNm"] == pytest.approx(0.0)
    assert by_sign[1]["moment_L_kNm"] == pytest.approx(40.0)
    assert by_sign[-1]["moment_B_kNm"] == pytest.approx(-40.0)
    assert by_sign[-1]["moment_L_kNm"] == pytest.approx(0.0)


def test_usace_seismic_resistance_reports_middle_third_reference_without_hiding_bearing_resistance():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        kh=0.0, kv=0.0, seismic_weight_kN=1000.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=5.0,
        eccentricity_B=0.40,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    assert result["qu_seismic_governing_kpa"] is not None
    assert result["overturning_check_pass"] is True
    assert result["overturning_failed_cases"] == []
    assert result["middle_third_check_pass"] is False
    assert len(result["middle_third_failed_cases"]) == 2
    assert all(case["middle_third_B_pass"] is False for case in result["cases"])
    assert all(case["B_effective_m"] == pytest.approx(1.2) for case in result["cases"])
    assert all(case["average_contact_pressure_kpa"] == pytest.approx(1000.0 / (1.2 * 3.0))
               for case in result["cases"])


def test_usace_seismic_resistance_middle_third_check_passes_for_centered_load():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        kh=0.1, kv=0.05, seismic_weight_kN=1000.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=5.0,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    assert result["overturning_check_pass"] is True
    assert all(case["overturning_check_pass"] for case in result["cases"])


def test_usace_pseudostatic_sliding_evaluates_both_vertical_kv_cases():
    result = foundation_sliding_pseudostatic_cases(
        vertical_load_kN=1000.0, uplift_kN=100.0,
        horizontal_load_kN=100.0, seismic_weight_kN=1200.0,
        kh=0.2, kv=0.1, area_m2=6.0,
        friction_angle_deg=30.0, cohesion_kpa=0.0,
        adhesion_ratio=0.0, active_force_kN=0.0,
        passive_force_kN=0.0, fs_required=1.1,
    )
    assert len(result["cases"]) == 2
    assert [case["vertical_load_kN"] for case in result["cases"]] == pytest.approx([880.0, 1120.0])
    assert [case["horizontal_load_kN"] for case in result["cases"]] == pytest.approx([340.0, 340.0])
    expected_fs = (880.0 - 100.0) * math.tan(math.radians(30.0)) / 340.0
    assert result["FS_sliding"] == pytest.approx(expected_fs)
    assert result["governing_case"]["vertical_sign"] == "向下減少"
    assert result["FS_minimum_required"] == pytest.approx(1.1)


def test_usace_pseudostatic_sliding_rejects_zero_or_uplift_vertical_case():
    with pytest.raises(ValueError, match="V−kvW≤0"):
        foundation_sliding_pseudostatic_cases(
            vertical_load_kN=1000.0, uplift_kN=0.0,
            horizontal_load_kN=100.0, seismic_weight_kN=2500.0,
            kh=0.2, kv=0.5, area_m2=6.0,
            friction_angle_deg=30.0, fs_required=1.1,
        )


def test_usace_pseudostatic_sliding_rejects_uplift_at_least_minimum_vertical_load():
    with pytest.raises(ValueError, match="基底揚壓力"):
        foundation_sliding_pseudostatic_cases(
            vertical_load_kN=1000.0, uplift_kN=900.0,
            horizontal_load_kN=100.0, seismic_weight_kN=1000.0,
            kh=0.2, kv=0.1, area_m2=6.0,
            friction_angle_deg=30.0, fs_required=1.1,
        )


def test_usace_pseudostatic_sliding_enforces_minimum_earthquake_fs():
    with pytest.raises(ValueError, match="不得低於 1.1"):
        foundation_sliding_pseudostatic_cases(
            vertical_load_kN=1000.0, uplift_kN=0.0,
            horizontal_load_kN=100.0, seismic_weight_kN=1000.0,
            kh=0.2, kv=0.1, area_m2=6.0,
            friction_angle_deg=30.0, fs_required=1.0,
        )


def test_general_seismic_eccentricity_evaluates_four_signed_load_combinations():
    result = seismic_foundation_eccentricity_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=50.0,
        seismic_weight_kN=1000.0, kh=0.1, kv=0.1,
        footing_type="spread", B=2.0, L=3.0,
        eccentricity_B=0.05, seismic_moment_B_kNm=50.0,
    )
    assert len(result["cases"]) == 4
    plus = next(case for case in result["cases"]
                if case["horizontal_earthquake_sign"] == 1 and case["vertical_load_kN"] == pytest.approx(900.0))
    minus = next(case for case in result["cases"]
                 if case["horizontal_earthquake_sign"] == -1 and case["vertical_load_kN"] == pytest.approx(900.0))
    assert plus["horizontal_load_kN"] == pytest.approx(150.0)
    assert minus["horizontal_load_kN"] == pytest.approx(50.0)
    assert plus["eccentricity_B_m"] == pytest.approx(100.0 / 900.0)
    assert plus["middle_third_B_limit_m"] == pytest.approx(2.0 / 6.0)
    assert minus["eccentricity_B_m"] == pytest.approx(0.0)
    assert result["passes"] is True
    assert result["seismic_moment_included"] is True


def test_general_seismic_eccentricity_envelopes_both_horizontal_directions_without_seismic_moment():
    result = seismic_foundation_eccentricity_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=50.0,
        seismic_weight_kN=1000.0, kh=0.1, kv=0.1,
        footing_type="spread", B=2.0, L=3.0,
        eccentricity_B=0.05,
    )
    assert len(result["cases"]) == 4
    by_sign = {case["horizontal_earthquake_sign"]: case for case in result["cases"]
               if case["vertical_load_kN"] == pytest.approx(900.0)}
    assert by_sign[1]["horizontal_load_kN"] == pytest.approx(150.0)
    assert by_sign[-1]["horizontal_load_kN"] == pytest.approx(50.0)
    assert by_sign[1]["moment_B_kNm"] == pytest.approx(50.0)
    assert by_sign[-1]["moment_B_kNm"] == pytest.approx(50.0)
    assert result["seismic_moment_included"] is False


def test_residual_pore_pressure_seismic_cases_envelope_both_horizontal_directions_without_moment():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=50.0,
        kh=0.1, kv=0.1, seismic_weight_kN=1000.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=1.0,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    assert len(result["cases"]) == 4
    by_sign = {case["horizontal_earthquake_sign"]: case for case in result["cases"]
               if case["vertical_load_kN"] == pytest.approx(900.0)}
    assert by_sign[1]["horizontal_load_kN"] == pytest.approx(150.0)
    assert by_sign[-1]["horizontal_load_kN"] == pytest.approx(50.0)
    assert by_sign[1]["moment_B_kNm"] == pytest.approx(0.0)
    assert by_sign[-1]["moment_B_kNm"] == pytest.approx(0.0)
    assert result["seismic_moment_included"] is False


def test_general_seismic_eccentricity_reports_middle_third_separately_from_footprint():
    result = seismic_foundation_eccentricity_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        seismic_weight_kN=1000.0, kh=0.0, kv=0.0,
        footing_type="spread", B=2.0, L=3.0,
        eccentricity_B=0.40,
    )
    assert result["passes"] is True
    assert result["geometry_passes"] is True
    assert result["middle_third_passes"] is False
    assert result["cases"][0]["resultant_within_footprint"] is True
    assert result["cases"][0]["compression_contact_pass"] is True
    assert result["cases"][0]["B_effective_m"] == pytest.approx(1.2)
    assert result["cases"][0]["middle_third_B_pass"] is False
    assert result["bearing_pressure_check_complete"] is False
    assert result["overall_seismic_overturning_passes"] is None


def test_general_seismic_eccentricity_flags_loss_of_positive_contact_dimension():
    result = seismic_foundation_eccentricity_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        seismic_weight_kN=1000.0, kh=0.1, kv=0.1,
        footing_type="spread", B=2.0, L=3.0,
        seismic_moment_B_kNm=1100.0,
    )
    assert result["passes"] is False
    assert any(not case["compression_contact_pass"] for case in result["cases"])


def test_general_seismic_eccentricity_rejects_strip_long_axis_moment_and_zero_vertical_case():
    with pytest.raises(ValueError, match="連續條形基礎不支援長邊方向偏心或彎矩"):
        seismic_foundation_eccentricity_cases(
            vertical_load_kN=1000.0, horizontal_load_kN=0.0,
            seismic_weight_kN=1000.0, kh=0.1, kv=0.0,
            footing_type="strip", B=2.0, L=10.0,
            seismic_moment_L_kNm=10.0,
        )
    with pytest.raises(ValueError, match="V−kvW≤0"):
        seismic_foundation_eccentricity_cases(
            vertical_load_kN=1000.0, horizontal_load_kN=0.0,
            seismic_weight_kN=2500.0, kh=0.1, kv=0.5,
            footing_type="spread", B=2.0, L=3.0,
        )


def test_general_seismic_eccentricity_rejects_spread_footing_with_long_side_shorter_than_width():
    with pytest.raises(ValueError, match="長邊 L 不可小於短邊 B"):
        seismic_foundation_eccentricity_cases(
            vertical_load_kN=1000.0, horizontal_load_kN=0.0,
            seismic_weight_kN=1000.0, kh=0.1, kv=0.0,
            footing_type="spread", B=3.0, L=2.0,
        )


def test_usace_seismic_residual_pore_pressure_weighted_partial_shear_zone_formula():
    result = seismic_bearing_capacity_residual_pore_pressure(
        footing_type="spread",
        effective_unit_weight_kn_m3=10.0,
        effective_unit_weight_unaffected_kn_m3=18.0,
        effective_width_m=2.0, bearing_factor_ngamma=20.0,
        residual_excess_pore_pressure_ratio=0.5,
        shape_depth_inclination_factor=1.0,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=False,
        partial_shear_zone_affected_fraction=0.4,
    )
    expected_gamma_b = 0.4 * (1.0 - 0.5) * 10.0 + 0.6 * 18.0
    expected_unweighted = 0.4 * 10.0 + 0.6 * 18.0
    assert result["gamma_effective_weighted_kn_m3"] == pytest.approx(expected_gamma_b)
    assert result["pore_pressure_resistance_factor"] == pytest.approx(expected_gamma_b / expected_unweighted)
    assert result["qu_seismic_kpa"] == pytest.approx(0.4 * expected_gamma_b * 2.0 * 20.0)
    assert result["pore_pressure_affected_fraction"] == pytest.approx(0.4)


def test_usace_seismic_residual_pore_pressure_cases_accept_weighted_partial_shear_zone():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        kh=0.0, kv=0.0, seismic_weight_kN=1000.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=5.0,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=False,
        partial_shear_zone_affected_fraction=0.5,
        gamma_effective_susceptible_kn_m3=10.0,
        gamma_effective_unaffected_kn_m3=18.5,
    )
    expected_gamma_b = 0.5 * (1.0 - 0.2) * 10.0 + 0.5 * 18.5
    assert result["partial_shear_zone_affected_fraction"] == pytest.approx(0.5)
    assert all(case["gamma_effective_weighted_kn_m3"] == pytest.approx(expected_gamma_b)
               for case in result["cases"])
    assert result["qu_seismic_governing_kpa"] is not None


def test_usace_seismic_partial_shear_zone_requires_fraction_and_both_effective_unit_weights():
    with pytest.raises(ValueError, match="部分剪力區模式必須提供"):
        seismic_bearing_capacity_residual_pore_pressure_cases(
            vertical_load_kN=1000.0, horizontal_load_kN=0.0,
            kh=0.0, kv=0.0, seismic_weight_kN=1000.0,
            footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
            c_kpa=0.0, phi_deg=30.0,
            gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
            B=2.0, L=3.0, Df=1.5, water_depth=5.0,
            non_liquefiable_confirmed=True, full_shear_zone_confirmed=False,
            partial_shear_zone_affected_fraction=0.5,
            gamma_effective_susceptible_kn_m3=10.0,
        )


def test_usace_seismic_full_shear_zone_rejects_partial_zone_overrides():
    with pytest.raises(ValueError, match="完整剪力區模式不可同時輸入"):
        seismic_bearing_capacity_residual_pore_pressure(
            footing_type="spread",
            effective_unit_weight_kn_m3=10.0,
            effective_unit_weight_unaffected_kn_m3=18.0,
            effective_width_m=2.0, bearing_factor_ngamma=20.0,
            residual_excess_pore_pressure_ratio=0.5,
            non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
            partial_shear_zone_affected_fraction=0.4,
        )


@pytest.mark.parametrize("fraction", [0.0, 1.0, -0.1, 1.1])
def test_usace_seismic_partial_shear_zone_rejects_invalid_weighted_fraction(fraction):
    with pytest.raises(ValueError, match="部分剪力區加權比例須介於 0 與 1"):
        seismic_bearing_capacity_residual_pore_pressure(
            footing_type="spread",
            effective_unit_weight_kn_m3=10.0,
            effective_unit_weight_unaffected_kn_m3=18.0,
            effective_width_m=2.0, bearing_factor_ngamma=20.0,
            residual_excess_pore_pressure_ratio=0.5,
            non_liquefiable_confirmed=True, full_shear_zone_confirmed=False,
            partial_shear_zone_affected_fraction=fraction,
        )


@pytest.mark.parametrize("q_allow,expected", [(300.0, True), (250.0, False)])
def test_general_seismic_eccentricity_checks_effective_pressure_against_user_allowable(q_allow, expected):
    result = seismic_foundation_eccentricity_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        seismic_weight_kN=1000.0, kh=0.0, kv=0.0,
        footing_type="spread", B=2.0, L=3.0,
        eccentricity_B=0.40,
        allowable_bearing_pressure_kpa=q_allow,
    )
    assert result["geometry_passes"] is True
    assert result["middle_third_passes"] is False
    assert result["bearing_pressure_check_complete"] is True
    assert result["bearing_pressure_passes"] is expected
    assert result["overall_seismic_overturning_passes"] is expected
    assert result["cases"][0]["average_contact_pressure_kpa"] == pytest.approx(1000.0 / (1.2 * 3.0))


def test_general_seismic_eccentricity_deducts_hydrostatic_base_uplift_from_qeq():
    result = seismic_foundation_eccentricity_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        seismic_weight_kN=1000.0, kh=0.0, kv=0.0,
        footing_type="spread", B=2.0, L=3.0,
        eccentricity_B=0.40,
        allowable_bearing_pressure_kpa=240.0,
        base_uplift_pressure_kpa=50.0,
    )
    case = result["cases"][0]
    gross_qeq = 1000.0 / (1.2 * 3.0)
    assert case["gross_average_contact_pressure_kpa"] == pytest.approx(gross_qeq)
    assert case["base_uplift_pressure_kpa"] == pytest.approx(50.0)
    assert case["average_contact_pressure_kpa"] == pytest.approx(gross_qeq - 50.0)
    assert case["bearing_pressure_pass"] is True
    assert result["uplift_stability_check_complete"] is False


def test_general_seismic_eccentricity_does_not_pass_nonpositive_effective_qeq():
    result = seismic_foundation_eccentricity_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        seismic_weight_kN=1000.0, kh=0.0, kv=0.0,
        footing_type="spread", B=2.0, L=3.0,
        eccentricity_B=0.40,
        allowable_bearing_pressure_kpa=500.0,
        base_uplift_pressure_kpa=300.0,
    )
    assert result["cases"][0]["average_contact_pressure_kpa"] < 0.0
    assert result["cases"][0]["bearing_pressure_pass"] is False
    assert result["overall_seismic_overturning_passes"] is False


def test_usace_seismic_residual_pore_pressure_cases_deduct_hydrostatic_base_uplift():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        kh=0.0, kv=0.0, seismic_weight_kN=1000.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=1.0,
        base_uplift_pressure_kpa=9.81 * 0.5,
        non_liquefiable_confirmed=True, full_shear_zone_confirmed=True,
    )
    expected_gross_qeq = 1000.0 / (2.0 * 3.0)
    expected_uplift = 9.81 * 0.5
    assert result["base_uplift_pressure_kpa"] == pytest.approx(expected_uplift)
    assert all(case["gross_average_contact_pressure_kpa"] == pytest.approx(expected_gross_qeq)
               for case in result["cases"])
    assert all(case["average_contact_pressure_kpa"] == pytest.approx(expected_gross_qeq - expected_uplift)
               for case in result["cases"])
    assert result["uplift_stability_check_complete"] is False


def test_usace_residual_pore_pressure_method_accepts_marginal_liquefaction_with_ru():
    result = seismic_bearing_capacity_residual_pore_pressure(
        footing_type="spread",
        effective_unit_weight_kn_m3=10.0,
        effective_width_m=2.0,
        bearing_factor_ngamma=20.0,
        residual_excess_pore_pressure_ratio=0.2,
        factor_of_safety_liquefaction=1.2,
        no_significant_lateral_spreading_confirmed=True,
        ru_source_confirmed=True,
        full_shear_zone_confirmed=True,
    )
    assert result["factor_of_safety_liquefaction"] == pytest.approx(1.2)
    assert result["qu_seismic_kpa"] == pytest.approx(128.0)


def test_usace_residual_pore_pressure_method_rejects_fsliq_at_or_below_one():
    with pytest.raises(ValueError, match="FS_liq≤1.0"):
        seismic_bearing_capacity_residual_pore_pressure(
            footing_type="spread",
            effective_unit_weight_kn_m3=10.0,
            effective_width_m=2.0,
            bearing_factor_ngamma=20.0,
            residual_excess_pore_pressure_ratio=0.2,
            factor_of_safety_liquefaction=1.0,
            no_significant_lateral_spreading_confirmed=True,
            ru_source_confirmed=True,
            full_shear_zone_confirmed=True,
        )


def test_usace_residual_pore_pressure_method_requires_no_significant_lateral_spreading():
    with pytest.raises(ValueError, match="顯著側向擴展"):
        seismic_bearing_capacity_residual_pore_pressure(
            footing_type="spread",
            effective_unit_weight_kn_m3=10.0,
            effective_width_m=2.0,
            bearing_factor_ngamma=20.0,
            residual_excess_pore_pressure_ratio=0.2,
            factor_of_safety_liquefaction=1.2,
            no_significant_lateral_spreading_confirmed=False,
            ru_source_confirmed=True,
            full_shear_zone_confirmed=True,
        )


def test_usace_residual_pore_pressure_method_requires_ru_source_confirmation():
    with pytest.raises(ValueError, match="ru 必須由"):
        seismic_bearing_capacity_residual_pore_pressure(
            footing_type="spread",
            effective_unit_weight_kn_m3=10.0,
            effective_width_m=2.0,
            bearing_factor_ngamma=20.0,
            residual_excess_pore_pressure_ratio=0.2,
            factor_of_safety_liquefaction=1.2,
            no_significant_lateral_spreading_confirmed=True,
            ru_source_confirmed=False,
            full_shear_zone_confirmed=True,
        )


def test_usace_residual_pore_pressure_cases_accept_fsliq_and_confirmed_ru_source():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        kh=0.0, kv=0.0, seismic_weight_kN=1000.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=1.0,
        factor_of_safety_liquefaction=1.2,
        no_significant_lateral_spreading_confirmed=True,
        ru_source_confirmed=True,
        full_shear_zone_confirmed=True,
    )
    assert result["factor_of_safety_liquefaction"] == pytest.approx(1.2)
    assert result["no_significant_lateral_spreading_confirmed"] is True
    assert result["ru_source_confirmed"] is True


def test_seismic_uplift_fs_adjusts_only_structure_weight_for_vertical_inertia():
    result = seismic_uplift_stability_cases(
        resisting_weight_kN=1500.0,
        structure_seismic_weight_kN=1000.0,
        uplift_force_kN=100.0,
        kv=0.1,
    )
    assert result["FS_uplift"] == pytest.approx(14.0)
    assert result["governing_case"]["effective_downward_weight_kN"] == pytest.approx(1400.0)
    assert result["passes"] is True
    assert result["FS_required"] == pytest.approx(1.5)


def test_seismic_uplift_fs_fails_when_vertical_seismic_case_is_below_1_5():
    result = seismic_uplift_stability_cases(
        resisting_weight_kN=200.0,
        structure_seismic_weight_kN=100.0,
        uplift_force_kN=150.0,
        kv=0.5,
    )
    assert result["FS_uplift"] == pytest.approx(1.0)
    assert result["passes"] is False


def test_seismic_uplift_fs_zero_uplift_is_not_reported_as_pass():
    result = seismic_uplift_stability_cases(
        resisting_weight_kN=1500.0,
        structure_seismic_weight_kN=1000.0,
        uplift_force_kN=0.0,
        kv=0.1,
    )
    assert result["applicable"] is False
    assert result["FS_uplift"] is None
    assert result["passes"] is None


def test_seismic_uplift_fs_requires_resisting_weight_to_include_structure_weight():
    with pytest.raises(ValueError, match="不得小於Ws"):
        seismic_uplift_stability_cases(
            resisting_weight_kN=500.0,
            structure_seismic_weight_kN=600.0,
            uplift_force_kN=100.0,
            kv=0.1,
        )



def test_general_seismic_qeq_subtracts_user_confirmed_residual_base_pressure():
    result = seismic_foundation_eccentricity_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        seismic_weight_kN=1000.0, kh=0.0, kv=0.0,
        footing_type="spread", B=2.0, L=3.0,
        allowable_bearing_pressure_kpa=100.0,
        base_uplift_pressure_kpa=60.0,
    )
    case = result["cases"][0]
    assert case["gross_average_contact_pressure_kpa"] == pytest.approx(1000.0 / 6.0)
    assert case["base_uplift_pressure_kpa"] == pytest.approx(60.0)
    assert case["average_contact_pressure_kpa"] == pytest.approx(1000.0 / 6.0 - 60.0)
    assert case["bearing_pressure_pass"] is False


def test_residual_pore_pressure_qeq_subtracts_total_base_pressure():
    result = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        kh=0.0, kv=0.0, seismic_weight_kN=1000.0,
        footing_type="spread", residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=2.0, L=3.0, Df=1.5, water_depth=1.0,
        base_uplift_pressure_kpa=20.0,
        factor_of_safety_liquefaction=1.2,
        no_significant_lateral_spreading_confirmed=True,
        ru_source_confirmed=True,
        full_shear_zone_confirmed=True,
    )
    assert result["base_uplift_pressure_kpa"] == pytest.approx(20.0)
    assert all(case["average_contact_pressure_kpa"] == pytest.approx(1000.0/6.0-20.0)
               for case in result["cases"])


def test_developed_rankine_sliding_pressures_match_usace_2025_equations_5_31_to_5_35():
    # USACE EM 1110-1-1905 (2025), Eqs. 5-31 to 5-35.
    gamma, depth, length = 18.0, 2.0, 3.0
    phi, cohesion, fs = 30.0, 12.0, 2.0
    phi_d = math.degrees(math.atan(math.tan(math.radians(phi)) / fs))
    c_d = cohesion / fs
    sin_d = math.sin(math.radians(phi_d))
    ka = (1.0 - sin_d) / (1.0 + sin_d)
    kp = 1.0 / ka

    result = developed_rankine_sliding_earth_pressures(
        effective_unit_weight_kn_m3=gamma,
        footing_depth_m=depth,
        footing_length_m=length,
        friction_angle_deg=phi,
        cohesion_kpa=cohesion,
        fs_sliding=fs,
        load_case="static",
    )

    expected_pa = max((0.5 * gamma * depth * ka - 2.0 * c_d) * depth * length, 0.0)
    expected_pp = (0.5 * gamma * depth * kp + 2.0 * c_d) * depth * length
    assert result["developed_phi_deg"] == pytest.approx(phi_d)
    assert result["developed_cohesion_kpa"] == pytest.approx(c_d)
    assert result["Ka_developed"] == pytest.approx(ka)
    assert result["Kp_developed"] == pytest.approx(kp)
    assert result["active_force_kN"] == pytest.approx(expected_pa)
    assert result["passive_force_kN"] == pytest.approx(expected_pp)


def test_developed_rankine_sliding_pressures_enforce_load_case_minimum_fs():
    args = dict(
        effective_unit_weight_kn_m3=18.0,
        footing_depth_m=2.0,
        footing_length_m=3.0,
        friction_angle_deg=30.0,
        cohesion_kpa=10.0,
        fs_sliding=1.9,
    )
    with pytest.raises(ValueError, match="不得低於 2.0"):
        developed_rankine_sliding_earth_pressures(**args, load_case="static")
    seismic = developed_rankine_sliding_earth_pressures(
        **{**args, "fs_sliding": 1.1}, load_case="seismic"
    )
    assert seismic["FS_minimum_required"] == pytest.approx(1.1)


def test_sliding_passive_resistance_is_capped_at_total_driving_force():
    result = foundation_sliding_factor_of_safety(
        vertical_load_kN=1000.0,
        uplift_kN=100.0,
        horizontal_load_kN=100.0,
        area_m2=10.0,
        friction_angle_deg=30.0,
        cohesion_kpa=0.0,
        adhesion_ratio=0.0,
        active_force_kN=20.0,
        passive_force_kN=500.0,
        fs_required=2.0,
    )
    assert result["passive_resistance_used_kN"] == pytest.approx(120.0)
    assert result["driving_force_kN"] == pytest.approx(0.0)
    assert result["passive_resistance_capped"] is True
    assert result["passive_balance_controls"] is True


@pytest.mark.parametrize("label", [
    "true", "1", "1.0", "yes", "y", "refusal",
    "partial penetration", "partial_penetration",
    "拒錘", "拒打", "拒貫", "部分貫入",
])
def test_spt_ui_refusal_mask_accepts_engine_refusal_vocabulary(label):
    import pandas as pd
    from geolysis_ui.module3 import _spt_refusal_mask

    result = _spt_refusal_mask(pd.Series([label, "false", "正常"]))
    assert result.tolist() == [True, False, False]


def test_bishop_slice_weight_splits_moist_and_saturated_soil_at_water_table():
    from geolysis_engine.stability import _bishop_slice_total_weight

    weight = _bishop_slice_total_weight(
        width_m=2.0, ground_elevation_m=10.0, base_elevation_m=4.0,
        groundwater_elevation_m=7.0,
        gamma_moist_kn_m3=18.0, gamma_sat_kn_m3=20.0,
    )
    # 3 m above water table at 18 kN/m³ and 3 m below at 20 kN/m³.
    assert weight == pytest.approx(228.0)


def test_bishop_circular_search_uses_saturated_weight_below_groundwater():
    from geolysis_engine import bishop_circular_search

    profile = [(0.0, 10.0), (5.0, 8.0), (10.0, 0.0), (20.0, 0.0)]
    common = dict(
        ground_profile=profile, cohesion_kpa=10.0, friction_angle_deg=25.0,
        center_x_values=[6.0], center_y_values=[12.0], radius_values=[15.0],
        slice_count=20, groundwater_elevation=-1.0,
    )
    split = bishop_circular_search(
        **common, unit_weight_kn_m3=18.0,
        unit_weight_moist_kn_m3=18.0, unit_weight_sat_kn_m3=20.0,
    )
    legacy = bishop_circular_search(**common, unit_weight_kn_m3=18.0)
    assert split["water_table_weighting"] is True
    assert split["unit_weight_moist_kn_m3"] == pytest.approx(18.0)
    assert split["unit_weight_sat_kn_m3"] == pytest.approx(20.0)
    assert split["FS"] != pytest.approx(legacy["FS"])


def test_spt_cohesive_soil_does_not_require_effective_stress_for_n60():
    result = spt_correct(
        12.0, 75.0, 1.15, 1.20, 5.0, None,
        "Liao & Whitman", 2.0, soil_behavior="cohesive",
    )
    expected_n60 = 12.0 * 1.25 * 1.0 * 1.20 * 0.85
    assert result["N60"] == pytest.approx(expected_n60)
    assert result["CB"] == pytest.approx(1.0)
    assert result["CN"] == pytest.approx(1.0)
    assert result["N1_60"] == pytest.approx(expected_n60)


def test_spt_cohesionless_no_cn_option_does_not_require_effective_stress():
    result = spt_correct(
        12.0, 60.0, 1.0, 1.0, 10.0, None,
        "不修正", 2.0, soil_behavior="cohesionless",
    )
    assert result["N60"] == pytest.approx(12.0)
    assert result["CN"] == pytest.approx(1.0)
    assert result["N1_60"] == pytest.approx(12.0)


def test_spt_cohesionless_cn_correction_still_requires_effective_stress():
    with pytest.raises(ValueError, match="有效覆土應力"):
        spt_correct(
            12.0, 60.0, 1.0, 1.0, 10.0, None,
            "Liao & Whitman", 2.0, soil_behavior="cohesionless",
        )


def test_spt_profile_accepts_cohesive_and_refusal_rows_without_effective_stress():
    from geolysis_engine import spt_profile

    result = spt_profile(
        [
            {"Depth_m": 1.0, "N": 12.0, "Soil_Behavior": "cohesive"},
            {"Depth_m": 2.0, "N": 50.0, "Soil_Behavior": "cohesionless", "Refusal": True},
        ],
        energy_ratio_pct=60.0, borehole_factor=1.05, sampler_factor=1.0,
        rod_length_m=8.0, cn_method="Liao & Whitman",
    )
    assert result[0]["N60"] == pytest.approx(12.0 * 0.95)
    assert result[0]["CN"] == pytest.approx(1.0)
    assert result[0]["Effective_Stress_KPa"] is None
    assert result[1]["N60"] is None
    assert result[1]["Effective_Stress_KPa"] is None


def test_spt_profile_requires_effective_stress_only_for_nonrefusal_cohesionless_rows_using_cn():
    from geolysis_engine import spt_profile

    with pytest.raises(ValueError, match="Effective_Stress_KPa"):
        spt_profile(
            [{"Depth_m": 1.0, "N": 12.0, "Soil_Behavior": "cohesionless"}],
            energy_ratio_pct=60.0, borehole_factor=1.0, sampler_factor=1.0,
            rod_length_m=8.0, cn_method="Liao & Whitman",
        )


def test_spt_profile_requires_explicit_per_row_dilatancy_flags_when_enabled_globally():
    from geolysis_engine import spt_profile

    with pytest.raises(ValueError, match="Apply_Dilatancy"):
        spt_profile(
            [{"Depth_m": 1.0, "N": 20.0, "Effective_Stress_KPa": 100.0}],
            energy_ratio_pct=60.0, borehole_factor=1.0, sampler_factor=1.0,
            rod_length_m=8.0, cn_method="Liao & Whitman",
            apply_dilatancy=True,
        )


def test_spt_profile_applies_dilatancy_only_to_explicitly_flagged_rows():
    from geolysis_engine import spt_profile

    result = spt_profile(
        [
            {"Depth_m": 1.0, "N": 20.0, "Effective_Stress_KPa": 100.0,
             "Soil_Behavior": "cohesionless", "Apply_Dilatancy": True},
            {"Depth_m": 2.0, "N": 20.0, "Effective_Stress_KPa": 100.0,
             "Soil_Behavior": "cohesionless", "Apply_Dilatancy": False},
        ],
        energy_ratio_pct=60.0, borehole_factor=1.0, sampler_factor=1.0,
        rod_length_m=8.0, cn_method="Liao & Whitman",
        apply_dilatancy=True,
    )
    assert result[0]["dilatancy_applied"] is True
    assert result[1]["dilatancy_applied"] is False


def test_spt_correction_rejects_borehole_and_sampler_factors_outside_usace_table():
    with pytest.raises(ValueError, match="CB 需 1.00–1.15"):
        spt_correct(
            12.0, 60.0, 1.20, 1.0, 8.0, 100.0,
            "Liao & Whitman", 2.0, soil_behavior="cohesionless",
        )
    with pytest.raises(ValueError, match="CS 需 1.00–1.30"):
        spt_correct(
            12.0, 60.0, 1.0, 1.40, 8.0, 100.0,
            "Liao & Whitman", 2.0, soil_behavior="cohesionless",
        )


def test_spt_correction_warns_when_energy_ratio_or_rod_length_exceeds_table_ranges():
    result = spt_correct(
        12.0, 140.0, 1.0, 1.0, 35.0, 100.0,
        "Liao & Whitman", 2.0, soil_behavior="cohesionless",
    )
    assert result["CR"] == pytest.approx(1.0)
    assert any("50–130%" in warning for warning in result["warnings"])
    assert any("30 m" in warning for warning in result["warnings"])


def test_spt_profile_global_dilatancy_does_not_require_flag_on_refusal_rows():
    from geolysis_engine import spt_profile

    result = spt_profile(
        [
            {"Depth_m": 1.0, "N": 50.0, "Soil_Behavior": "cohesionless", "Refusal": True},
            {"Depth_m": 2.0, "N": 20.0, "Soil_Behavior": "cohesionless",
             "Effective_Stress_KPa": 100.0, "Apply_Dilatancy": False},
        ],
        energy_ratio_pct=60.0, borehole_factor=1.0, sampler_factor=1.0,
        rod_length_m=8.0, cn_method="Liao & Whitman", apply_dilatancy=True,
    )
    assert result[0]["N60"] is None
    assert result[0]["dilatancy_applied"] is False
    assert result[1]["dilatancy_applied"] is False


def test_uscs_and_aashto_group_symbols_include_chinese_interpretations():
    from geolysis_engine.classification import _uscs_description, _aashto_description

    assert "級配不良砂土" in _uscs_description("SP-SC")
    assert "黏土質細料" in _uscs_description("SP-SC")
    assert "邊界區" in _uscs_description("CL-ML")
    assert "烘乾" in _uscs_description("OL（暫定）")
    assert "高液限黏土" in _aashto_description("A-7-5")
    assert "PI ≤ LL − 30" in _aashto_description("A-7-5")


def test_uscs_missing_gradation_description_does_not_claim_final_group():
    from geolysis_engine.classification import _uscs_description

    description = _uscs_description("G? (缺少 D10/D30/D60)")
    assert "不能判定" in description
    assert "D10" in description


def test_base_uplift_pressure_readiness_blocks_underestimated_or_unconfirmed_uplift():
    from geolysis_engine import base_uplift_pressure_readiness

    assert not base_uplift_pressure_readiness(
        uplift_force_kN=90.0, hydrostatic_reference_kN=100.0,
        load_case="seismic", pressure_confirmed=True,
    )["ready"]
    assert not base_uplift_pressure_readiness(
        uplift_force_kN=100.0, hydrostatic_reference_kN=100.0,
        load_case="seismic", pressure_confirmed=False,
    )["ready"]
    assert not base_uplift_pressure_readiness(
        uplift_force_kN=100.0, hydrostatic_reference_kN=0.0,
        load_case="static", pressure_confirmed=False,
    )["ready"]


def test_base_uplift_pressure_readiness_accepts_confirmed_reference_and_flags_larger_u():
    from geolysis_engine import base_uplift_pressure_readiness

    exact = base_uplift_pressure_readiness(
        uplift_force_kN=100.0, hydrostatic_reference_kN=100.0,
        load_case="seismic", pressure_confirmed=True,
    )
    assert exact["ready"] is True
    assert exact["exceeds_reference"] is False
    larger = base_uplift_pressure_readiness(
        uplift_force_kN=120.0, hydrostatic_reference_kN=100.0,
        load_case="static", pressure_confirmed=True,
    )
    assert larger["ready"] is True
    assert larger["exceeds_reference"] is True
    dry_static = base_uplift_pressure_readiness(
        uplift_force_kN=0.0, hydrostatic_reference_kN=0.0,
        load_case="static", pressure_confirmed=False,
    )
    assert dry_static["ready"] is True


def test_layered_punching_reports_usace_shear_zone_depth_applicability():
    from geolysis_engine import layered_bearing_capacity_punching

    isolated_ok = layered_bearing_capacity_punching(
        q_ult_strong_kpa=500.0, q_ult_weak_kpa=200.0,
        strong_layer_thickness_m=2.0, footing_width_m=2.0,
        footing_length_m=3.0, footing_type="isolated",
    )
    assert isolated_ok["within_usace_shear_zone_range"] is True
    assert isolated_ok["recommended_depth_range_m"] == pytest.approx((1.0, 4.0))
    assert isolated_ok["applicability_warning"] is None

    isolated_out = layered_bearing_capacity_punching(
        q_ult_strong_kpa=500.0, q_ult_weak_kpa=200.0,
        strong_layer_thickness_m=0.5, footing_width_m=2.0,
        footing_length_m=3.0, footing_type="isolated",
    )
    assert isolated_out["within_usace_shear_zone_range"] is False
    assert "不可標示為完整" in isolated_out["applicability_warning"]

    strip_out = layered_bearing_capacity_punching(
        q_ult_strong_kpa=500.0, q_ult_weak_kpa=200.0,
        strong_layer_thickness_m=1.5, footing_width_m=2.0,
        footing_length_m=10.0, footing_type="continuous",
    )
    assert strip_out["within_usace_shear_zone_range"] is False
    assert strip_out["recommended_depth_range_m"] == pytest.approx((2.0, 8.0))


def test_usace_dmt_rm_all_four_equation_branches():
    # Independently evaluate the four USACE EM 1110-1-1905 Eq. 3-41 branches.
    cases = [
        (0.5, 2.0, "Eq. 3-41a (ID≤0.6)", max(0.85, 0.14 + 2.36 * math.log10(2.0))),
        (1.5, 4.0, "Eq. 3-41b (0.6<ID<3)", (
            (0.14 + 0.15 * (1.5 - 0.6))
            + (2.5 - (0.14 + 0.15 * (1.5 - 0.6))) * math.log10(4.0)
        )),
        (3.5, 4.0, "Eq. 3-41c (ID≥3)", 0.5 + 2.0 * math.log10(4.0)),
        (0.5, 12.0, "Eq. 3-41d (KD>10)", 0.32 + 2.18 * math.log10(12.0)),
    ]
    for id_value, kd_value, expected_branch, expected_rm in cases:
        layers = [
            {
                "thickness_m": 0.1,
                "p0_bar": 2.0,
                "p1_bar": 2.0 + id_value,
                "u0_bar": 1.0,
                "sigma_v0_eff_bar": 1.0 / kd_value,
            }
            for _ in range(20)
        ]
        result = dmt_settlement_2025(
            layers=layers,
            footing_width_m=1.0,
            footing_length_m=1.0,
            gross_pressure_kpa=200.0,
            base_effective_stress_kpa=50.0,
        )
        first = result["layer_results"][0]
        assert first["ID"] == pytest.approx(id_value)
        assert first["KD"] == pytest.approx(kd_value)
        assert first["RM_branch"] == expected_branch
        assert first["RM"] == pytest.approx(expected_rm, rel=1e-12)

def test_usace_schmertmann_cpt_interpolates_es_peak_depth_and_iz_for_intermediate_aspect_ratio():
    # USACE EM 1110-1-1905 (2025), §7-12: interpolate between axisymmetric
    # L/B=1 and plane-strain L/B=10; Eq. 7-23 uses the printed 0.111 coefficient.
    B, ratio, qc = 1.0, 5.5, 1000.0
    layers = [{"thickness_m": 0.25, "qc_kpa": qc} for _ in range(12)]
    result = schmertmann_cpt_settlement_2025(
        layers=layers,
        footing_width_m=B,
        footing_length_m=B * ratio,
        gross_pressure_kpa=200.0,
        base_effective_stress_kpa=50.0,
        peak_effective_stress_kpa=100.0,
        soil_applicability_confirmed=True,
    )
    assert result["peak_depth_m"] == pytest.approx(0.75 * B)
    assert result["influence_depth_required_m"] == pytest.approx(3.0 * B)
    assert result["layer_results"][0]["Es_kPa"] == pytest.approx(3.0 * qc)
    first = result["layer_results"][0]
    expected_iz = first["Iz_axisymmetric"] + 0.111 * 4.5 * (
        first["Iz_plane_strain"] - first["Iz_axisymmetric"]
    )
    assert first["Iz_used"] == pytest.approx(expected_iz)


def test_usace_2025_seismic_residual_pore_pressure_strip_footing_eq_9_3():
    # USACE EM 1110-1-1905 (2025), Eq. 9-3:
    # q_u = 1/2 * (1-r_u) * gamma_b * B' * N_gamma.
    result = seismic_bearing_capacity_residual_pore_pressure(
        footing_type="strip",
        effective_unit_weight_kn_m3=12.0,
        effective_width_m=2.5,
        bearing_factor_ngamma=18.0,
        residual_excess_pore_pressure_ratio=0.30,
        shape_depth_inclination_factor=0.85,
        factor_of_safety_liquefaction=1.2,
        no_significant_lateral_spreading_confirmed=True,
        ru_source_confirmed=True,
        full_shear_zone_confirmed=True,
    )
    expected = 0.5 * (1.0 - 0.30) * 12.0 * 2.5 * 18.0 * 0.85
    assert result["qu_seismic_kpa"] == pytest.approx(expected)
    assert "Eqs. 9-3/9-4" in result["method"]


def test_usace_seismic_qeq_combines_eccentric_effective_area_and_base_uplift():
    # USACE EM 1110-1-1905 (2025), Eqs. 5-2 and 5-4 to 5-8:
    # q_eq = V/A' - u_D, A' = (B-2e_B)(L-2e_L).
    result = seismic_foundation_eccentricity_cases(
        vertical_load_kN=1000.0, horizontal_load_kN=0.0,
        seismic_weight_kN=1000.0, kh=0.0, kv=0.0,
        footing_type="spread", B=2.0, L=3.0,
        eccentricity_B=0.40, eccentricity_L=0.25,
        allowable_bearing_pressure_kpa=400.0,
        base_uplift_pressure_kpa=60.0,
    )
    case = result["cases"][0]
    effective_area = (2.0 - 2.0 * 0.40) * (3.0 - 2.0 * 0.25)
    expected = 1000.0 / effective_area - 60.0
    assert case["effective_area_m2"] == pytest.approx(effective_area)
    assert case["average_contact_pressure_kpa"] == pytest.approx(expected)


def test_seismic_eccentricity_and_residual_bearing_share_identical_load_envelopes():
    common = dict(
        vertical_load_kN=1000.0, horizontal_load_kN=50.0,
        seismic_weight_kN=1000.0, kh=0.1, kv=0.1,
        footing_type="spread", B=2.0, L=3.0,
        eccentricity_B=0.05, seismic_moment_B_kNm=50.0,
        base_uplift_pressure_kpa=10.0,
    )
    geometry = seismic_foundation_eccentricity_cases(**common)
    bearing = seismic_bearing_capacity_residual_pore_pressure_cases(
        vertical_load_kN=common["vertical_load_kN"],
        horizontal_load_kN=common["horizontal_load_kN"],
        seismic_weight_kN=common["seismic_weight_kN"],
        kh=common["kh"], kv=common["kv"],
        footing_type=common["footing_type"],
        residual_excess_pore_pressure_ratio=0.2,
        c_kpa=0.0, phi_deg=30.0,
        gamma_moist=18.5, gamma_sub=9.5, gamma_below=18.5,
        B=common["B"], L=common["L"], Df=1.5, water_depth=5.0,
        eccentricity_B=common["eccentricity_B"],
        seismic_moment_B_kNm=common["seismic_moment_B_kNm"],
        base_uplift_pressure_kpa=common["base_uplift_pressure_kpa"],
        factor_of_safety_liquefaction=1.2,
        no_significant_lateral_spreading_confirmed=True,
        ru_source_confirmed=True, full_shear_zone_confirmed=True,
    )
    geom_cases = {
        (case["horizontal_earthquake_sign"], round(case["vertical_load_kN"], 8)): case
        for case in geometry["cases"]
    }
    bear_cases = {
        (case["horizontal_earthquake_sign"], round(case["vertical_load_kN"], 8)): case
        for case in bearing["cases"]
    }
    assert set(geom_cases) == set(bear_cases)
    for key, geom in geom_cases.items():
        calc = bear_cases[key]
        assert calc["B_effective_m"] == pytest.approx(geom["B_effective_m"])
        assert calc["L_effective_m"] == pytest.approx(geom["L_effective_m"])
        assert calc["average_contact_pressure_kpa"] == pytest.approx(
            geom["average_contact_pressure_kpa"]
        )


def test_fhwa_quantitative_gsi_from_rqd_and_jcond89():
    from geolysis_engine import gsi_quantitative_from_rqd_jcond

    result = gsi_quantitative_from_rqd_jcond(
        rqd_percent=80.0,
        persistence_rating=6,
        separation_rating=5,
        roughness_rating=5,
        infilling_rating=4,
        weathering_rating=5,
    )
    assert result["JCond89"] == 25
    assert result["GSI"] == pytest.approx(77.5)
    assert result["equation"] == "GSI = 1.5 * JCond89 + RQD / 2"


def test_fhwa_quantitative_gsi_rejects_invalid_rqd_and_non_table_ratings():
    from geolysis_engine import gsi_quantitative_from_rqd_jcond

    common = dict(
        persistence_rating=6, separation_rating=5, roughness_rating=5,
        infilling_rating=4, weathering_rating=5,
    )
    with pytest.raises(ValueError, match="RQD 必須介於"):
        gsi_quantitative_from_rqd_jcond(rqd_percent=101, **common)
    with pytest.raises(ValueError, match="Table 9-8"):
        gsi_quantitative_from_rqd_jcond(
            rqd_percent=80, persistence_rating=3,
            separation_rating=5, roughness_rating=5, infilling_rating=4,
            weathering_rating=5,
        )


def test_usace_dmt_typical_kd_range_is_a_warning_not_a_hard_rejection():
    layers = [
        {"thickness_m": 0.2, "p0_bar": 2.0, "p1_bar": 3.0,
         "u0_bar": 0.5, "sigma_v0_eff_bar": 1.0}
        for _ in range(10)
    ]
    # KD = 1.5, below the typical 2–20 range in USACE §3-9c(2).
    result = dmt_settlement_2025(
        layers=layers, footing_width_m=1.0, footing_length_m=1.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
    )
    assert result["layer_results"][0]["KD"] == pytest.approx(1.5)
    assert any("常見範圍 2–20" in warning for warning in result["warnings"])
    assert result["settlement_mm"] > 0


def test_usace_dmt_typical_kd_range_does_not_warn_for_typical_values():
    layers = [
        {"thickness_m": 0.2, "p0_bar": 2.5, "p1_bar": 3.5,
         "u0_bar": 0.5, "sigma_v0_eff_bar": 1.0}
        for _ in range(10)
    ]
    result = dmt_settlement_2025(
        layers=layers, footing_width_m=1.0, footing_length_m=1.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
    )
    assert result["layer_results"][0]["KD"] == pytest.approx(2.0)
    assert not any("KD 超出" in warning for warning in result["warnings"])
    assert any("尚未低於 0.10" in warning for warning in result["warnings"])


def test_fhwa_gsi_scale_effect_warning_only_triggers_for_slopes_over_20m():
    from geolysis_engine import gsi_scale_effect_warning

    assert gsi_scale_effect_warning(application="slope", height_m=20.0) is None
    warning = gsi_scale_effect_warning(application="slope", height_m=25.0)
    assert "超過" in warning and "未自動折減" in warning
    assert gsi_scale_effect_warning(application="tunnel", height_m=100.0) is None
    assert gsi_scale_effect_warning(application="general", height_m=100.0) is None


def test_base_uplift_pressure_readiness_accepts_loadcase_specific_base_pressure_reference():
    from geolysis_engine import base_uplift_pressure_readiness

    result = base_uplift_pressure_readiness(
        uplift_force_kN=160.0, base_pressure_reference_kN=160.0,
        load_case="seismic", pressure_confirmed=True,
    )
    assert result["ready"] is True
    assert result["exceeds_reference"] is False
    lower = base_uplift_pressure_readiness(
        uplift_force_kN=150.0, base_pressure_reference_kN=160.0,
        load_case="seismic", pressure_confirmed=True,
    )
    assert lower["ready"] is False
    assert "適用基底壓力參考值" in lower["reason"]


def test_base_uplift_pressure_readiness_rejects_conflicting_reference_aliases():
    from geolysis_engine import base_uplift_pressure_readiness

    with pytest.raises(ValueError, match="不可同時提供不同值"):
        base_uplift_pressure_readiness(
            uplift_force_kN=160.0, base_pressure_reference_kN=160.0,
            hydrostatic_reference_kN=100.0, load_case="seismic",
            pressure_confirmed=True,
        )


def test_module3_normalizes_legacy_effective_stress_csv_column_case():
    import pandas as pd
    from geolysis_ui.module3 import _normalize_spt_profile_effective_stress

    legacy = pd.DataFrame({
        "Depth_m": [1.0, 2.0],
        "N": [12.0, 18.0],
        "Effective_Stress_kPa": [100.0, 125.0],
    })
    normalized = _normalize_spt_profile_effective_stress(legacy)
    assert normalized["Effective_Stress_KPa"].tolist() == [100.0, 125.0]
    assert "Effective_Stress_kPa" not in normalized.columns


def test_module3_merges_legacy_and_canonical_effective_stress_columns():
    import pandas as pd
    from geolysis_ui.module3 import _normalize_spt_profile_effective_stress

    profile = pd.DataFrame({
        "Effective_Stress_KPa": [None, 150.0],
        "Effective_Stress_kPa": [90.0, 120.0],
    })
    normalized = _normalize_spt_profile_effective_stress(profile)
    assert normalized["Effective_Stress_KPa"].tolist() == [90.0, 150.0]
    assert "Effective_Stress_kPa" not in normalized.columns


def test_developed_rankine_helper_explicitly_disclaims_seismic_dynamic_pressure():
    result = developed_rankine_sliding_earth_pressures(
        effective_unit_weight_kn_m3=18.0,
        footing_depth_m=2.0,
        footing_length_m=3.0,
        friction_angle_deg=30.0,
        cohesion_kpa=0.0,
        fs_sliding=1.1,
        load_case="seismic",
    )
    assert "計算靜態" in result["limitations"]
    assert "不會計算地震動態土壓增量" in result["limitations"]


def test_pseudostatic_sliding_limitations_require_seismic_pa_pp_inputs():
    result = foundation_sliding_pseudostatic_cases(
        vertical_load_kN=1000.0, uplift_kN=100.0,
        horizontal_load_kN=100.0, seismic_weight_kN=1000.0,
        kh=0.15, kv=0.1, area_m2=10.0,
        friction_angle_deg=30.0, cohesion_kpa=0.0,
        active_force_kN=20.0, passive_force_kN=10.0,
    )
    assert "地震作用下正反向控制值" in result["limitations"]
    assert "地震動態土壓" in result["limitations"]


def test_seismic_sliding_earth_pressure_readiness_requires_explicit_manual_confirmation():
    from geolysis_ui.module5 import _slide_seismic_earth_pressure_ready

    assert _slide_seismic_earth_pressure_ready("static", False) is True
    assert _slide_seismic_earth_pressure_ready("seismic", False) is False
    assert _slide_seismic_earth_pressure_ready("seismic", True) is True


def test_bishop_manual_slice_csv_uses_canonical_per_metre_weight_header():
    import pandas as pd
    from geolysis_ui.module5 import _normalize_bishop_weight_column

    frame = pd.DataFrame({
        "width_m": [1.0],
        "weight_kN_per_m": [100.0],
        "base_angle_deg": [10.0],
        "cohesion_kpa": [10.0],
        "friction_angle_deg": [25.0],
        "pore_pressure_kpa": [0.0],
    })
    normalized, legacy = _normalize_bishop_weight_column(frame)
    assert legacy is False
    assert normalized["weight_kN"].tolist() == [100.0]
    assert "weight_kN_per_m" not in normalized.columns


def test_bishop_manual_slice_csv_accepts_legacy_weight_header_as_per_metre():
    import pandas as pd
    from geolysis_ui.module5 import _normalize_bishop_weight_column

    frame = pd.DataFrame({"weight_kN": [100.0]})
    normalized, legacy = _normalize_bishop_weight_column(frame)
    assert legacy is True
    assert normalized["weight_kN"].tolist() == [100.0]


def test_bishop_manual_slice_csv_rejects_ambiguous_dual_weight_headers():
    import pandas as pd
    from geolysis_ui.module5 import _normalize_bishop_weight_column

    frame = pd.DataFrame({"weight_kN": [100.0], "weight_kN_per_m": [100.0]})
    with pytest.raises(ValueError, match="不可同時提供"):
        _normalize_bishop_weight_column(frame)


def test_bishop_rejects_slice_with_nonpositive_effective_normal_contact():
    slices = [
        {"width_m": 1.0, "weight_kN": 10.0, "base_angle_deg": 10.0,
         "cohesion_kpa": 5.0, "friction_angle_deg": 25.0, "pore_pressure_kpa": 12.0},
        {"width_m": 1.0, "weight_kN": 100.0, "base_angle_deg": 15.0,
         "cohesion_kpa": 5.0, "friction_angle_deg": 25.0, "pore_pressure_kpa": 0.0},
        {"width_m": 1.0, "weight_kN": 100.0, "base_angle_deg": 20.0,
         "cohesion_kpa": 5.0, "friction_angle_deg": 25.0, "pore_pressure_kpa": 0.0},
    ]
    with pytest.raises(ValueError, match="無正向有效法向接觸"):
        bishop_simplified_factor_of_safety(slices=slices)


def test_bishop_circular_search_rejects_ponded_groundwater_without_external_water_pressure():
    from geolysis_engine import bishop_circular_search

    with pytest.raises(ValueError, match="地表積水／淹水"):
        bishop_circular_search(
            ground_profile=[(0.0, 10.0), (5.0, 8.0), (10.0, 0.0), (20.0, 0.0)],
            cohesion_kpa=10.0, friction_angle_deg=25.0,
            unit_weight_kn_m3=18.0,
            center_x_values=[6.0], center_y_values=[12.0], radius_values=[15.0],
            slice_count=20, groundwater_elevation=6.0,
            unit_weight_moist_kn_m3=18.0, unit_weight_sat_kn_m3=20.0,
        )

def test_usace_2025_dmt_modulus_warns_when_bottom_stress_may_need_deeper_review():
    layers = [
        {"Layer": i + 1, "depth_center_m": (i + 0.5) * 0.2,
         "thickness_m": 0.2, "MDMT_kpa": 10000.0}
        for i in range(10)
    ]
    result = dmt_modulus_settlement_2025(
        layers=layers, footing_width_m=1.0, footing_length_m=1.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
    )
    assert result["settlement_mm"] > 0
    assert any("尚未低於 0.10" in warning for warning in result["warnings"])


def test_usace_2025_dmt_readings_warn_when_bottom_stress_may_need_deeper_review():
    layers = [
        {"thickness_m": 0.2, "p0_bar": 2.0, "p1_bar": 3.0,
         "u0_bar": 0.5, "sigma_v0_eff_bar": 1.0}
        for _ in range(10)
    ]
    result = dmt_settlement_2025(
        layers=layers, footing_width_m=1.0, footing_length_m=1.0,
        gross_pressure_kpa=200.0, base_effective_stress_kpa=50.0,
    )
    assert result["settlement_mm"] > 0
    assert any("尚未低於 0.10" in warning for warning in result["warnings"])



@pytest.mark.parametrize(
    "width,length,expected",
    [
        (2.0, 2.0, "isolated"),
        (2.0, 20.0, "isolated"),  # L/B = 10 is not a strip footing.
        (2.0, 20.02, "continuous"),
        (1.0, 10.1, "continuous"),
    ],
)
def test_usace_footing_type_uses_strict_length_to_width_ratio_boundary(
    width, length, expected
):
    assert usace_footing_type(
        footing_width_m=width, footing_length_m=length
    ) == expected


def test_usace_footing_type_rejects_nonpositive_dimensions():
    with pytest.raises(ValueError, match="必須大於 0"):
        usace_footing_type(footing_width_m=0.0, footing_length_m=2.0)
