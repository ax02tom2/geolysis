from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_core_modules_import_without_dataclass_reload_path():
    import core_log_parser
    import core_photo_analysis

    assert sys.modules.get("core_log_parser") is core_log_parser
    assert sys.modules.get("core_photo_analysis") is core_photo_analysis
    assert not hasattr(core_log_parser.CoreRowRecord, "__dataclass_fields__")
    assert not hasattr(core_photo_analysis.ImageInfo, "__dataclass_fields__")
    assert "from dataclasses import" not in Path(core_log_parser.__file__).read_text(encoding="utf-8")
    assert "from dataclasses import" not in Path(core_photo_analysis.__file__).read_text(encoding="utf-8")


def test_app_does_not_force_reload_core_module():
    app = Path(__file__).resolve().parents[1] / "app.py"
    source = app.read_text(encoding="utf-8")
    assert "importlib.reload(" not in source
    assert "CORE_ANALYSIS_SOURCE_SHA256" in source
    assert "render_core_log_analysis" in source
