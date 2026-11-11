"""USACE Appendix C consolidation and excavation-rebound benchmarks."""
import pytest
from geolysis_engine import consolidation_settlement_1d, excavation_rebound_recompression_layers


def test_usace_2025_appendix_c1_clay_e_log_p_settlement():
    # EM 1110-1-1905 (31 Jul 2025), Appendix C, Example C-1, Table C-1.
    # Cc/(1+e0) and Cr/(1+e0) are transcribed directly; e0=1 reconstructs
    # the indices while preserving those published normalized ratios.
    ft_to_m, tsf_to_kpa = 0.3048, 95.7605
    rows = [
        (1.0, .15, .79, .44, .113, .012),
        (2.0, .24, .88, .40, .113, .012),
        (2.0, .33, .97, .28, .113, .012),
        (3.0, .40, 1.04, .16, .113, .012),
        (3.0, .49, 5.89, .09, .048, .006),
        (3.0, .59, 5.99, .05, .048, .006),
    ]
    settlement_ft = []
    for h, s0, sp, ds, cc_ratio, cr_ratio in rows:
        r = consolidation_settlement_1d(
            layer_thickness_m=h * ft_to_m, initial_void_ratio=1.0,
            compression_index=2.0 * cc_ratio, recompression_index=2.0 * cr_ratio,
            initial_effective_stress_kpa=s0 * tsf_to_kpa,
            preconsolidation_stress_kpa=sp * tsf_to_kpa,
            stress_increase_kpa=ds * tsf_to_kpa,
        )
        settlement_ft.append(r["settlement_m"] / ft_to_m)
    assert sum(settlement_ft) == pytest.approx(.0309, abs=.0002)
    assert sum(settlement_ft) * 12.0 == pytest.approx(.37, abs=.01)


def test_usace_2025_appendix_c4_layered_rebound_and_recompression():
    # EM 1110-1-1905 (31 Jul 2025), Appendix C, Example C-4, Table C-4.
    # Rebound and recompression use separate thicknesses; e-log-p void ratios
    # are read at initial, excavation and final stress for each stratum.
    ft_to_m, tsf_to_kpa = 0.3048, 95.7605
    layers = [
        {
            "Layer": 2, "rebound_thickness_m": 8.0 * ft_to_m,
            "recompression_thickness_m": 6.0 * ft_to_m,
            "initial_effective_stress_kpa": .54 * tsf_to_kpa,
            "excavation_effective_stress_kpa": .10 * tsf_to_kpa,
            "final_effective_stress_kpa": 1.41 * tsf_to_kpa,
            "e0": .947, "e_exc": .964, "e_final": .805,
        },
        {
            "Layer": 3, "rebound_thickness_m": 14.0 * ft_to_m,
            "recompression_thickness_m": 8.0 * ft_to_m,
            "initial_effective_stress_kpa": .82 * tsf_to_kpa,
            "excavation_effective_stress_kpa": .58 * tsf_to_kpa,
            "final_effective_stress_kpa": .83 * tsf_to_kpa,
            "e0": .991, "e_exc": .999, "e_final": .983,
        },
    ]
    r = excavation_rebound_recompression_layers(layers=layers)
    assert r["rebound_mm"] / (12.0 * 25.4) == pytest.approx(-.1261, abs=.002)
    assert r["recompression_settlement_mm"] / (12.0 * 25.4) == pytest.approx(.5498, abs=.002)
    assert r["net_settlement_mm"] / (12.0 * 25.4) == pytest.approx(.4237, abs=.003)
    assert len(r["layer_results"]) == 2


def test_layered_rebound_recompression_rejects_inconsistent_void_ratio_path():
    with pytest.raises(ValueError, match="孔隙比方向不符"):
        excavation_rebound_recompression_layers(layers=[{
            "rebound_thickness_m": 2.0, "recompression_thickness_m": 1.0,
            "initial_effective_stress_kpa": 100.0,
            "excavation_effective_stress_kpa": 50.0,
            "final_effective_stress_kpa": 120.0,
            "e0": .8, "e_exc": .7, "e_final": .6,
        }])
