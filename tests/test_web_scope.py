from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
UI_FILES = sorted((ROOT / "geolysis_ui").glob("module*.py"))
UI_SOURCE = "\n".join(path.read_text(encoding="utf-8") for path in UI_FILES)
CORE_UI = (ROOT / "geolysis_ui" / "core_log.py").read_text(encoding="utf-8")
APP_AND_UI = APP + "\n" + UI_SOURCE + "\n" + CORE_UI


def test_five_engineering_modules_remain():
    for label in ("模組一：Hoek-Brown", "模組二：土壤分類", "模組三：SPT", "模組四：容許承載力", "模組五：極限承載力"):
        assert label in APP_AND_UI


def test_docx_pdf_core_log_and_rqd_workflow_is_available_in_web_app():
    assert "岩心柱狀圖解析與 RQD 初估" in CORE_UI
    assert "上傳整孔岩心柱狀圖" in CORE_UI
    assert "天然節理" in CORE_UI
    assert "機械破損" in CORE_UI
    for forbidden in ("qwen3-vl", "ollama_status", "core_local_vlm"):
        assert forbidden not in APP_AND_UI


def test_web_package_keeps_parser_and_analysis_engines_without_local_vlm():
    for filename in ("core_log_parser.py", "core_photo_analysis.py"):
        assert (ROOT / filename).exists()
    assert not (ROOT / "core_local_vlm.py").exists()


def test_each_engineering_ui_module_has_a_render_function():
    assert len(UI_FILES) == 5
    for index, path in enumerate(UI_FILES, start=1):
        assert f"def render_module_{index}(" in path.read_text(encoding="utf-8")
