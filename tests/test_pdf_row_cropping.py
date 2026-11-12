from PIL import Image

from core_log_parser import _crop_box_rows


def test_full_four_row_image_splits_into_four_equal_rows():
    image = Image.new("RGB", (100, 440))
    rows = _crop_box_rows(image, 4)
    assert len(rows) == 4
    assert [row.size for row in rows] == [(100, 110)] * 4


def test_full_box_with_two_visible_labels_uses_top_half_only():
    image = Image.new("RGB", (100, 440))
    rows = _crop_box_rows(image, 2, image_is_pre_cropped=False)
    assert len(rows) == 2
    assert [row.size for row in rows] == [(100, 110)] * 2


def test_already_cropped_two_row_image_is_not_cropped_twice():
    image = Image.new("RGB", (100, 218))
    rows = _crop_box_rows(image, 2, image_is_pre_cropped=True)
    assert len(rows) == 2
    assert [row.size for row in rows] == [(100, 109)] * 2


def test_h25_1b_real_pdf_regression_when_fixture_is_available():
    """Set H25_CORE_PDF to the supplied borehole PDF to run this regression."""
    import os
    from pathlib import Path
    import pytest
    from core_log_parser import parse_pdf_core_log

    fixture = os.environ.get("H25_CORE_PDF")
    if not fixture or not Path(fixture).is_file():
        pytest.skip("Set H25_CORE_PDF to the supplied H25-1B(50m).pdf fixture")

    parsed = parse_pdf_core_log(Path(fixture).read_bytes(), start_depth_m=0.0)
    records = parsed["records"]
    assert parsed["pages_detected"] == 3
    assert [parsed["page_views"][i]["row_count"] for i in range(3)] == [20, 20, 10]
    assert len(records) == 50
    assert [record.row_number for record in records] == list(range(1, 51))
    assert [(record.depth_start_m, record.depth_end_m) for record in records[:2]] == [(0.0, 1.0), (1.0, 2.0)]
    assert records[-2].image.height >= 100
    assert records[-1].image.height >= 100
    assert records[-2].image.tobytes() != records[-1].image.tobytes()
    assert not parsed["warnings"]


def test_pdf_header_depth_inference_uses_first_global_row_number():
    from core_log_parser import _infer_start_depth_from_header

    assert _infer_start_depth_from_header((20.0, 40.0), 21, 1.0) == 0.0
    assert _infer_start_depth_from_header((20.0, 40.0), 1, 1.0) == 20.0
    assert _infer_start_depth_from_header(None, 1, 1.0) is None
