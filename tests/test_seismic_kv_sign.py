"""Module 5 vertical seismic coefficient magnitude and sign-envelope checks."""
import pytest

from geolysis_engine import (
    seismic_bearing_capacity_pseudostatic,
    seismic_bearing_capacity_residual_pore_pressure_cases,
)


def test_pseudostatic_kv_magnitude_evaluates_both_vertical_directions():
    result = seismic_bearing_capacity_pseudostatic(
        vertical_load_kN=1000.0,
        horizontal_load_kN=100.0,
        footing_area_m2=10.0,
        kh=0.2,
        kv=0.1,
    )
    assert [row["vertical_load_kN"] for row in result["cases"]] == pytest.approx([900.0, 1100.0])
    assert [row["vertical_sign"] for row in result["cases"]] == ["向下減少", "向下增加"]


def test_zero_kv_does_not_mislabel_vertical_load_direction():
    result = seismic_bearing_capacity_pseudostatic(
        vertical_load_kN=1000.0,
        horizontal_load_kN=0.0,
        footing_area_m2=10.0,
        kh=0.0,
        kv=0.0,
    )
    assert all(row["vertical_sign"] == "無垂直增減" for row in result["cases"])


def test_negative_kv_is_rejected_because_direction_is_already_enveloped():
    with pytest.raises(ValueError, match="0≤kv≤0.5"):
        seismic_bearing_capacity_pseudostatic(
            vertical_load_kN=1000.0,
            horizontal_load_kN=0.0,
            footing_area_m2=10.0,
            kh=0.2,
            kv=-0.1,
        )


def test_residual_pore_pressure_cases_reject_negative_kv_magnitude():
    with pytest.raises(ValueError, match="0≤kv≤0.5"):
        seismic_bearing_capacity_residual_pore_pressure_cases(
            vertical_load_kN=1000.0,
            horizontal_load_kN=0.0,
            kh=0.2,
            kv=-0.1,
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
            non_liquefiable_confirmed=True,
            full_shear_zone_confirmed=True,
        )



def test_pseudostatic_horizontal_action_uses_adverse_direction_envelope():
    result = seismic_bearing_capacity_pseudostatic(
        vertical_load_kN=1000.0,
        horizontal_load_kN=100.0,
        footing_area_m2=10.0,
        kh=0.2,
        kv=0.1,
    )
    # Static H and the adverse horizontal earthquake component align:
    # max(|H + khV|, |H - khV|) = H + khV for H, kh, V >= 0.
    assert [row["horizontal_load_kN"] for row in result["cases"]] == pytest.approx([300.0, 300.0])
    assert all("同向（不利包絡）" in row["horizontal_load_direction"] for row in result["cases"])
    assert result["governing_horizontal_load_kN"] == pytest.approx(300.0)



def test_pseudostatic_separates_effective_seismic_weight_from_static_vertical_load():
    result = seismic_bearing_capacity_pseudostatic(
        vertical_load_kN=1000.0,
        horizontal_load_kN=100.0,
        footing_area_m2=10.0,
        kh=0.2,
        kv=0.1,
        seismic_weight_kN=1200.0,
    )
    assert [row["vertical_load_kN"] for row in result["cases"]] == pytest.approx([880.0, 1120.0])
    assert [row["horizontal_load_kN"] for row in result["cases"]] == pytest.approx([340.0, 340.0])
    assert result["seismic_weight_kN"] == pytest.approx(1200.0)


def test_pseudostatic_rejects_vertical_seismic_case_that_reaches_uplift():
    with pytest.raises(ValueError, match="零壓或上拔"):
        seismic_bearing_capacity_pseudostatic(
            vertical_load_kN=100.0,
            horizontal_load_kN=0.0,
            footing_area_m2=10.0,
            kh=0.2,
            kv=0.5,
            seismic_weight_kN=1000.0,
        )
