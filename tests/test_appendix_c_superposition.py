"""USACE Appendix C-2/C-3 superposition and consolidation-time benchmarks."""
import pytest
from geolysis_engine import (
    consolidation_settlement_layers_from_stress_profile,
    consolidation_time_rate,
)

FT_TO_M = 0.3048
TSF_TO_KPA = 95.7605


def _layers_from_table(thickness_ft, depth_ft, sigma0_tsf, sigmap_tsf,
                       delta_tsf, cc_ratio, cr_ratio):
    rows = []
    for i, values in enumerate(zip(
        thickness_ft, depth_ft, sigma0_tsf, sigmap_tsf,
        delta_tsf, cc_ratio, cr_ratio
    ), 1):
        h, z, s0, sp, ds, cc, cr = values
        rows.append({
            "Layer": i,
            "Depth_center_m": z * FT_TO_M,
            "Thickness_m": h * FT_TO_M,
            # Reconstruct Cc and Cr from the published normalized indices.
            # e0=1 preserves C/(1+e0) exactly.
            "e0": 1.0,
            "Cc": 2.0 * cc,
            "Cr": 2.0 * cr,
            "Sigma0_kPa": s0 * TSF_TO_KPA,
            "SigmaP_kPa": sp * TSF_TO_KPA,
            "Delta_sigma_kPa": ds * TSF_TO_KPA,
        })
    return rows


def test_usace_2025_appendix_c2_superimposed_footings_at_point_b_and_e():
    # EM 1110-1-1905 (31 Jul 2025), Appendix C, Table C-2.
    h = [1, 2, 2, 3, 3, 3]
    z = [.5, 2, 4, 6.5, 9.5, 12.5]
    s0 = [.15, .24, .33, .40, .49, .59]
    sp = [.79, .88, .97, 1.04, 5.89, 5.99]
    cc = [.113, .113, .113, .113, .048, .048]
    cr = [.012, .012, .012, .012, .006, .006]

    # Point B: isolated footing plus adjacent strip footing, using the
    # final settlement table's Δσz values. The preceding stress summary has
    # one inconsistent layer-6 entry; .08 tsf agrees with σzf=.67 and δc=.001.
    point_b = consolidation_settlement_layers_from_stress_profile(layers=_layers_from_table(
        h, z, s0, sp, [.44, .40, .29, .18, .12, .08], cc, cr
    ))
    point_e = consolidation_settlement_layers_from_stress_profile(layers=_layers_from_table(
        h, z, s0, sp, [.32, .21, .17, .13, .09, .07], cc, cr
    ))
    assert point_b["settlement_mm"] / (12.0 * 25.4) == pytest.approx(.0324, abs=.0003)
    assert point_e["settlement_mm"] / (12.0 * 25.4) == pytest.approx(.0235, abs=.0003)


def test_usace_2025_appendix_c3a_areal_fill_only_settlement():
    # EM 1110-1-1905 (31 Jul 2025), Appendix C, Table C-3a.
    h = [2, 1, 2, 2, 3, 3, 3, 4, 5]
    z = [1, 2.5, 3.5, 6, 8.5, 11.5, 14.5, 18, 22.5]
    s0 = [.06, .15, .21, .33, .40, .49, .59, .69, .84]
    sp = [.70, .79, .85, .97, 1.04, 5.89, 5.99, 6.09, 6.24]
    cc = [.113] * 5 + [.048] * 4
    cr = [.012] * 5 + [.006] * 4
    result = consolidation_settlement_layers_from_stress_profile(layers=_layers_from_table(
        h, z, s0, sp, [.54] * 9, cc, cr
    ))
    assert result["settlement_mm"] / (12.0 * 25.4) == pytest.approx(.092, abs=.001)


def test_usace_2025_appendix_c3b_areal_fill_plus_footing_settlement():
    # EM 1110-1-1905 (31 Jul 2025), Appendix C, Table C-3b.
    h = [2, 1, 2, 2, 3, 3, 3, 4, 5]
    # Depths are measured below the footing base; the first layer begins
    # 6 ft below grade because compacted structural fill occupies that zone.
    z = [7, 8.5, 9.5, 12, 14.5, 17.5, 20.5, 24, 28.5]
    s0 = [.06, .15, .21, .33, .40, .49, .59, .69, .84]
    sp = [.70, .79, .85, .97, 1.04, 5.89, 5.99, 6.09, 6.24]
    cc = [.113] * 5 + [.048] * 4
    cr = [.012] * 5 + [.006] * 4
    footing_delta = [.31, .23, .19, .13, .09, .06, .05, .03, .02]
    total_delta = [x + .54 for x in footing_delta]
    result = consolidation_settlement_layers_from_stress_profile(layers=_layers_from_table(
        h, z, s0, sp, total_delta, cc, cr
    ))
    assert result["settlement_mm"] / (12.0 * 25.4) == pytest.approx(.145, abs=.001)


def test_usace_2025_appendix_c3c_time_to_70_percent_consolidation():
    # Table C-3c: Cv=0.412 ft²/day, Hdr=25/2 ft, Tv=0.403 at U=70%.
    cv_m2_day = .412 * FT_TO_M ** 2
    result = consolidation_time_rate(
        primary_settlement_mm=1.10 * 25.4,
        layer_thickness_m=25.0 * FT_TO_M,
        cv_m2_per_day=cv_m2_day,
        target_degree_percent=70.0,
        elapsed_days=0.0,
        drainage="double",
    )
    assert result["time_factor_target"] == pytest.approx(.403, abs=.002)
    assert result["time_to_target_days"] == pytest.approx(152.8, abs=1.0)
