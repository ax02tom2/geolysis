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
