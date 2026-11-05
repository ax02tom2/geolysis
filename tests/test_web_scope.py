from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_five_engineering_modules_remain():
    for label in ("模組一：Hoek-Brown", "模組二：土壤分類", "模組三：SPT", "模組四：容許承載力", "模組五：極限承載力"):
        assert label in APP


def test_photo_rqd_and_local_ai_are_not_in_web_app():
    for forbidden in ("岩心照片分析與 RQD", "上傳整孔岩心柱狀圖", "qwen3-vl", "ollama_status", "RQD"):
        assert forbidden not in APP


def test_web_package_has_no_local_image_pipeline_modules():
    for filename in ("core_log_parser.py", "core_photo_analysis.py", "core_local_vlm.py"):
        assert not (ROOT / filename).exists()
