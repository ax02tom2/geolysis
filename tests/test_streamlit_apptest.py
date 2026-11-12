"""Runtime smoke test for the complete Streamlit page using Streamlit's AppTest."""
from pathlib import Path

from streamlit.testing.v1 import AppTest


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
                "m5x_auto_c_hb", "m5x_auto_phi_hb"):
        widget = next(item for item in app.number_input if item.key == key)
        assert widget.value == 0.0, f"{key} must not inherit Module 1 HB strength by default"

    for key in ("m5x_c_top_hb", "m5x_phi_top_hb",
                "m5x_c_low_hb", "m5x_phi_low_hb"):
        widget = next(item for item in app.number_input if item.key == key)
        assert widget.value == 0.0, f"{key} must require layer-specific inputs when HB source is selected"
