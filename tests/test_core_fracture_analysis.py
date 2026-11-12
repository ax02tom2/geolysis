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
        segments, [{"distance_mm": 950, "review_class": "天然節理"}], 1.25,
        row_review_confirmed=True
    )
    mechanical = estimate_rqd_from_image_segments(
        segments, [{"distance_mm": 950, "review_class": "機械破損"}], 1.25,
        row_review_confirmed=True
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


def test_v8_row_analysis_handles_float_occupancy_without_opencv_median_blur():
    """Regression: OpenCV 5 medianBlur rejects the float32 occupancy profile."""
    from core_photo_analysis import analyze_core_row_v8

    image = Image.new("RGB", (1200, 100), (35, 105, 185))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (120, 17, 1080, 83), radius=30,
        fill=(165, 158, 145), outline=(75, 70, 65), width=2,
    )
    result = analyze_core_row_v8(image, mm_per_px=1000.0 / 1170.0)
    assert result["success"] is True
    assert result["segments"]
    assert "medianBlur" not in result.get("warning", "")


def test_v8_analysis_returns_consistent_structure_for_each_depth_row():
    from core_photo_analysis import analyze_core_row_v8

    rows = []
    for core_start, core_end in [(120, 1080), (140, 1060), (160, 1040), (100, 1100)]:
        image = Image.new("RGB", (1200, 100), (35, 105, 185))
        ImageDraw.Draw(image).rounded_rectangle(
            (core_start, 17, core_end, 83), radius=25,
            fill=(165, 158, 145), outline=(75, 70, 65), width=2,
        )
        rows.append(analyze_core_row_v8(image, mm_per_px=1000.0 / 1170.0))
    assert all(item["success"] for item in rows)
    assert all("segments" in item and "gaps" in item and "uncertain" in item for item in rows)


def test_v8_does_not_depend_on_opencv_median_blur(monkeypatch):
    import cv2
    from core_photo_analysis import analyze_core_row_v8

    def reject_median_blur(*args, **kwargs):
        raise cv2.error("simulated OpenCV 5 medianBlur depth assertion")

    monkeypatch.setattr(cv2, "medianBlur", reject_median_blur)
    image = Image.new("RGB", (1200, 100), (35, 105, 185))
    ImageDraw.Draw(image).rounded_rectangle(
        (120, 17, 1080, 83), radius=30,
        fill=(165, 158, 145), outline=(75, 70, 65), width=2,
    )
    result = analyze_core_row_v8(image, mm_per_px=1000.0 / 1170.0)
    assert result["success"] is True
    assert result["segments"]


def test_no_fracture_candidates_do_not_produce_assumed_100_percent_rqd():
    from core_photo_analysis import estimate_rqd_from_image_segments

    result = estimate_rqd_from_image_segments(
        [{"x_start_px": 0, "x_end_px": 800}], [], 1.25,
    )
    assert result["ready"] is False
    assert result["recovery_percent"] == 100.0
    assert result["rqd_percent"] is None
    assert "不代表沒有天然節理" in result["warning"]


def test_fracture_detector_accepts_opencv_hough_n_by_4_shape(monkeypatch):
    import cv2
    import numpy as np
    from core_photo_analysis import detect_core_break_candidates_v1

    # OpenCV build may return N×4 instead of N×1×4.
    monkeypatch.setattr(
        cv2, "HoughLinesP",
        lambda *args, **kwargs: np.array([[400, 18, 402, 83]], dtype=np.int32),
    )
    result = detect_core_break_candidates_v1(_synthetic_core_row(), 1.25)
    assert result["success"] is True
    assert len(result["candidates"]) == 1
    assert abs(result["candidates"][0]["distance_mm"] - 501.2) < 1.0


def test_fracture_detector_accepts_opencv_hough_n_by_1_by_4_shape(monkeypatch):
    import cv2
    import numpy as np
    from core_photo_analysis import detect_core_break_candidates_v1

    monkeypatch.setattr(
        cv2, "HoughLinesP",
        lambda *args, **kwargs: np.array([[[400, 18, 402, 83]]], dtype=np.int32),
    )
    result = detect_core_break_candidates_v1(_synthetic_core_row(), 1.25)
    assert result["success"] is True
    assert len(result["candidates"]) == 1
    assert abs(result["candidates"][0]["distance_mm"] - 501.2) < 1.0


def test_hough_normalizer_accepts_single_line_and_python_lists():
    import numpy as np
    from core_photo_analysis import _normalize_hough_lines

    assert _normalize_hough_lines([10, 20, 30, 40]).shape == (1, 4)
    assert _normalize_hough_lines([[10, 20, 30, 40], [50, 60, 70, 80]]).shape == (2, 4)
    assert _normalize_hough_lines(np.array([[10], [20], [30], [40]])).shape == (1, 4)
    assert _normalize_hough_lines(None).shape == (0, 4)


def test_hough_normalizer_rejects_ambiguous_array_without_index_error():
    import numpy as np
    import pytest
    from core_photo_analysis import _normalize_hough_lines

    with pytest.raises(ValueError, match="shape"):
        _normalize_hough_lines(np.zeros((5, 3), dtype=np.int32))


def test_fracture_detector_accepts_grayscale_and_rgba_pil_images(monkeypatch):
    import cv2
    import numpy as np
    from PIL import Image
    from core_photo_analysis import detect_core_break_candidates_v1

    hough = np.array([[400, 18, 402, 83]], dtype=np.int32)
    monkeypatch.setattr(cv2, "HoughLinesP", lambda *args, **kwargs: hough)
    rgb = _synthetic_core_row()
    # Grayscale inputs are safely normalized but cannot pass the required blue-tray check.
    gray_result = detect_core_break_candidates_v1(rgb.convert("L"), 1.25)
    assert gray_result["success"] is False
    assert "藍色托盤" in gray_result["warning"]

    rgba_result = detect_core_break_candidates_v1(rgb.convert("RGBA"), 1.25)
    assert rgba_result["success"] is True
    assert len(rgba_result["candidates"]) == 1


def test_cache_invalidation_fingerprint_is_passed_to_both_web_ui_call_sites():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    ui_source = root.joinpath("geolysis_ui", "core_log.py").read_text(encoding="utf-8")
    app_source = root.joinpath("app.py").read_text(encoding="utf-8")
    assert "def _cached_row_analysis(image, mm_per_px, engine_fingerprint: str)" in ui_source
    assert ui_source.count("_cached_row_analysis(\n                    row_measurement,\n                    row_scale[\"mm_per_px\"],\n                    engine_fingerprint,\n                )") == 1
    assert ui_source.count("_cached_row_analysis(\n                            measured_row, row_cal[\"mm_per_px\"], engine_fingerprint\n                        )") == 1
    assert "importlib.reload(" not in app_source
    assert "break_detection_traceback" in ui_source


def test_rqd_keeps_recovery_available_while_break_review_is_pending():
    from core_photo_analysis import estimate_rqd_from_image_segments

    result = estimate_rqd_from_image_segments(
        core_segments=[{"x_start_px": 0, "x_end_px": 120}],
        reviewed_breaks=[{"distance_mm": 60, "review_class": "待確認"}],
        mm_per_px=1.0, row_length_mm=1000.0,
    )
    assert result["ready"] is False
    assert result["recovery_percent"] == 12.0
    assert result["rqd_percent"] is None


def test_rqd_can_be_finalized_after_explicit_no_break_confirmation():
    from core_photo_analysis import estimate_rqd_from_image_segments

    result = estimate_rqd_from_image_segments(
        core_segments=[{"x_start_px": 0, "x_end_px": 120}],
        reviewed_breaks=[], mm_per_px=1.0, row_length_mm=1000.0,
        no_breaks_confirmed=True,
    )
    assert result["ready"] is True
    assert result["recovery_percent"] == 12.0
    assert result["rqd_percent"] == 12.0
    assert result["piece_lengths_mm"] == [120.0]


def test_core_loss_gap_review_does_not_rejoin_or_add_missing_length():
    result = estimate_rqd_from_image_segments(
        [
            {"x_start_px": 0, "x_end_px": 400},
            {"x_start_px": 500, "x_end_px": 800},
        ],
        [{
            "candidate_type": "core_gap",
            "left_segment_index": 0,
            "right_segment_index": 1,
            "gap_start_mm": 400.0,
            "gap_end_mm": 500.0,
            "review_class": "岩心缺失／採取損失",
        }],
        1.0,
        row_length_mm=1000.0,
        no_breaks_confirmed=True,
    )
    assert result["ready"] is True
    assert result["recovery_percent"] == 70.0
    assert result["rqd_percent"] == 70.0
    assert result["piece_lengths_mm"] == [400.0, 300.0]


def test_rejected_break_candidate_still_requires_whole_row_review_confirmation():
    segments = [{"x_start_px": 0, "x_end_px": 800}]
    rejected = [{"distance_mm": 500, "review_class": "非斷裂／誤判"}]
    pending = estimate_rqd_from_image_segments(segments, rejected, 1.25)
    assert pending["ready"] is False
    assert pending["recovery_percent"] == 100.0
    assert pending["rqd_percent"] is None

    confirmed = estimate_rqd_from_image_segments(
        segments, rejected, 1.25, row_review_confirmed=True
    )
    assert confirmed["ready"] is True
    assert confirmed["rqd_percent"] == 100.0


def test_natural_joint_candidate_also_requires_review_of_all_continuous_intervals():
    segments = [{"x_start_px": 0, "x_end_px": 800}]
    natural = [{"distance_mm": 500, "review_class": "天然節理"}]
    pending = estimate_rqd_from_image_segments(segments, natural, 1.25)
    assert pending["ready"] is False
    assert pending["rqd_percent"] is None
    confirmed = estimate_rqd_from_image_segments(
        segments, natural, 1.25, row_review_confirmed=True
    )
    assert confirmed["ready"] is True
    assert confirmed["rqd_percent"] == 100.0
