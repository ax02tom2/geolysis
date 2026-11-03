from PIL import Image, ImageDraw

from core_photo_analysis import (
    calculate_core_indices,
    detect_tray_rows,
    parse_piece_lengths,
    pixel_scale_mm_per_px,
)


def make_synthetic_tray(rows=5, width=900, row_height=150):
    height = rows * row_height
    image = Image.new("RGB", (width, height), (220, 220, 210))
    draw = ImageDraw.Draw(image)
    for i in range(rows):
        y0 = i * row_height + 10
        draw.rectangle((10, y0, width - 10, y0 + row_height - 20), fill=(160, 145, 125), outline=(60, 55, 50), width=4)
        for x in range(25, width - 50, 150):
            draw.rounded_rectangle((x, y0 + 30, x + 120, y0 + 100), radius=28, fill=(90, 95, 92), outline=(35, 35, 35), width=3)
    return image


def test_rqd_and_recovery_calculation():
    result = calculate_core_indices(3.0, [125, 180, 95, 210, 110])
    assert round(result["recovery_percent"], 3) == 24.0
    assert round(result["rqd_percent"], 3) == 20.833
    assert result["qualifying_piece_count"] == 4


def test_length_parser_and_scale():
    assert parse_piece_lengths("125, 180；95\n210") == [125.0, 180.0, 95.0, 210.0]
    assert pixel_scale_mm_per_px(100, 200) == 0.5


def test_row_candidate_detection_on_controlled_fixture():
    result = detect_tray_rows(make_synthetic_tray(rows=5), max_rows=12)
    # The detector should recover the five horizontal bands in this controlled case.
    assert len(result["row_bands"]) == 5
    assert len(result["candidates"]) == 4
    assert result["method"] == "horizontal_gradient_candidate_v1"


def make_blue_tray(rows=5, width=900, row_height=150):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (width, rows * row_height), (205, 198, 180))
    draw = ImageDraw.Draw(image)
    # 藍色箱體外框與橫向隔板；內部岩芯以灰褐色表示。
    draw.rectangle((12, 12, width - 12, rows * row_height - 12), outline=(25, 95, 190), width=18)
    for i in range(1, rows):
        y = i * row_height
        draw.line((15, y, width - 15, y), fill=(25, 95, 190), width=14)
    for i in range(rows):
        y0 = i * row_height + 30
        draw.rounded_rectangle((35, y0, width - 35, y0 + 85), radius=38, fill=(112, 105, 92), outline=(65, 60, 55), width=4)
    return image


def test_blue_tray_hough_candidate_detection():
    from core_photo_analysis import detect_blue_tray_rows
    result = detect_blue_tray_rows(make_blue_tray(rows=5), max_rows=12)
    assert result["method"] == "blue_tray_hough_v1"
    assert len(result["candidates"]) >= 3
    ys = [x["y_px"] for x in result["candidates"]]
    assert ys == sorted(ys)


def test_blue_tray_detector_gracefully_handles_non_blue_image():
    from core_photo_analysis import detect_blue_tray_rows
    image = Image.new("RGB", (800, 500), (180, 160, 130))
    result = detect_blue_tray_rows(image)
    assert result["method"] == "blue_hough_v1"
    assert result["candidates"] == []
    assert "未找到" in result["warning"]


def make_skewed_blue_tray():
    import cv2
    import numpy as np
    from PIL import Image
    canvas = np.full((600, 900, 3), (190, 190, 185), dtype=np.uint8)
    outer = np.array([[150, 70], [760, 115], [700, 520], [105, 455]], dtype=np.int32)
    cv2.fillConvexPoly(canvas, outer, (25, 95, 190))
    inner = np.array([[170, 90], [740, 132], [682, 498], [128, 435]], dtype=np.int32)
    cv2.fillConvexPoly(canvas, inner, (175, 150, 120))
    return Image.fromarray(canvas)


def test_blue_tray_quad_detection_and_perspective_rectification():
    from core_photo_analysis import detect_blue_tray_quadrilateral, rectify_tray_perspective
    image = make_skewed_blue_tray()
    result = detect_blue_tray_quadrilateral(image)
    assert result["success"] is True
    assert len(result["corners"]) == 4
    rectified, info = rectify_tray_perspective(image, result)
    assert rectified.width >= 400
    assert rectified.height >= 250
    assert info["output_width_px"] == rectified.width
    assert "不能因此取得真實 mm/px" in info["warning"]


def test_blue_tray_quad_detector_falls_back_for_non_blue_image():
    from core_photo_analysis import detect_blue_tray_quadrilateral
    image = Image.new("RGB", (800, 500), (160, 145, 125))
    result = detect_blue_tray_quadrilateral(image)
    assert result["success"] is False
    assert "未找到" in result["warning"]


def test_fixed_four_row_layout_uses_one_meter_per_row():
    from core_photo_analysis import (
        calculate_fixed_tray_row_layout,
        crop_fixed_tray_rows,
        draw_fixed_tray_row_layout,
    )
    image = Image.new("RGB", (1200, 480), (150, 140, 125))
    layout = calculate_fixed_tray_row_layout(image)
    assert layout["row_count"] == 4
    assert layout["row_length_mm"] == 1000.0
    assert len(layout["rows"]) == 4
    assert abs(layout["mm_per_px"] - (1000.0 / 1200.0)) < 1e-12
    assert [r["box_px"][1:4:2] for r in layout["rows"]] == [[0, 120], [120, 240], [240, 360], [360, 480]]
    crops = crop_fixed_tray_rows(image, layout)
    assert len(crops) == 4
    assert all(crop.size == (1200, 120) for crop in crops)
    overlay = draw_fixed_tray_row_layout(image, layout)
    assert overlay.size == image.size


def test_fixed_row_layout_rejects_invalid_geometry():
    import pytest
    from core_photo_analysis import calculate_fixed_tray_row_layout
    with pytest.raises(ValueError):
        calculate_fixed_tray_row_layout(Image.new("RGB", (50, 100)))
    with pytest.raises(ValueError):
        calculate_fixed_tray_row_layout(Image.new("RGB", (500, 500)), row_count=0)
    with pytest.raises(ValueError):
        calculate_fixed_tray_row_layout(Image.new("RGB", (500, 500)), row_length_mm=0)
