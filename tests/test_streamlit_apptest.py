"""Runtime smoke test for the complete Streamlit page using Streamlit's AppTest."""
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from geolysis_ui.module4 import _module5_transfer_value


ROOT = Path(__file__).resolve().parents[1]


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
        patch("geolysis_ui.module4.st.checkbox", side_effect=[True, True]),
        patch("geolysis_ui.module4.st.caption"),
        patch("geolysis_ui.module4.st.warning"),
    ):
        value = _module5_transfer_value(
            key_prefix="test", label="gross qult", field="qult_gross_kpa",
            width_m=2.0, length_m=3.0, footing_type="isolated", depth_m=1.5,
        )
    assert value == 1200.0


def test_module4_rejects_module5_transfer_when_foundation_geometry_differs():
    transfer = {
        "transfer_id": "test12345678", "qult_gross_kpa": 1200.0,
        "qa_net_kpa": 360.0, "qa_gross_kpa": 410.0, "qeq_gross_kpa": 180.0,
        "B_m": 2.0, "L_m": 3.0, "Df_m": 1.5, "Dw_m": 2.0,
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
    assert value is None
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
    assert not app.exception, "\\n".join(str(item.message) for item in app.exception)

    method = next(widget for widget in app.radio if widget.key == "gsi_method")
    method.set_value("鑽孔定量估算（FHWA Eq. 9-19）")
    app.run()
    assert not app.exception, "\\n".join(str(item.message) for item in app.exception)

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
    assert not app.exception, "\\n".join(str(item.message) for item in app.exception)
    gsi_input = next(item for item in app.number_input if item.label == "GSI 代表值（可直接調整）")
    assert gsi_input.value == 77.5


def test_module1_quantitative_gsi_imports_only_completed_core_photo_rqd_rows():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    def seed_core_rqd():
        app.session_state["core_log_rqd_summary"] = [
            {"depth": "0.0–1.0m", "rqd_percent": 70.0, "review": "完成", "depth_length_m": 1.0},
            {"depth": "1.0–2.0m", "rqd_percent": 90.0, "review": "完成", "depth_length_m": 1.0},
            {"depth": "2.0–3.0m", "rqd_percent": 100.0, "review": "有不確定區", "depth_length_m": 1.0},
        ]
        app.session_state["core_log_rqd_source"] = {"filename": "borehole_core.pdf"}

    method = next(widget for widget in app.radio if widget.key == "gsi_method")
    seed_core_rqd()
    method.set_value("鑽孔定量估算（FHWA Eq. 9-19）")
    app.run()

    seed_core_rqd()
    depths = next(widget for widget in app.multiselect if widget.key == "gsi_quant_rqd_depths")
    depths.set_value(["0.0–1.0m", "1.0–2.0m"])
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
    seed_core_rqd()
    app.run()

    assert not app.exception, "\\n".join(str(item.message) for item in app.exception)
    rqd_metric = next(item for item in app.metric if item.label == "所選深度區間加權平均 RQD")
    assert rqd_metric.value == "80.0%"
    gsi_input = next(item for item in app.number_input if item.label == "GSI 代表值（可直接調整）")
    assert gsi_input.value == 77.5
