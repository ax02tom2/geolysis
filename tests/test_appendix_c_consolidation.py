"""USACE Appendix C consolidation and excavation-rebound benchmarks."""
import pytest

from geolysis_engine import (
    consolidation_settlement_1d,
    excavation_rebound_recompression_layers,
)


def test_usace_2025_appendix_c1_clay_e_log_p_settlement():
    # EM 1110-1-1905 (31 Jul 2025), Appendix C, Example C-1, Table C-1.
    # Six layer rows from the published table; Cc/(1+e0) and Cr/(1+e0)
    # are transcribed directly. e0=1 is used only to reconstruct Cc and Cr
    # while preserving the published normalized ratios.
    ft_to_m = 0.3048
    tsf_to_kpa = 95.7605
    rows = [
        (1.0, 0.15, 0.79, 0.44, 0.113, 0.012),
        (2.0, 0.24, 0.88, 0.40, 0.113, 0.012),
        (2.0, 0.33, 0.97, 0.28, 0.113, 0.012),
        (3.0, 0.40, 1.04, 0.16, 0.113, 0.012),
        (3.0, 0.49, 5.89, 0.09, 0.048, 0.006),
        (3.0, 0.59, 5.99, 0.05, 0.048, 0.006),
    ]
    settlements_ft = []
    for thickness_ft, sigma0, sigmap, delta_sigma, cc_ratio, cr_ratio in rows:
        result = consolidation_settlement_1d(
            layer_thickness_m=thickness_ft * ft_to_m,
            initial_void_ratio=1.0,
            compression_index=2.0 * cc_ratio,
            recompression_index=2.0 * cr_ratio,
            initial_effective_stress_kpa=sigma0 * tsf_to_kpa,
            preconsolidation_stress_kpa=sigmap * tsf_to_kpa,
            stress_increase_kpa=delta_sigma * tsf_to_kpa,
        )
        settlements_ft.append(result["settlement_m"] / ft_to_m)

    assert sum(settlements_ft) == pytest.approx(0.0309, abs=0.0002)
    assert sum(settlements_ft) * 12.0 == pytest.approx(0.37, abs=0.01)


def test_usace_2025_appendix_c4_layered_rebound_and_recompression():
    # EM 1110-1-1905 (31 Jul 2025), Appendix C, Example C-4, Table C-4.
    # The e-log-p curve supplies separate e0, e_exc and e_final values.
    # Rebound thickness differs from recompression thickness because the
    # recompression zone is limited to the footing's 2B influence depth.
    ft_to_m = 0.3048
    tsf_to_kpa = 95.7605
    layers = [
        {
            "Layer": 2,
            "rebound_thickness_m": 8.0 * ft_to_m,
            "recompression_thickness_m": 6.0 * ft_to_m,
            "initial_effective_stress_kpa": 0.54 * tsf_to_kpa,
            "excavation_effective_stress_kpa": 0.10 * tsf_to_kpa,
            "final_effective_stress_kpa": 1.41 * tsf_to_kpa,
            "e0": 0.947, "e_exc": 0.964, "e_final": 0.805,
        },
        {
            "Layer": 3,
            "rebound_thickness_m": 14.0 * ft_to_m,
            "recompression_thickness_m": 8.0 * ft_to_m,
            "initial_effective_stress_kpa": 0.82 * tsf_to_kpa,
            "excavation_effective_stress_kpa": 0.58 * tsf_to_kpa,
            "final_effective_stress_kpa": 0.83 * tsf_to_kpa,
            "e0": 0.991, "e_exc": 0.999, "e_final": 0.983,
        },
    ]
    result = excavation_rebound_recompression_layers(layers=layers)

    assert result["rebound_mm"] / (12.0 * 25.4) == pytest.approx(-0.1261, abs=0.002)
    assert result["recompression_settlement_mm"] / (12.0 * 25.4) == pytest.approx(0.5498, abs=0.002)
    assert result["net_settlement_mm"] / (12.0 * 25.4) == pytest.approx(0.4237, abs=0.003)
    assert len(result["layer_results"]) == 2


def test_layered_rebound_recompression_rejects_inconsistent_stress_and_void_ratio_paths():
    with pytest.raises(ValueError, match="孔隙比方向不符"):
        excavation_rebound_recompression_layers(layers=[{
            "rebound_thickness_m": 2.0,
            "recompression_thickness_m": 1.0,
            "initial_effective_stress_kpa": 100.0,
            "excavation_effective_stress_kpa": 50.0,
            "final_effective_stress_kpa": 120.0,
            "e0": 0.8, "e_exc": 0.7, "e_final": 0.6,
        }])
