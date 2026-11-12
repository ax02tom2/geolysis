from io import BytesIO

import fitz
from PIL import Image, ImageDraw
from docx import Document

from core_log_parser import parse_docx_core_log, parse_pdf_core_log


def _box_image():
    im = Image.new("RGB", (800, 400), "white")
    d = ImageDraw.Draw(im)
    for y in (100, 200, 300):
        d.line((0, y, 800, y), fill="black", width=3)
    b = BytesIO()
    im.save(b, format="JPEG", quality=90)
    return b.getvalue()


def _header_image():
    im = Image.new("RGB", (800, 180), "lightgray")
    b = BytesIO()
    im.save(b, format="JPEG")
    return b.getvalue()


def _docx_fixture():
    doc = Document()
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).merge(table.cell(0, 1)).paragraphs[0].add_run().add_picture(BytesIO(_header_image()), width=__import__('docx').shared.Cm(10))
    table.cell(1, 0).paragraphs[0].add_run().add_picture(BytesIO(_box_image()), width=__import__('docx').shared.Cm(15))
    cell = table.cell(1, 1)
    cell.paragraphs[0].text = "1"
    for n in (2, 3, 4):
        cell.add_paragraph(str(n))
    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def _pdf_fixture():
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(40, 30, 520, 125), stream=_header_image())
    page.insert_image(fitz.Rect(40, 160, 470, 360), stream=_box_image())
    for i, n in enumerate((1, 2, 3, 4)):
        page.insert_text((485, 185 + i * 50), str(n), fontsize=12)
    out = pdf.tobytes()
    pdf.close()
    return out


def test_docx_extracts_four_rows_and_maps_depths():
    result = parse_docx_core_log(_docx_fixture(), start_depth_m=12.0)
    assert result["pages_detected"] == 1
    assert result["rows_detected"] == 4
    assert [r.row_number for r in result["records"]] == [1, 2, 3, 4]
    assert [(r.depth_start_m, r.depth_end_m) for r in result["records"]] == [
        (12.0, 13.0), (13.0, 14.0), (14.0, 15.0), (15.0, 16.0)
    ]
    assert all(r.image.width == 800 for r in result["records"])
    assert all(r.image.height == 100 for r in result["records"])


def test_pdf_extracts_rows_and_labels():
    result = parse_pdf_core_log(_pdf_fixture(), start_depth_m=5.0)
    assert result["rows_detected"] == 4
    assert [r.row_number for r in result["records"]] == [1, 2, 3, 4]
    assert result["records"][0].depth_start_m == 5.0
    assert result["records"][-1].depth_end_m == 9.0


def test_docx_missing_row_labels_does_not_guess_depth():
    data = _docx_fixture()
    # The valid fixture is intentionally labelled; parser must only assign
    # depth when a real sequential row number is present.
    result = parse_docx_core_log(data, start_depth_m=0)
    assert all(r.depth_start_m is not None for r in result["records"])


def test_docx_partial_last_box_keeps_only_visible_rows():
    doc = Document()
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).merge(table.cell(0, 1)).paragraphs[0].add_run().add_picture(BytesIO(_header_image()), width=__import__('docx').shared.Cm(10))
    table.cell(1, 0).paragraphs[0].add_run().add_picture(BytesIO(_box_image()), width=__import__('docx').shared.Cm(15))
    table.cell(1, 1).paragraphs[0].text = "19"
    table.cell(1, 1).add_paragraph("20")
    out = BytesIO()
    doc.save(out)
    result = parse_docx_core_log(out.getvalue(), start_depth_m=0)
    assert len(result["records"]) == 2
    assert [r.row_number for r in result["records"]] == [19, 20]
    assert result["records"][0].depth_start_m == 18.0
    assert result["records"][1].depth_end_m == 20.0
    assert all(r.image.height == 100 for r in result["records"])


def test_pdf_keeps_full_page_preview_and_row_overlay_coordinates():
    result = parse_pdf_core_log(_pdf_fixture(), start_depth_m=5.0)
    assert len(result["page_views"]) == 1
    page = result["page_views"][0]
    assert page["page"] == 1
    assert page["image"].size == (page["width_px"], page["height_px"])
    assert page["image"].width > 595
    assert all(r.page_bbox_px is not None for r in result["records"])
    boxes = [r.page_bbox_px for r in result["records"]]
    assert all(0 <= x0 < x1 <= page["width_px"] and 0 <= y0 < y1 <= page["height_px"]
               for x0, y0, x1, y1 in boxes)
    assert all(boxes[i][1] < boxes[i + 1][1] for i in range(len(boxes) - 1))


def _pdf_fixture_with_missing_middle_label():
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(40, 30, 520, 125), stream=_header_image())
    page.insert_image(fitz.Rect(40, 160, 470, 360), stream=_box_image())
    # Row 2 label is deliberately absent. Rows 3 and 4 must not shift upward.
    for y, n in ((185, 1), (285, 3), (335, 4)):
        page.insert_text((485, y), str(n), fontsize=12)
    out = pdf.tobytes()
    pdf.close()
    return out


def _pdf_fixture_with_cropped_two_row_box():
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(40, 30, 520, 125), stream=_header_image())
    two_rows = Image.new("RGB", (800, 200), "white")
    draw = ImageDraw.Draw(two_rows)
    draw.line((0, 100, 800, 100), fill="black", width=3)
    buf = BytesIO()
    two_rows.save(buf, format="JPEG", quality=90)
    # A complete four-row box on the same page establishes the normal
    # embedded-image height for this cropped two-row final box.
    page.insert_image(fitz.Rect(40, 160, 470, 360), stream=_box_image())
    page.insert_image(fitz.Rect(40, 380, 470, 480), stream=buf.getvalue())
    out = pdf.tobytes()
    pdf.close()
    return out


def test_pdf_missing_middle_label_does_not_drop_or_shift_core_rows():
    result = parse_pdf_core_log(_pdf_fixture_with_missing_middle_label(), start_depth_m=0.0)
    assert result["rows_detected"] == 4
    assert [r.row_number for r in result["records"]] == [1, None, 3, 4]
    assert [r.row_in_box for r in result["records"]] == [1, 2, 3, 4]


def test_pdf_cropped_partial_box_without_labels_infers_visible_rows_from_image_height():
    result = parse_pdf_core_log(_pdf_fixture_with_cropped_two_row_box(), start_depth_m=0.0)
    assert result["rows_detected"] == 6
    assert [r.row_in_box for r in result["records"][-2:]] == [1, 2]
    assert [r.image.height for r in result["records"][-2:]] == [100, 100]
