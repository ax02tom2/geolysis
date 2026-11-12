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


def test_core_log_parser_reads_decimal_and_interval_row_end_depth_labels():
    from core_log_parser import _parse_row_label

    decimal = _parse_row_label("21.0")
    assert decimal == {
        "row_number": None,
        "depth_start_label_m": None,
        "depth_end_label_m": 21.0,
    }
    with_unit = _parse_row_label("22 m")
    assert with_unit["depth_end_label_m"] == 22.0
    interval = _parse_row_label("22.0–23.0m")
    assert interval["depth_start_label_m"] == 22.0
    assert interval["depth_end_label_m"] == 23.0
    integer_row = _parse_row_label("23")
    assert integer_row["row_number"] == 23


def test_core_log_parser_attaches_depths_from_row_end_labels_without_start_input():
    from core_log_parser import CoreRowRecord, _attach_depths, _validate_row_sequence

    records = [
        CoreRowRecord(
            page=1, box_index=1, row_in_box=i + 1, row_number=None,
            depth_start_m=None, depth_end_m=None, width_px=1000, height_px=100,
            image=Image.new("RGB", (1000, 100)), source="test", warnings=[],
            depth_end_label_m=float(i + 1),
        )
        for i in range(3)
    ]
    warnings = []
    _attach_depths(records, start_depth_m=None, row_length_m=1.0)
    _validate_row_sequence(records, warnings)
    assert [(r.depth_start_m, r.depth_end_m) for r in records] == [
        (0.0, 1.0), (1.0, 2.0), (2.0, 3.0)
    ]
    assert warnings == []


def test_pdf_parser_uses_decimal_row_end_depths_without_manual_start_depth():
    from io import BytesIO
    import fitz
    from PIL import Image
    from core_log_parser import parse_pdf_core_log

    page_image = Image.new("RGB", (480, 480), (25, 95, 190))
    image_buffer = BytesIO()
    page_image.save(image_buffer, format="PNG")

    document = fitz.open()
    page = document.new_page(width=600, height=800)
    page.insert_image(fitz.Rect(50, 100, 530, 580), stream=image_buffer.getvalue())
    for index, depth_end in enumerate(("1.0", "2.0", "3.0", "4.0")):
        page.insert_text((540, 160 + index * 120), depth_end, fontsize=10)

    parsed = parse_pdf_core_log(document.tobytes(), start_depth_m=None, row_length_m=1.0)
    records = parsed["records"]
    assert len(records) == 4
    assert [(r.depth_start_m, r.depth_end_m) for r in records] == [
        (0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 4.0)
    ]
    assert parsed["depth_source"] == "PDF 列尾深度標籤"


def test_attach_depths_uses_file_order_only_when_all_labels_are_absent():
    from core_log_parser import CoreRowRecord, _attach_depths

    records = [
        CoreRowRecord(
            page=1, box_index=1, row_in_box=i + 1, row_number=None,
            depth_start_m=None, depth_end_m=None, width_px=1000, height_px=100,
            image=Image.new("RGB", (1000, 100)), source="test", warnings=[],
        )
        for i in range(3)
    ]
    _attach_depths(records, start_depth_m=12.0, row_length_m=1.0)
    assert [(r.depth_start_m, r.depth_end_m) for r in records] == [
        (12.0, 13.0), (13.0, 14.0), (14.0, 15.0)
    ]


def test_attach_depths_does_not_apply_sequence_fallback_to_partially_labelled_rows():
    from core_log_parser import CoreRowRecord, _attach_depths

    records = [
        CoreRowRecord(
            page=1, box_index=1, row_in_box=1, row_number=None,
            depth_start_m=None, depth_end_m=None, width_px=1000, height_px=100,
            image=Image.new("RGB", (1000, 100)), source="test", warnings=[],
            depth_end_label_m=1.0,
        ),
        CoreRowRecord(
            page=1, box_index=1, row_in_box=2, row_number=None,
            depth_start_m=None, depth_end_m=None, width_px=1000, height_px=100,
            image=Image.new("RGB", (1000, 100)), source="test", warnings=[],
        ),
    ]
    _attach_depths(records, start_depth_m=0.0, row_length_m=1.0)
    assert (records[0].depth_start_m, records[0].depth_end_m) == (0.0, 1.0)
    assert records[1].depth_start_m is None
    assert records[1].depth_end_m is None
