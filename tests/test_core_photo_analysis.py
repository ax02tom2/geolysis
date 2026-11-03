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
