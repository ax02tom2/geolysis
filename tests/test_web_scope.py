from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
UI_FILES = sorted((ROOT / "geolysis_ui").glob("module*.py"))
UI_SOURCE = "\n".join(path.read_text(encoding="utf-8") for path in UI_FILES)
MODULE1 = (ROOT / "geolysis_ui" / "module1.py").read_text(encoding="utf-8")
APP_AND_UI = APP + "\n" + UI_SOURCE


def test_five_engineering_modules_remain():
    for label in ("模組一：岩體參數分析", "模組二：土壤分類", "模組三：SPT", "模組四：容許承載力", "模組五：極限承載力"):
        assert label in APP_AND_UI
    assert len(UI_FILES) == 5
    for index, path in enumerate(UI_FILES, start=1):
        assert f"def render_module_{index}(" in path.read_text(encoding="utf-8")


def test_core_log_upload_and_image_rqd_estimation_are_removed():
    forbidden = (
        "render_core_log_analysis",
        "core_log_parser",
        "core_photo_analysis",
        "岩心柱狀圖解析",
        "上傳整孔岩心柱狀圖",
        "RQD 影像初估",
        "逐列 RQD 初估",
    )
    for token in forbidden:
        assert token not in APP_AND_UI
    for path in (
        ROOT / "geolysis_ui" / "core_log.py",
        ROOT / "core_log_parser.py",
        ROOT / "core_photo_analysis.py",
    ):
        assert not path.exists()


def test_module1_has_no_rqd_input_or_fhwa_quantitative_gsi():
    assert "RQD" not in MODULE1.upper()
    assert "gsi_quant_rqd_text" not in MODULE1
    assert "FHWA Eq. 9.19" not in MODULE1


def test_image_and_document_parsing_dependencies_are_removed():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for dependency in ("opencv-python", "PyMuPDF", "python-docx"):
        assert dependency not in requirements


def test_sidebar_module_selection_matches_expander_labels():
    assert 'exp_1 = display_mode in ["全部展開", "模組一：岩體參數分析"]' in APP
    assert "模組一：岩體參數與岩心分析" not in APP



def test_module5_seismic_guidance_matches_implemented_base_pressure_and_uplift_checks():
    module5 = (ROOT / "geolysis_ui" / "module5.py").read_text(encoding="utf-8")
    assert "仍未納入基底殘餘超額孔壓上拔" not in module5
    assert "基底殘餘超額孔壓可由使用者確認輸入並納入 qeq" in module5
    assert "獨立 §9-10(f) 地震抗浮 FS≥1.5 檢核" in module5
    assert "全基底總揚壓合力 U 仍須由使用者依孔壓分布積分輸入" in module5
    assert "目前仍未包含土體慣性力" in module5


def test_module5_layered_insitu_csv_does_not_prefill_example_measurements():
    module5 = (ROOT / "geolysis_ui" / "module5.py").read_text(encoding="utf-8")
    assert 'value="thickness_m,test_type,drainage,measurements"' in module5
    assert '1.5,SPT,drained,20;22;18' not in module5
    assert '2.0,SPT,undrained,4;5;4' not in module5
    assert "系統不預填示範數值" in module5


def test_module5_multilayer_soil_profile_does_not_synthesize_default_layers():
    module5 = (ROOT / "geolysis_ui" / "module5.py").read_text(encoding="utf-8")
    assert 'value="thickness_m,c_kpa,phi_deg,gamma_below_kn_m3"' in module5
    assert '1.0,{c_top5},{phi_top5},{gamma_below5}' not in module5
    assert '2.0,{c_low5},{phi_low5},{gamma_below5}' not in module5
    assert "不會將主分析土壤參數複製成假設地層" in module5


def test_module5_two_layer_punching_requires_project_data_confirmation():
    module5 = (ROOT / "geolysis_ui" / "module5.py").read_text(encoding="utf-8")
    assert 'key="m5x_layer_data_confirmed"' in module5
    assert "or not layer_data_confirmed5" in module5
    assert "主分析參數或預設 0 值誤當成實測資料" in module5
    assert module5.count("bool(layer_data_confirmed5)") >= 2
