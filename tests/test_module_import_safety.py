from __future__ import annotations

from pathlib import Path


def test_app_does_not_import_removed_core_log_or_image_analysis():
    app = Path(__file__).resolve().parents[1] / "app.py"
    source = app.read_text(encoding="utf-8")
    for removed in ("core_log_parser", "core_photo_analysis", "render_core_log_analysis"):
        assert removed not in source
    assert "importlib.reload(" not in source


def test_all_five_module_renderers_remain_importable():
    from geolysis_ui import (
        render_module_1,
        render_module_2,
        render_module_3,
        render_module_4,
        render_module_5,
    )

    assert all(callable(fn) for fn in (
        render_module_1,
        render_module_2,
        render_module_3,
        render_module_4,
        render_module_5,
    ))
