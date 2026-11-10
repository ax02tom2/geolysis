from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
UI_FILES = sorted((ROOT / "geolysis_ui").glob("module*.py"))
UI_SOURCE = "\n".join(path.read_text(encoding="utf-8") for path in UI_FILES)
APP_AND_UI = APP + "\n" + UI_SOURCE


def test_five_engineering_modules_remain():
    for label in ("模組一：Hoek-Brown", "模組二：土壤分類", "模組三：SPT", "模組四：容許承載力", "模組五：極限承載力"):
        assert label in APP_AND_UI


def test_photo_rqd_and_local_ai_are_not_in_web_app():
    for forbidden in ("岩心照片分析與 RQD", "上傳整孔岩心柱狀圖", "qwen3-vl", "ollama_status", "RQD"):
        assert forbidden not in APP_AND_UI


def test_web_package_has_no_local_image_pipeline_modules():
    for filename in ("core_log_parser.py", "core_photo_analysis.py", "core_local_vlm.py"):
        assert not (ROOT / filename).exists()


def test_each_engineering_ui_module_has_a_render_function():
    assert len(UI_FILES) == 5
    for index, path in enumerate(UI_FILES, start=1):
        assert f"def render_module_{index}(" in path.read_text(encoding="utf-8")
