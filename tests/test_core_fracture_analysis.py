from PIL import Image, ImageDraw

from core_photo_analysis import (
    detect_core_break_candidates_v1,
    draw_core_fracture_candidates,
    estimate_rqd_from_image_segments,
)


def _synthetic_core_row(with_break=True):
    image = Image.new("RGB", (800, 100), (30, 100, 180))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 15, 780, 85), radius=28,
                           fill=(160, 155, 145), outline=(80, 75, 70), width=2)
    for x in range(35, 770, 23):
        shade = 125 + (x % 30)
        draw.line((x, 25, x + 5, 75), fill=(shade, shade - 5, shade - 15), width=2)
    if with_break:
        for y in range(18, 84):
            draw.line((400 + (y % 3) - 1, y, 401 + (y % 3) - 1, y),
                      fill=(25, 20, 18), width=2)
    return image


def test_detects_transverse_break_candidate_and_excludes_tray_edges():
    result = detect_core_break_candidates_v1(_synthetic_core_row(), 1.25)
    assert result["success"] is True
    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert abs(candidate["distance_mm"] - 500.0) < 15
    assert candidate["suggested_class"] == "疑似機械破損特徵"
    assert candidate["review_status"] == "待人工確認"
    assert candidate["confidence"] == "低"


def test_no_detected_line_is_not_claimed_as_no_fracture():
    result = detect_core_break_candidates_v1(_synthetic_core_row(False), 1.25)
    assert result["success"] is True
    assert result["candidates"] == []
    assert "不代表沒有斷裂" in result["warning"]


def test_rqd_estimate_waits_for_manual_review_of_every_candidate():
    result = estimate_rqd_from_image_segments(
        [{"x_start_px": 0, "x_end_px": 800}],
        [{"distance_mm": 500, "review_class": "待確認"}],
        1.25,
    )
    assert result["ready"] is False
    assert result["rqd_percent"] is None
    assert result["unresolved_count"] == 1


def test_natural_joint_splits_core_but_mechanical_break_does_not():
    segments = [{"x_start_px": 0, "x_end_px": 800}]
    natural = estimate_rqd_from_image_segments(
        segments, [{"distance_mm": 950, "review_class": "天然節理"}], 1.25
    )
    mechanical = estimate_rqd_from_image_segments(
        segments, [{"distance_mm": 950, "review_class": "機械破損"}], 1.25
    )
    assert natural["ready"] is True
    assert natural["recovery_percent"] == 100.0
    assert natural["rqd_percent"] == 95.0
    assert mechanical["rqd_percent"] == 100.0


def test_slanted_trace_is_only_a_low_confidence_natural_joint_prompt():
    image = Image.new("RGB", (800, 100), (30, 100, 180))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 15, 780, 85), radius=28,
                           fill=(160, 155, 145), outline=(80, 75, 70), width=2)
    draw.line((340, 18, 380, 83), fill=(20, 18, 15), width=4)
    result = detect_core_break_candidates_v1(image, 1.25)
    assert result["success"] is True
    assert result["candidates"]
    assert result["candidates"][0]["suggested_class"] == "疑似天然節理特徵"
    assert result["candidates"][0]["confidence"] == "低"
    overlay = draw_core_fracture_candidates(image, result)
    assert overlay.size == image.size
    assert overlay.tobytes() != image.tobytes()
