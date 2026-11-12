"""Runtime smoke test for the complete Streamlit page using Streamlit's AppTest."""
from pathlib import Path
from unittest.mock import patch

import pytest

from streamlit.testing.v1 import AppTest
from geolysis_ui.module4 import _module5_transfer_value, _pmt_transfer_footing_type


ROOT = Path(__file__).resolve().parents[1]


def test_pmt_capacity_transfer_maps_strip_and_rectangular_footings_to_module5_types():
    assert _pmt_transfer_footing_type(2.0, 3.0, False) == "isolated"
    assert _pmt_transfer_footing_type(2.0, 20.0, False) == "isolated"
    assert _pmt_transfer_footing_type(2.0, 21.0, False) == "continuous"
    assert _pmt_transfer_footing_type(2.0, 2.0, True) == "round"


def test_streamlit_app_renders_without_uncaught_exception():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)



def test_module5_hoek_brown_source_selection_uses_explicit_shared_state():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    source = next(widget for widget in app.selectbox if widget.key == "m5_src")
    source.select("模組一 Hoek-Brown 等效參數（一般淺層圍壓擬合）")
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    assert "geolysis_hb_current" in app.session_state
    assert "geolysis_hb_metadata" in app.session_state



def test_module5_hoebrown_source_cannot_bypass_advanced_soil_applicability_guards():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    source = next(widget for widget in app.selectbox if widget.key == "m5_src")
    source.select("模組一 Hoek-Brown 等效參數（一般淺層圍壓擬合）")
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    for key in ("m5x_slope_run", "m5x_layer_run",
                "m5x_multi_layer_run", "m5x_seismic_capacity_run"):
        widget = next(item for item in app.button if item.key == key)
        assert widget.disabled, f"{key} must be disabled until HB foundation applicability is confirmed"

    for key in ("m5x_slide_phi_hb", "m5x_slide_backfill_phi_hb",
                "m5x_auto_c_slope", "m5x_auto_phi_slope"):
        widget = next(item for item in app.number_input if item.key == key)
        assert widget.value == 0.0, f"{key} must not inherit Module 1 HB strength by default"

    for key in ("m5x_c_top_hb", "m5x_phi_top_hb",
                "m5x_c_low_hb", "m5x_phi_low_hb"):
        widget = next(item for item in app.number_input if item.key == key)
        assert widget.value == 0.0, f"{key} must require layer-specific inputs when HB source is selected"



def test_module4_accepts_module5_qult_only_after_geometry_and_condition_confirmation():
    transfer = {
        "transfer_id": "test12345678",
        "qult_gross_kpa": 1200.0,
        "qa_gross_kpa": 410.0,
        "qa_net_kpa": 360.0,
        "qeq_gross_kpa": 180.0,
        "B_m": 2.0,
        "L_m": 3.0,
        "B_effective_m": 1.6,
        "L_effective_m": 2.4,
        "Df_m": 1.5,
        "Dw_m": 2.0,
        "footing_type": "isolated",
        "source": "手動輸入",
        "theory": "Meyerhof",
        "FS_bearing": 6.0,
        "passes_bearing": True,
        "load_confirmed": True,
        "complete_capacity_model": True,
    }
    with (
        patch("geolysis_ui.module4.st.session_state", {"m5_bearing_transfer": transfer}),
        patch("geolysis_ui.module4.st.checkbox", side_effect=[True, True, True]),
        patch("geolysis_ui.module4.st.caption"),
        patch("geolysis_ui.module4.st.warning"),
    ):
        value = _module5_transfer_value(
            key_prefix="test", label="gross qult", field="qult_gross_kpa",
            width_m=2.0, length_m=3.0, footing_type="isolated", depth_m=1.5,
        )
    assert value == (1200.0, 180.0)


def test_module4_rejects_module5_transfer_when_foundation_geometry_differs():
    transfer = {
        "transfer_id": "test12345678", "qult_gross_kpa": 1200.0,
        "qa_net_kpa": 360.0, "qa_gross_kpa": 410.0, "qeq_gross_kpa": 180.0,
        "B_m": 2.0, "L_m": 3.0, "B_effective_m": 1.6, "L_effective_m": 2.4, "Df_m": 1.5, "Dw_m": 2.0,
        "footing_type": "isolated", "source": "手動輸入", "theory": "Meyerhof",
        "FS_bearing": 6.0, "passes_bearing": True,
    }
    with (
        patch("geolysis_ui.module4.st.session_state", {"m5_bearing_transfer": transfer}),
        patch("geolysis_ui.module4.st.checkbox") as checkbox,
        patch("geolysis_ui.module4.st.caption"),
        patch("geolysis_ui.module4.st.warning"),
    ):
        value = _module5_transfer_value(
            key_prefix="test", label="gross qult", field="qult_gross_kpa",
            width_m=2.5, length_m=3.0, footing_type="isolated", depth_m=1.5,
        )
    assert value == (None, None)
    checkbox.assert_not_called()



def test_module5_confirmed_bearing_result_is_published_to_module4():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    loads_confirmed = next(widget for widget in app.checkbox if widget.key == "m5_loads_confirmed")
    loads_confirmed.check()
    app.run()
    calculate = next(widget for widget in app.button if widget.key == "m5_run")
    calculate.click()
    app.run()

    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    transfer = app.session_state["m5_bearing_transfer"]
    assert transfer is not None
    assert transfer["load_confirmed"] is True
    assert transfer["complete_capacity_model"] is True
    assert transfer["qult_gross_kpa"] > 0
    assert transfer["qa_net_kpa"] > 0
    transfer_checkbox_key = f"m4_bb_use_m5_{transfer['transfer_id']}"
    assert any(widget.key == transfer_checkbox_key for widget in app.checkbox)



def test_module5_bishop_methods_require_project_specific_inputs_and_confirmation():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    slice_csv = next(widget for widget in app.text_area if widget.key == "m5x_bishop_csv")
    assert slice_csv.value == ""
    slice_button = next(widget for widget in app.button if widget.key == "m5x_bishop_run")
    assert slice_button.disabled

    profile_csv = next(widget for widget in app.text_area if widget.key == "m5x_profile")
    assert profile_csv.value == ""
    bishop_c = next(widget for widget in app.number_input if widget.key == "m5x_auto_c_slope")
    bishop_phi = next(widget for widget in app.number_input if widget.key == "m5x_auto_phi_slope")
    assert bishop_c.value == 0.0
    assert bishop_phi.value == 0.0
    auto_button = next(widget for widget in app.button if widget.key == "m5x_auto_bishop_run")
    assert auto_button.disabled
    static_scope_warnings = [item.value for item in app.warning]
    assert any("僅為靜態圓弧滑動分析" in value and "不含 kh／kv" in value
               for value in static_scope_warnings)
    assert any("同樣僅計算靜態 Bishop FS" in value and "不含 kh／kv" in value
               for value in static_scope_warnings)


def test_module5_residual_base_pressure_confirmation_gates_seismic_qallow():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    qallow = next(widget for widget in app.number_input if widget.key == "m5x_seismic_qallow")
    qallow.set_value(100.0)
    app.run()
    pressure = next(widget for widget in app.number_input if widget.key == "m5x_residual_base_u")
    confirmation = next(widget for widget in app.checkbox if widget.key == "m5x_residual_base_u_confirm")
    assert confirmation.value is False

    calculate = next(widget for widget in app.button if widget.key == "m5x_seismic_ecc_run")
    calculate.click()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    result = app.session_state["m5x_seismic_ecc_result"]
    assert result["bearing_pressure_check_complete"] is False

    pressure = next(widget for widget in app.number_input if widget.key == "m5x_residual_base_u")
    pressure.set_value(12.0)
    app.run()
    assert app.session_state["m5x_residual_base_u"] == 12.0
    confirmation = next(widget for widget in app.checkbox if widget.key == "m5x_residual_base_u_confirm")
    confirmation.check()
    app.run()
    assert app.session_state["m5x_residual_base_u_confirm"] is True
    calculate = next(widget for widget in app.button if widget.key == "m5x_seismic_ecc_run")
    calculate.click()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    result = app.session_state["m5x_seismic_ecc_result"]
    assert abs(result["base_uplift_pressure_kpa"] - 12.0) < 1e-6
    assert result["bearing_pressure_check_complete"] is True


def test_module1_fhwa_quantitative_gsi_mode_renders_and_calculates():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    method = next(widget for widget in app.radio if widget.key == "gsi_method")
    method.set_value("鑽孔定量估算（FHWA Eq. 9-19）")
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    rqd = next(widget for widget in app.text_input if widget.key == "gsi_quant_rqd_text")
    rqd.set_value("80")
    choices = {
        "gsi_jcond_persistence": "小於 1 m（6）",
        "gsi_jcond_separation": "小於 0.1 mm（5）",
        "gsi_jcond_roughness": "粗糙（5）",
        "gsi_jcond_infilling": "硬質充填小於 5 mm（4）",
        "gsi_jcond_weathering": "微風化（5）",
    }
    for key, value in choices.items():
        widget = next(item for item in app.selectbox if item.key == key)
        widget.select(value)
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    gsi_input = next(item for item in app.number_input if item.label == "GSI 代表值（可直接調整）")
    assert gsi_input.value == 77.5


def test_module5_defaults_uplift_force_from_base_pressure_and_full_footing_area():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    water = next(widget for widget in app.number_input if widget.key == "m5_dw")
    water.set_value(0.0)
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    # Default Df=1.5 m, B=2 m, L=3 m; u_D=(Df-Dw)*9.81 kPa.
    expected_u = 1.5 * 9.81 * 2.0 * 3.0
    uplift_widget = next(widget for widget in app.number_input if widget.key.startswith("m5x_slide_u_"))
    assert uplift_widget.value == pytest.approx(expected_u)
    assert "可覆寫" in uplift_widget.label


def test_module5_residual_base_pressure_only_increases_uplift_reference_for_seismic_case():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    next(widget for widget in app.number_input if widget.key == "m5_dw").set_value(0.0)
    next(widget for widget in app.number_input if widget.key == "m5x_residual_base_u").set_value(12.0)
    next(widget for widget in app.checkbox if widget.key == "m5x_residual_base_u_confirm").check()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    static_u = next(widget for widget in app.number_input if widget.key.startswith("m5x_slide_u_"))
    expected_hydrostatic = 1.5 * 9.81 * 2.0 * 3.0
    assert static_u.value == pytest.approx(expected_hydrostatic)

    next(widget for widget in app.selectbox if widget.key == "m5x_slide_case").select("含地震荷載")
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    seismic_u = next(widget for widget in app.number_input if widget.key.startswith("m5x_slide_u_"))
    assert seismic_u.value == pytest.approx((1.5 * 9.81 + 12.0) * 2.0 * 3.0)


def test_module5_seismic_uplift_exposes_dead_load_interpretation_caveat():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    warnings = [item.value for item in app.warning]
    assert any("§5-7(b)" in value and "§9-10(f)" in value and "Wf、Wc" in value
               for value in warnings)
    weight_confirmation = next(
        widget for widget in app.checkbox if widget.key == "m5x_uplift_weights_confirm"
    )
    assert "依本案適用規範確認地震抗浮可採 Wf+Ws+Wc" in weight_confirmation.label


def test_module1_alishan_tunnel_case_can_be_selected_and_calculated_in_streamlit():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    preset = "砂岩／頁岩互層（阿里山森林鐵路42號隧道案例）"
    rock = next(widget for widget in app.selectbox if widget.key == "hb_rock_type_for_mi")
    rock.select(preset)
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    case_key = f"hb_ucs_case_{preset}"
    ucs_case = next(widget for widget in app.selectbox if widget.key == case_key)
    expected_case = "阿里山42號隧道｜邊坡設計 UCS 43.3 MPa"
    assert expected_case in ucs_case.options
    ucs_case.select(expected_case)

    disturbance = next(widget for widget in app.selectbox if widget.label == "開挖/自然擾動程度參考 (D)")
    disturbance.select("弱岩機械開挖且有明顯應力鬆弛損傷 (D = 0.7)")
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)


def test_module5_seismic_sliding_hides_static_rankine_auto_pressure_and_gates_run_on_manual_confirmation():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    load_case = next(widget for widget in app.selectbox if widget.key == "m5x_slide_case")
    load_case.select("含地震荷載")
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    assert not any(widget.key == "m5x_slide_auto_earth" for widget in app.checkbox)
    assert any(widget.key == "m5x_slide_seismic_earth_pressure_confirm" for widget in app.checkbox)
    assert not any(widget.key == "m5x_slide_gamma" for widget in app.number_input)
    assert not any(str(widget.key).startswith("m5x_slide_backfill_phi_") for widget in app.number_input)
    assert not any(str(widget.key).startswith("m5x_slide_backfill_c_") for widget in app.number_input)

    uplift = next(widget for widget in app.number_input if widget.label.startswith("基底揚壓力合力 U"))
    uplift.set_value(1.0)
    pressure_confirm = next(widget for widget in app.checkbox if widget.key == "m5x_uplift_pressure_confirm")
    pressure_confirm.check()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    slide_button = next(widget for widget in app.button if widget.key == "m5x_slide_run")
    assert slide_button.disabled is True

    earth_pressure_confirm = next(
        widget for widget in app.checkbox if widget.key == "m5x_slide_seismic_earth_pressure_confirm"
    )
    earth_pressure_confirm.check()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    slide_button = next(widget for widget in app.button if widget.key == "m5x_slide_run")
    assert slide_button.disabled is False


def test_module4_single_consolidation_layer_cannot_extend_above_foundation_base():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    method = next(widget for widget in app.selectbox if widget.key == "m4_method")
    method.set_value("黏土：一維主固結沉陷控制法")
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    layer_center = next(widget for widget in app.number_input if widget.key == "m4c_z")
    layer_center.set_value(1.0)
    layer_thickness = next(widget for widget in app.number_input if widget.key == "m4c_h")
    layer_thickness.set_value(5.0)
    app.run()

    assert any("壓縮層頂面位於基礎底以上" in item.value for item in app.error)



def test_module4_burland_settlement_uses_transferred_qeq_in_actual_calculation():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    # Produce a genuine transfer by running Module 5 through its public UI.
    loads_confirmed = next(widget for widget in app.checkbox if widget.key == "m5_loads_confirmed")
    loads_confirmed.check()
    app.run()
    calculate = next(widget for widget in app.button if widget.key == "m5_run")
    calculate.click()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    transfer = app.session_state["m5_bearing_transfer"]
    assert transfer is not None
    assert transfer["qeq_gross_kpa"] > 0
    transfer_id = transfer["transfer_id"]

    use_qult = next(
        widget for widget in app.checkbox
        if widget.key == f"m4_bb_use_m5_{transfer_id}"
    )
    use_qult.check()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    conditions_key = (
        f"m4_bb_conditions_{transfer_id}_"
        f"{transfer['B_m']:.2f}_{transfer['L_m']:.2f}_{1.5:.2f}_any"
    )
    conditions = next(widget for widget in app.checkbox if widget.key == conditions_key)
    conditions.check()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    use_qeq = next(
        widget for widget in app.checkbox
        if widget.key == f"m4_bb_use_m5_qeq_{transfer_id}"
    )
    use_qeq.check()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    # The default manual q is 150 kPa. The displayed adopted pressure must
    # equal the real Module 5 qeq, proving the Burland path consumes qeq.
    expected = f"目前 q 採用值 = {transfer['qeq_gross_kpa']:.1f} kPa"
    assert any(expected in item.value for item in app.markdown)


def test_module4_burland_eccentric_settlement_uses_effective_dimensions():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    eccentric = next(
        widget for widget in app.checkbox
        if widget.key == "m4_bb_eccentric_settlement"
    )
    eccentric.check()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    next(widget for widget in app.number_input if widget.key == "m4_bb_settlement_eb").set_value(0.10)
    next(widget for widget in app.number_input if widget.key == "m4_bb_settlement_el").set_value(0.20)
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    assert any("B′=1.800 m、L′=2.600 m" in item.value for item in app.caption)
    # Burland influence depth must use B'=1.8 m, not the physical B=2.0 m.
    assert any("影響深度 Zi = 1.51 m" in item.value for item in app.markdown)


@pytest.mark.parametrize(
    ("method_label", "method_key", "csv_key", "csv_text"),
    [
        (
            "DMT：增量拘束模數法（USACE 2025）",
            "m4_dmt_mode",
            "m4_dmt_layers",
            "Layer,depth_center_m,thickness_m,MDMT_kpa\n1,0.5,1.0,10000\n2,1.5,1.0,10000\n3,2.5,1.0,10000\n4,3.5,1.0,10000",
        ),
        (
            "CPT：Schmertmann 沉陷法（USACE 2025）",
            None,
            "m4_cpt_layers",
            "Layer,thickness_m,qc_kpa\n1,1.0,8000\n2,1.0,8500\n3,1.0,9000\n4,1.0,9500\n5,1.0,10000",
        ),
        (
            "PMT：Ménard–Rousseau 法（USACE 2025）",
            None,
            "m4_pmt_layers",
            "group,E0_kpa\nE1,12000\nE2,13000\nE345,14000\nE678,15000\nE916,16000",
        ),
    ],
)
def test_module4_dmt_cpt_pmt_actual_calculations_use_module5_qeq(
    method_label, method_key, csv_key, csv_text
):
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    next(widget for widget in app.checkbox if widget.key == "m5_loads_confirmed").check()
    app.run()
    next(widget for widget in app.button if widget.key == "m5_run").click()
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    transfer = app.session_state["m5_bearing_transfer"]
    assert transfer is not None
    assert transfer["qeq_gross_kpa"] < transfer["qult_gross_kpa"] / 3.0

    next(widget for widget in app.selectbox if widget.key == "m4_method").select(method_label)
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)

    # Match Module 5's physical 2 m × 3 m footing before accepting the transfer.
    geometry_key = {
        "DMT：增量拘束模數法（USACE 2025）": "m4_dmt_l",
        "CPT：Schmertmann 沉陷法（USACE 2025）": "m4_cpt_l",
        "PMT：Ménard–Rousseau 法（USACE 2025）": "m4_pmt_l",
    }[method_label]
    next(widget for widget in app.number_input if widget.key == geometry_key).set_value(3.0)
    app.run()

    prefix = {
        "DMT：增量拘束模數法（USACE 2025）": "m4_dmt",
        "CPT：Schmertmann 沉陷法（USACE 2025）": "m4_cpt",
        "PMT：Ménard–Rousseau 法（USACE 2025）": "m4_pmt",
    }[method_label]
    transfer_id = transfer["transfer_id"]
    next(widget for widget in app.checkbox if widget.key == f"{prefix}_use_m5_{transfer_id}").check()
    app.run()
    condition_key = f"{prefix}_conditions_{transfer_id}_2.00_3.00_0.00_isolated"
    next(widget for widget in app.checkbox if widget.key == condition_key).check()
    app.run()
    next(widget for widget in app.checkbox if widget.key == f"{prefix}_use_m5_qeq_{transfer_id}").check()

    if method_key:
        next(widget for widget in app.selectbox if widget.key == method_key).select("MDMT")
    if prefix == "m4_cpt":
        next(widget for widget in app.checkbox if widget.key == "m4_cpt_soil_confirm").check()
    if prefix == "m4_pmt":
        next(widget for widget in app.number_input if widget.key == "m4_pmt_pne").set_value(1500.0)
        next(widget for widget in app.number_input if widget.key == "m4_pmt_py").set_value(1000.0)
        next(widget for widget in app.checkbox if widget.key == "m4_pmt_deep_confirm").check()
        next(widget for widget in app.checkbox if widget.key == "m4_pmt_lambda_confirm").check()
    next(widget for widget in app.text_area if widget.key == csv_key).set_value(csv_text)
    app.run()
    assert not app.exception, "\n".join(str(item.message) for item in app.exception)
    calculation_errors = [
        item.value for item in app.error
        if any(token in item.value for token in ("DMT 沉陷估算失敗", "CPT 沉陷估算失敗", "PMT 沉陷估算失敗"))
    ]
    assert not calculation_errors, (
        f"{calculation_errors}; state="
        f"{[(key, app.session_state.get(key)) for key in ('m4_dmt_b','m4_dmt_l','m4_dmt_q','m4_dmt_fs','m4_dmt_mode','m4_dmt_layers','m4_cpt_b','m4_cpt_l','m4_cpt_q','m4_cpt_fs','m4_cpt_layers','m4_cpt_soil_confirm','m4_pmt_b','m4_pmt_l','m4_pmt_q','m4_pmt_fs','m4_pmt_layers','m4_pmt_pne','m4_pmt_py')]}; transfer={app.session_state.get('m5_bearing_transfer')}"
    )
    expected = f"採用 gross 壓力 = {transfer['qeq_gross_kpa']:.1f} kPa"
    assert any(expected in item.value for item in app.markdown)


def test_module2_classification_result_clears_when_confirmation_is_revoked():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception, "\\n".join(str(item.message) for item in app.exception)

    next(widget for widget in app.checkbox if widget.key == "m2_data_confirm").check()
    app.run()
    next(widget for widget in app.button if widget.key == "m2_run").click()
    app.run()
    assert app.session_state.get("m2_result") is not None

    next(widget for widget in app.checkbox if widget.key == "m2_data_confirm").uncheck()
    app.run()
    assert app.session_state.get("m2_result") is None
