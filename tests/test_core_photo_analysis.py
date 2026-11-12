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


def make_synthetic_core_row(width=1000, height=160, gap_positions=(250, 500, 750)):
    """Four visually distinct core pieces separated by full-height narrow gaps."""
    import numpy as np
    from PIL import Image
    arr = np.full((height, width, 3), (145, 125, 105), dtype=np.uint8)
    # Add deterministic rock-like texture, avoiding random test instability.
    for x in range(width):
        shade = int(12 * ((x // 7) % 2))
        arr[25:height - 25, x, :] = np.clip(arr[25:height - 25, x, :].astype(int) + shade, 0, 255)
    for x in gap_positions:
        arr[15:height - 15, max(0, x - 4):min(width, x + 5), :] = (25, 25, 25)
    return Image.fromarray(arr)


def test_core_discontinuity_candidates_detect_synthetic_gaps():
    from core_photo_analysis import detect_core_discontinuity_candidates
    image = make_synthetic_core_row()
    result = detect_core_discontinuity_candidates(image, mm_per_px=1.0, min_separation_mm=50)
    xs = [item["x_px"] for item in result["candidates"]]
    assert result["success"] is True
    assert len(xs) >= 2
    assert any(abs(x - 250) <= 8 for x in xs)
    assert any(abs(x - 500) <= 8 for x in xs)
    assert "不可直接判定為天然節理" in result["warning"]


def test_core_discontinuity_detector_rejects_invalid_scale():
    import pytest
    from core_photo_analysis import detect_core_discontinuity_candidates
    with pytest.raises(ValueError):
        detect_core_discontinuity_candidates(make_synthetic_core_row(), mm_per_px=0)


def test_confirmed_cut_positions_convert_to_image_spans():
    import pytest
    from core_photo_analysis import segment_lengths_from_confirmed_cuts
    assert segment_lengths_from_confirmed_cuts(1000, 1.0, [250, 500, 750]) == [250.0, 250.0, 250.0, 250.0]
    with pytest.raises(ValueError):
        segment_lengths_from_confirmed_cuts(1000, 1.0, [0, 500])
    with pytest.raises(ValueError):
        segment_lengths_from_confirmed_cuts(1000, 1.0, [500, 500])


def test_row_measurement_span_calibration_excludes_tray_margins():
    import pytest
    from core_photo_analysis import calibrate_row_measurement_span
    image = Image.new("RGB", (1200, 160), (140, 130, 120))
    cropped, info = calibrate_row_measurement_span(image, 100, 1100, 1000)
    assert cropped.size == (1000, 160)
    assert info["span_px"] == 1000
    assert info["mm_per_px"] == 1.0
    with pytest.raises(ValueError):
        calibrate_row_measurement_span(image, 0, 30, 1000)


def test_core_discontinuity_detector_returns_no_candidates_for_uniform_row():
    from core_photo_analysis import detect_core_discontinuity_candidates
    image = Image.new("RGB", (1000, 160), (150, 130, 110))
    result = detect_core_discontinuity_candidates(image, mm_per_px=1.0)
    assert result["success"] is True
    assert result["candidates"] == []


def make_blue_core_row(width=1000, height=160, spans=((40, 260), (300, 520), (570, 820), (850, 960))):
    image = Image.new("RGB", (width, height), (25, 95, 190))
    draw = ImageDraw.Draw(image)
    for a, b in spans:
        draw.rounded_rectangle((a, 28, b, height - 28), radius=30, fill=(125, 112, 96), outline=(75, 68, 60), width=3)
    return image


def test_v7_blue_tray_core_occupancy_segments_and_gaps():
    from core_photo_analysis import segment_core_occupancy, draw_core_occupancy_segments
    image = make_blue_core_row()
    result = segment_core_occupancy(image, mm_per_px=1.0, min_gap_mm=15)
    assert result["success"] is True
    assert len(result["intervals"]) == 4
    assert len(result["gaps"]) >= 3
    assert result["method"] == "blue_tray_nonblue_column_occupancy_v1"
    assert draw_core_occupancy_segments(image, result).size == image.size
    assert "不可直接用於 RQD" in result["warning"]


def test_v7_occupancy_falls_back_for_non_blue_row():
    from core_photo_analysis import segment_core_occupancy
    image = Image.new("RGB", (1000, 160), (130, 110, 90))
    result = segment_core_occupancy(image, mm_per_px=1.0)
    assert result["success"] is False
    assert result["intervals"] == []
    assert "已停用自動分割" in result["warning"]


def test_v7_occupancy_rejects_invalid_parameters():
    import pytest
    from core_photo_analysis import segment_core_occupancy
    with pytest.raises(ValueError):
        segment_core_occupancy(make_blue_core_row(), mm_per_px=0)
    with pytest.raises(ValueError):
        segment_core_occupancy(make_blue_core_row(), mm_per_px=1.0, min_core_occupancy=0.99)


def test_v8_multiband_segmentation_finds_four_core_bodies_and_gaps():
    from core_photo_analysis import analyze_core_row_v8, draw_core_row_analysis_v8
    image = make_blue_core_row(width=1000, height=180,
                               spans=((35, 230), (270, 470), (530, 760), (810, 965)))
    result = analyze_core_row_v8(image, mm_per_px=1.0, min_segment_mm=40, min_gap_mm=12)
    assert result["success"] is True
    assert len(result["segments"]) == 4
    assert len(result["gaps"]) >= 3
    assert all(x["length_mm"] >= 40 for x in result["segments"])
    assert all(x["confidence"] in {"較高", "中", "低"} for x in result["segments"])
    assert draw_core_row_analysis_v8(image, result).size == image.size
    assert "不得計入回收率或 RQD" in result["warning"]


def test_v8_multiband_segmentation_marks_ambiguous_shadow_zone():
    import numpy as np
    from PIL import Image
    from core_photo_analysis import analyze_core_row_v8
    arr = np.zeros((180, 1000, 3), dtype=np.uint8)
    arr[:] = (25, 95, 190)
    # Main rock body in three bands, plus a partial-height non-blue shadow/stain.
    arr[35:145, 60:430] = (125, 112, 96)
    arr[75:105, 470:550] = (95, 85, 75)
    result = analyze_core_row_v8(Image.fromarray(arr), mm_per_px=1.0, min_segment_mm=50)
    assert result["success"] is True
    assert any(x["x_start_px"] <= 470 and x["x_end_px"] >= 550 for x in result["uncertain"])


def test_v8_refuses_non_blue_background_and_invalid_scale():
    import pytest
    from core_photo_analysis import analyze_core_row_v8
    image = Image.new("RGB", (1000, 180), (130, 110, 90))
    result = analyze_core_row_v8(image, mm_per_px=1.0)
    assert result["success"] is False
    assert result["segments"] == []
    with pytest.raises(ValueError):
        analyze_core_row_v8(image, mm_per_px=0)


def test_rotate_image_clockwise_and_preserves_source():
    from core_photo_analysis import rotate_image
    image = Image.new("RGB", (120, 80), (10, 20, 30))
    rotated = rotate_image(image, 90)
    assert rotated.size == (80, 120)
    assert image.size == (120, 80)
    assert rotate_image(image, 180).size == (120, 80)
    assert rotate_image(image, 270).size == (80, 120)


def test_rotate_image_rejects_non_quarter_turn():
    import pytest
    from core_photo_analysis import rotate_image
    with pytest.raises(ValueError):
        rotate_image(Image.new("RGB", (100, 100)), 45)


def test_validate_tray_quadrilateral_orders_and_checks_points():
    import pytest
    from core_photo_analysis import validate_tray_quadrilateral
    points = [[390, 290], [10, 10], [390, 10], [10, 290]]
    ordered = validate_tray_quadrilateral(points, 400, 300)
    assert ordered == [[10.0, 10.0], [390.0, 10.0], [390.0, 290.0], [10.0, 290.0]]
    with pytest.raises(ValueError):
        validate_tray_quadrilateral([[-1, 0], [390, 10], [390, 290], [10, 290]], 400, 300)
    with pytest.raises(ValueError):
        validate_tray_quadrilateral([[10, 10], [20, 10], [20, 20], [10, 20]], 400, 300)


def test_crop_tray_insets_returns_independent_crop_and_metadata():
    import pytest
    from core_photo_analysis import crop_tray_insets
    image = Image.new("RGB", (1000, 400), (90, 100, 110))
    cropped, info = crop_tray_insets(image, 2, 3, 5, 5)
    assert cropped.size == (950, 360)
    assert info["box_px"] == [20, 20, 970, 380]
    assert image.size == (1000, 400)
    with pytest.raises(ValueError):
        crop_tray_insets(image, 30, 0, 0, 0)
    with pytest.raises(ValueError):
        crop_tray_insets(Image.new("RGB", (100, 100)), 20, 20, 20, 20)


def test_custom_four_row_boundaries_allow_nonuniform_tray_rows():
    from core_photo_analysis import calculate_fixed_tray_row_layout, crop_fixed_tray_rows
    image = Image.new("RGB", (1000, 800), (140, 130, 120))
    layout = calculate_fixed_tray_row_layout(
        image, row_boundaries_pct=[23.0, 49.5, 76.0]
    )
    assert layout["row_boundaries_pct"] == [23.0, 49.5, 76.0]
    assert [r["box_px"][1:4:2] for r in layout["rows"]] == [
        [0, 184], [184, 396], [396, 608], [608, 800]
    ]
    assert [im.height for im in crop_fixed_tray_rows(image, layout)] == [184, 212, 212, 192]
    assert all(abs(row["mm_per_px"] - 1.0) < 1e-12 for row in layout["rows"])


def test_custom_four_row_boundaries_reject_order_and_too_short_rows():
    import pytest
    from core_photo_analysis import calculate_fixed_tray_row_layout
    image = Image.new("RGB", (1000, 400), (140, 130, 120))
    with pytest.raises(ValueError, match="遞增"):
        calculate_fixed_tray_row_layout(image, row_boundaries_pct=[30, 25, 75])
    with pytest.raises(ValueError, match="列高不足"):
        calculate_fixed_tray_row_layout(image, row_boundaries_pct=[2, 50, 75])
    with pytest.raises(ValueError, match="必須提供"):
        calculate_fixed_tray_row_layout(image, row_boundaries_pct=[25, 75])


def test_v8_all_blue_row_is_rejected_as_no_visible_core():
    from PIL import Image
    from core_photo_analysis import analyze_core_row_v8

    image = Image.new("RGB", (600, 180), (25, 95, 190))
    result = analyze_core_row_v8(image, mm_per_px=1.0)
    assert result["success"] is False


def test_core_log_row_analysis_is_cached_by_image_scale_and_engine_fingerprint(monkeypatch):
    from geolysis_ui import core_log

    calls = {"core": 0, "breaks": 0}

    def fake_core(image, mm_per_px):
        calls["core"] += 1
        return {"success": True, "segments": [], "gaps": [], "uncertain": [], "core_segments": []}

    def fake_breaks(image, mm_per_px):
        calls["breaks"] += 1
        return {"success": True, "candidates": []}

    monkeypatch.setattr(core_log, "analyze_core_row_v8", fake_core)
    monkeypatch.setattr(core_log, "detect_core_break_candidates_v1", fake_breaks)
    core_log._cached_row_analysis.clear()

    image = Image.new("RGB", (320, 120), (130, 120, 110))
    core_log._cached_row_analysis(image, 1000.0 / 320.0, "cache-test-v1")
    core_log._cached_row_analysis(image.copy(), 1000.0 / 320.0, "cache-test-v1")
    assert calls == {"core": 1, "breaks": 1}

    core_log._cached_row_analysis(image, 0.5, "cache-test-v1")
    assert calls == {"core": 2, "breaks": 2}

    core_log._cached_row_analysis(image, 1000.0 / 320.0, "cache-test-v2")
    assert calls == {"core": 3, "breaks": 3}
    core_log._cached_row_analysis.clear()


def test_core_log_tray_detection_has_single_cache_wrapper():
    from geolysis_ui import core_log

    assert callable(core_log._cached_tray_detection)
    assert hasattr(core_log._cached_tray_detection, "clear")


def test_rqd_handoff_uses_v8_segments_key_and_computes_a_row_result():
    from geolysis_ui.core_log import _rqd_segments_from_analysis
    from core_photo_analysis import estimate_rqd_from_image_segments

    analysis = {
        "success": True,
        "segments": [{"x_start_px": 0, "x_end_px": 400, "length_mm": 1000.0}],
        "gaps": [],
        "uncertain": [],
    }
    segments = _rqd_segments_from_analysis(analysis)
    result = estimate_rqd_from_image_segments(
        segments, [], mm_per_px=2.5, row_length_mm=1000.0,
        no_breaks_confirmed=True,
    )
    assert len(segments) == 1
    assert result["ready"] is True
    assert result["recovery_percent"] == 100.0
    assert result["rqd_percent"] == 100.0


def test_rqd_handoff_keeps_legacy_core_segments_fallback():
    from geolysis_ui.core_log import _rqd_segments_from_analysis

    legacy = {"core_segments": [{"x_start_px": 10, "x_end_px": 30}]}
    assert _rqd_segments_from_analysis(legacy) == legacy["core_segments"]


def test_core_photo_cache_digest_includes_image_dimensions():
    from geolysis_ui.core_log import _image_digest

    pixels = bytes([10, 20, 30] * 4)
    square = Image.frombytes("RGB", (2, 2), pixels)
    strip = Image.frombytes("RGB", (1, 4), pixels)
    assert square.tobytes() == strip.tobytes()
    assert _image_digest(square) != _image_digest(strip)


def test_rqd_natural_break_splits_piece_but_mechanical_break_rejoins():
    from core_photo_analysis import estimate_rqd_from_image_segments

    segments = [{"x_start_px": 0, "x_end_px": 400}]
    natural = estimate_rqd_from_image_segments(
        segments, [{"distance_mm": 950.0, "review_class": "天然節理"}],
        mm_per_px=2.5, row_length_mm=1000.0,
    )
    mechanical = estimate_rqd_from_image_segments(
        segments, [{"distance_mm": 300.0, "review_class": "機械破損"}],
        mm_per_px=2.5, row_length_mm=1000.0,
    )
    assert natural["recovery_percent"] == 100.0
    assert natural["piece_lengths_mm"] == [950.0, 50.0]
    assert natural["rqd_percent"] == 95.0
    assert mechanical["piece_lengths_mm"] == [1000.0]
    assert mechanical["rqd_percent"] == 100.0


def test_rqd_remains_pending_until_every_detected_break_is_reviewed():
    from core_photo_analysis import estimate_rqd_from_image_segments

    result = estimate_rqd_from_image_segments(
        [{"x_start_px": 0, "x_end_px": 400}],
        [{"distance_mm": 300.0, "review_class": "待確認"}],
        mm_per_px=2.5, row_length_mm=1000.0,
    )
    assert result["recovery_percent"] == 100.0
    assert result["rqd_percent"] is None
    assert result["ready"] is False


def test_core_gap_review_candidates_identify_adjacent_segments_and_physical_interval():
    from core_photo_analysis import build_core_gap_review_candidates

    analysis = {
        "success": True,
        "segments": [
            {"x_start_px": 0, "x_end_px": 25},
            {"x_start_px": 30, "x_end_px": 500},
        ],
        "gaps": [{"x_start_px": 25, "x_end_px": 30, "length_mm": 10.0}],
    }
    candidates = build_core_gap_review_candidates(analysis, mm_per_px=2.0)
    assert len(candidates) == 1
    assert candidates[0]["candidate_type"] == "core_gap"
    assert candidates[0]["left_segment_index"] == 0
    assert candidates[0]["right_segment_index"] == 1
    assert candidates[0]["gap_start_mm"] == 50.0
    assert candidates[0]["gap_end_mm"] == 60.0


def test_rqd_merges_mechanical_core_gap_but_not_natural_joint_or_core_loss():
    from core_photo_analysis import estimate_rqd_from_image_segments

    segments = [
        {"x_start_px": 0, "x_end_px": 25},
        {"x_start_px": 30, "x_end_px": 500},
    ]
    gap = {
        "candidate_type": "core_gap",
        "left_segment_index": 0,
        "right_segment_index": 1,
        "gap_start_mm": 50.0,
        "gap_end_mm": 60.0,
        "distance_mm": 55.0,
    }
    mechanical = estimate_rqd_from_image_segments(
        segments, [{**gap, "review_class": "機械破損"}],
        mm_per_px=2.0, row_length_mm=1000.0, no_breaks_confirmed=True,
    )
    natural = estimate_rqd_from_image_segments(
        segments, [{**gap, "review_class": "天然節理"}],
        mm_per_px=2.0, row_length_mm=1000.0, no_breaks_confirmed=True,
    )
    core_loss = estimate_rqd_from_image_segments(
        segments, [{**gap, "review_class": "岩心缺失／採取損失"}],
        mm_per_px=2.0, row_length_mm=1000.0, no_breaks_confirmed=True,
    )
    false_gap = estimate_rqd_from_image_segments(
        segments, [{**gap, "review_class": "非斷裂／誤判"}],
        mm_per_px=2.0, row_length_mm=1000.0, no_breaks_confirmed=True,
    )

    assert mechanical["recovery_percent"] == 99.0
    assert mechanical["piece_lengths_mm"] == [990.0]
    assert mechanical["rqd_percent"] == 99.0
    assert natural["piece_lengths_mm"] == [50.0, 940.0]
    assert natural["rqd_percent"] == 94.0
    assert core_loss["piece_lengths_mm"] == [50.0, 940.0]
    assert core_loss["rqd_percent"] == 94.0
    assert false_gap["recovery_percent"] == 100.0
    assert false_gap["piece_lengths_mm"] == [1000.0]
    assert false_gap["rqd_percent"] == 100.0


def test_rqd_does_not_merge_gap_pair_when_multiple_gap_reviews_conflict():
    from core_photo_analysis import build_core_gap_review_candidates, estimate_rqd_from_image_segments

    analysis = {
        "success": True,
        "segments": [
            {"x_start_px": 0, "x_end_px": 25},
            {"x_start_px": 40, "x_end_px": 500},
        ],
        "gaps": [
            {"x_start_px": 25, "x_end_px": 30, "length_mm": 10.0},
            {"x_start_px": 35, "x_end_px": 40, "length_mm": 10.0},
        ],
    }
    gaps = build_core_gap_review_candidates(analysis, mm_per_px=2.0)
    assert len(gaps) == 2
    reviewed = [
        {**gaps[0], "review_class": "機械破損"},
        {**gaps[1], "review_class": "天然節理"},
    ]
    result = estimate_rqd_from_image_segments(
        analysis["segments"], reviewed, mm_per_px=2.0, row_length_mm=1000.0,
        no_breaks_confirmed=True,
    )
    assert result["piece_lengths_mm"] == [50.0, 920.0]
    assert result["rqd_percent"] == 92.0


def test_core_review_fingerprint_changes_with_pixels_scale_and_engine():
    from geolysis_ui.core_log import _core_review_fingerprint

    image = Image.new("RGB", (40, 20), (20, 30, 40))
    baseline = _core_review_fingerprint(image, 2.5, "engine-a")
    changed_pixels = Image.new("RGB", (40, 20), (20, 30, 41))
    changed_shape = Image.new("RGB", (20, 40), (20, 30, 40))
    assert _core_review_fingerprint(changed_pixels, 2.5, "engine-a") != baseline
    assert _core_review_fingerprint(changed_shape, 2.5, "engine-a") != baseline
    assert _core_review_fingerprint(image, 2.6, "engine-a") != baseline
    assert _core_review_fingerprint(image, 2.5, "engine-b") != baseline


def test_rqd_requires_full_core_review_when_only_gap_candidates_exist():
    from core_photo_analysis import estimate_rqd_from_image_segments

    segments = [
        {"x_start_px": 0, "x_end_px": 25},
        {"x_start_px": 30, "x_end_px": 500},
    ]
    gap = {
        "candidate_type": "core_gap",
        "left_segment_index": 0,
        "right_segment_index": 1,
        "gap_start_mm": 50.0,
        "gap_end_mm": 60.0,
        "distance_mm": 55.0,
        "review_class": "機械破損",
    }
    pending = estimate_rqd_from_image_segments(
        segments, [gap], mm_per_px=2.0, row_length_mm=1000.0,
        no_breaks_confirmed=False,
    )
    reviewed = estimate_rqd_from_image_segments(
        segments, [gap], mm_per_px=2.0, row_length_mm=1000.0,
        no_breaks_confirmed=True,
    )
    assert pending["ready"] is False
    assert pending["rqd_percent"] is None
    assert reviewed["ready"] is True
    assert reviewed["piece_lengths_mm"] == [990.0]


def test_core_measurement_inputs_reject_nan_and_infinity():
    import pytest

    with pytest.raises(ValueError, match="有限"):
        pixel_scale_mm_per_px(float("nan"), 200)
    with pytest.raises(ValueError, match="有限"):
        pixel_scale_mm_per_px(100, float("inf"))
    with pytest.raises(ValueError, match="有限"):
        parse_piece_lengths("100, nan, 200")
    with pytest.raises(ValueError, match="有限"):
        calculate_core_indices(1.0, [float("inf")])


def test_core_indices_reject_recovered_length_exceeding_drilled_interval():
    import pytest

    with pytest.raises(ValueError, match="不可超過鑽進深度"):
        calculate_core_indices(1.0, [600.0, 500.0])


def test_core_indices_reject_rqd_piece_total_exceeding_recovered_length():
    import pytest

    with pytest.raises(ValueError, match="RQD 分段總長度"):
        calculate_core_indices(
            1.0, [300.0, 300.0], rqd_piece_lengths_mm=[350.0, 350.0]
        )


def test_core_indices_reject_nonpositive_rqd_threshold():
    import pytest

    with pytest.raises(ValueError, match="RQD 最小岩心段門檻"):
        calculate_core_indices(1.0, [300.0], rqd_threshold_mm=0.0)
