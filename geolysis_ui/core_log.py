"""Web UI for whole-hole core-log parsing and per-row RQD first-pass review."""
from __future__ import annotations

import hashlib
import logging
import traceback
from typing import Any

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw

from core_log_parser import parse_core_log
from core_photo_analysis import (
    analyze_core_row_v8,
    build_core_gap_review_candidates,
    calibrate_row_measurement_span,
    detect_core_break_candidates_v1,
    draw_core_fracture_candidates,
    draw_core_row_analysis_v8,
    estimate_rqd_from_image_segments,
    crop_tray_insets,
    rotate_image,
    detect_blue_tray_quadrilateral,
    draw_tray_quadrilateral,
    rectify_tray_perspective,
)

logger = logging.getLogger(__name__)


def _image_digest(image: Image.Image) -> str:
    rgb = image.convert("RGB")
    digest = hashlib.sha256()
    digest.update(f"{rgb.width}x{rgb.height}:RGB\\0".encode("ascii"))
    digest.update(rgb.tobytes())
    return digest.hexdigest()


def _core_review_fingerprint(image: Image.Image, mm_per_px: float, engine_fingerprint: str) -> str:
    """Invalidate manual fracture/gap reviews when image, scale or engine changes."""
    payload = f"{_image_digest(image)}|{float(mm_per_px):.9g}|{engine_fingerprint}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


@st.cache_data(
    show_spinner=False,
    hash_funcs={Image.Image: _image_digest},
)
def _cached_tray_detection(image, engine_fingerprint: str):
    """Cache blue-tray quadrilateral detection using the same source fingerprint."""
    return detect_blue_tray_quadrilateral(image)


@st.cache_data(
    show_spinner=False,
    hash_funcs={Image.Image: _image_digest},
)
def _cached_row_analysis(image, mm_per_px, engine_fingerprint: str):
    """Cache image analysis by pixels, scale and source fingerprint.

    The fingerprint invalidates Streamlit's cache whenever the analysis engine
    changes, while the image hash prevents two different rows sharing results.
    """
    try:
        core_result = analyze_core_row_v8(image, mm_per_px)
        break_result = detect_core_break_candidates_v1(image, mm_per_px)
        return core_result, break_result
    except Exception:
        break_detection_traceback = traceback.format_exc()
        logger.error("Core-row analysis failed: %s", break_detection_traceback)
        return (
            {
                "success": False,
                "segments": [],
                "gaps": [],
                "uncertain": [],
                "core_segments": [],
                "warning": "本列影像分析失敗；請確認影像方向、托盤背景及比例尺。",
            },
            {
                "success": False,
                "candidates": [],
                "warning": "斷裂候選分析失敗；請人工檢視原始影像。",
                "traceback": break_detection_traceback,
            },
        )


def _rqd_segments_from_analysis(analysis: dict) -> list[dict]:
    """Map the V8 detector's public 'segments' output to the RQD estimator.

    Keep the legacy core_segments fallback for cached/error payloads produced
    by earlier engine versions; successful V8 results use the 'segments' key.
    """
    if not isinstance(analysis, dict):
        return []
    segments = analysis.get("segments")
    if segments is None:
        segments = analysis.get("core_segments", [])
    return list(segments or [])


def _row_label(record: Any) -> str:
    if record.depth_start_m is not None and record.depth_end_m is not None:
        return f"{record.depth_start_m:.1f}–{record.depth_end_m:.1f} m"
    if record.row_number is not None:
        return f"第 {record.row_number} 列"
    return f"第 {record.page} 頁／箱 {record.box_index}／列 {record.row_in_box}"


def _make_page_overlay(page_view: dict, row_items: list[dict]) -> Image.Image:
    page_image = page_view["image"].convert("RGB").copy()
    draw = ImageDraw.Draw(page_image)
    for item in row_items:
        record = item["record"]
        bbox = record.page_bbox_px
        if record.page != page_view.get("page") or not bbox:
            continue
        x0, y0, x1, y1 = [int(v) for v in bbox]
        x0 = max(0, min(page_image.width - 1, x0))
        y0 = max(0, min(page_image.height - 1, y0))
        x1 = max(x0 + 1, min(page_image.width, x1))
        y1 = max(y0 + 1, min(page_image.height, y1))
        overlay = item["overlay"].resize(
            (x1 - x0, y1 - y0), Image.Resampling.LANCZOS
        )
        page_image.paste(overlay, (x0, y0))
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(30, 110, 230), width=3)
    return page_image


def render_core_log_analysis(expanded: bool = False, engine_fingerprint: str = "") -> None:
    """Render the DOCX/PDF whole-hole core-column workflow."""
    with st.expander("岩心柱狀圖解析與 RQD 初估", expanded=expanded):
        st.caption(
            "支援整孔 DOCX／PDF。每列依 1.0 m 初估採取率與 RQD；"
            "先顯示原始頁面疊圖，再逐列覆核疑似斷裂線跡、岩心間隙及不確定位置。"
        )
        uploaded = st.file_uploader(
            "上傳整孔岩心柱狀圖（DOCX／PDF）",
            type=["docx", "pdf"],
            key="core_log_upload",
        )
        if uploaded is None:
            st.info("上傳原始柱狀圖後即可解析；不需要先拆成單列照片。")
            st.session_state.pop("core_log_result", None)
            st.session_state.pop("core_log_file_digest", None)
            return

        file_bytes = uploaded.getvalue()
        file_digest = hashlib.sha256(file_bytes).hexdigest()
        if st.session_state.get("core_log_file_digest") != file_digest:
            st.session_state["core_log_file_digest"] = file_digest
            st.session_state["core_log_result"] = None

        if st.button("解析整孔柱狀圖", key="core_log_parse_button", type="primary"):
            try:
                with st.spinner("正在保留原始頁面並擷取各列岩心影像…"):
                    parsed = parse_core_log(
                        file_bytes,
                        uploaded.name,
                        start_depth_m=None,
                        row_length_m=1.0,
                    )
                st.session_state["core_log_result"] = parsed
            except Exception as exc:
                logger.exception("Core-log parsing failed")
                st.error(f"柱狀圖解析失敗：{exc}")
                return

        parsed = st.session_state.get("core_log_result")
        if not parsed:
            st.caption("解析完成後會在此顯示原始頁面、逐列影像與成果表。")
            return

        records = parsed.get("records", [])
        if not records:
            st.error("檔案中沒有擷取到可辨識的岩心列；請確認 PDF／DOCX 是否包含可擷取的岩心照片。")
            for warning in parsed.get("warnings", []):
                st.warning(warning)
            return

        # PDF 可由頁首可讀深度範圍推定起始深度；DOCX 或掃描頁若無法推定，
        # 才要求使用者輸入一次起始深度，不要求逐列輸入深度。
        if all(record.depth_start_m is None for record in records):
            has_row_numbers = any(record.row_number is not None for record in records)
            if has_row_numbers:
                st.warning("檔案有列號但沒有可讀的深度起點；可輸入一次第一列起始深度，系統依列號推算各列深度。")
            else:
                st.warning("檔案沒有可讀的列號或列尾深度；若確認所有 1 m 列均依序存在，可輸入第一列起始深度，系統暫按檔案列序推算。")
            start_depth = st.number_input(
                "第一列起始深度（m）",
                min_value=0.0,
                max_value=10000.0,
                value=0.0,
                step=1.0,
                key=f"core_log_start_depth_{file_digest[:10]}",
            )
            if st.button("套用起始深度並更新列深度", key="core_log_apply_depth"):
                try:
                    parsed = parse_core_log(
                        file_bytes,
                        uploaded.name,
                        start_depth_m=float(start_depth),
                        row_length_m=1.0,
                    )
                    st.session_state["core_log_result"] = parsed
                    st.rerun()
                except Exception as exc:
                    logger.exception("Applying core-log start depth failed")
                    st.error(f"深度套用失敗：{exc}")
                    return
        if all(record.depth_start_m is None for record in records):
            st.warning("未能從檔案讀取列號；仍可檢視原始影像與逐列初估，但深度索引需依原始編錄人工核對。")

        if parsed.get("borehole_id"):
            st.caption(f"鑽孔編號：{parsed['borehole_id']}")
        valid_starts = [r.depth_start_m for r in records if r.depth_start_m is not None]
        valid_ends = [r.depth_end_m for r in records if r.depth_end_m is not None]
        depth_label = (
            f"深度 {min(valid_starts):.1f}–{max(valid_ends):.1f} m"
            if valid_starts and valid_ends else "深度索引未建立"
        )
        st.caption(
            f"擷取 {len(records)} 列｜每列 1.0 m｜{depth_label}"
            + (f"｜深度來源：{parsed['depth_source']}" if parsed.get("depth_source") else "")
        )
        for warning in parsed.get("warnings", []):
            st.warning(warning)

        # First-pass analysis uses the full extracted row width as the 1 m scale.
        # The per-row review below can calibrate the true 1 m span when tray margins exist.
        row_items = []
        with st.spinner("正在逐列初估岩心本體、空隙與疑似斷裂…"):
            for index, record in enumerate(records):
                row_measurement = record.image
                row_scale = {"mm_per_px": 1000.0 / max(1, row_measurement.width)}
                core_result, break_result = _cached_row_analysis(
                    row_measurement,
                    row_scale["mm_per_px"],
                    engine_fingerprint,
                )
                row_overlay = draw_core_row_analysis_v8(row_measurement, core_result)
                row_overlay = draw_core_fracture_candidates(row_overlay, break_result)
                row_items.append({
                    "index": index,
                    "record": record,
                    "analysis": core_result,
                    "breaks": break_result,
                    "overlay": row_overlay,
                    "mm_per_px": row_scale["mm_per_px"],
                })

        page_views = parsed.get("page_views", [])
        if page_views:
            st.markdown("**原始頁面與偵測疊圖**")
            st.caption("綠色：岩心本體候選；紅色：空隙候選；黃色：不確定區；藍框：逐列範圍。此頁為原始方向初估，逐列校正結果見下方。")
            for page_view in page_views:
                page_overlay = _make_page_overlay(page_view, row_items)
                st.image(
                    page_overlay,
                    caption=f"第 {page_view.get('page')} 頁｜原始頁面直接疊加逐列偵測結果",
                    use_container_width=True,
                )
        else:
            st.markdown("**DOCX 擷取列影像**")
            st.caption("DOCX 以原始內嵌影像擷取；下方逐列顯示原圖與偵測疊圖。")

        st.markdown("**逐列採取率與 RQD 覆核**")
        st.caption(
            "採取率依岩心本體影像區間初估；RQD 只計入人工確認為天然節理分段後，"
            "長度至少 100 mm 的岩心段。機械破損不切斷 RQD 岩心段。"
        )

        final_rows = []
        for item in row_items:
            record = item["record"]
            index = item["index"]
            with st.expander(f"{_row_label(record)}｜第 {index + 1} 列覆核", expanded=False):
                st.image(item["overlay"], caption="本列原始方向初估疊圖", use_container_width=True)
                with st.expander("影像旋轉／托盤邊緣校正", expanded=False):
                    rotation = st.selectbox(
                        "順時針旋轉角度",
                        [0, 180],
                        index=0,
                        key=f"core_rotation_{file_digest[:10]}_{index}",
                    )
                    rotated_row = rotate_image(record.image, rotation)
                    perspective_enabled = st.checkbox(
                        "自動偵測藍色托盤四角（透視校正）",
                        value=False,
                        key=f"core_perspective_{file_digest[:10]}_{index}",
                    )
                    tray_detection = None
                    apply_perspective = False
                    if perspective_enabled:
                        tray_detection = _cached_tray_detection(rotated_row, engine_fingerprint)
                        if tray_detection.get("success"):
                            st.image(
                                draw_tray_quadrilateral(rotated_row, tray_detection),
                                caption="藍色托盤四角候選；請確認四個角都落在同一列托盤外框",
                                use_container_width=True,
                            )
                            apply_perspective = st.checkbox(
                                "確認四角正確，套用透視校正",
                                value=False,
                                key=f"core_perspective_confirm_{file_digest[:10]}_{index}",
                            )
                        else:
                            st.warning(tray_detection.get("warning", "未能可靠偵測托盤外框；保留原圖。"))
                    crop_supported = min(record.image.width, record.image.height) >= 80
                    crop_enabled = st.checkbox(
                        "裁除托盤邊框（不改變原始檔案）",
                        value=False,
                        disabled=not crop_supported,
                        key=f"core_crop_enabled_{file_digest[:10]}_{index}",
                    )
                    if not crop_supported:
                        st.caption("本列影像短邊小於 80 px，暫不提供邊框裁切；可使用 1 m 量測範圍校正。")
                    if crop_enabled:
                        crop_cols = st.columns(4)
                        left_pct = crop_cols[0].slider("左 (%)", 0, 20, 1, key=f"core_crop_l_{file_digest[:10]}_{index}")
                        right_pct = crop_cols[1].slider("右 (%)", 0, 20, 1, key=f"core_crop_r_{file_digest[:10]}_{index}")
                        top_pct = crop_cols[2].slider("上 (%)", 0, 20, 1, key=f"core_crop_t_{file_digest[:10]}_{index}")
                        bottom_pct = crop_cols[3].slider("下 (%)", 0, 20, 1, key=f"core_crop_b_{file_digest[:10]}_{index}")
                    else:
                        left_pct = right_pct = top_pct = bottom_pct = 0

                calibrate = st.checkbox(
                    "校正本列實際 1 m 量測範圍（排除托盤邊框及端部空隙）",
                    value=False,
                    key=f"core_calibrate_{file_digest[:10]}_{index}",
                )
                analysis = item["analysis"]
                break_result = item["breaks"]
                # 180° rotation preserves the horizontal 1 m axis. Cropping only
                # removes frame margins; retain the original row scale unless the
                # user explicitly calibrates a measured 1 m span below.
                row_measurement = rotated_row
                mm_per_px = item["mm_per_px"]
                perspective_applied = False
                if apply_perspective and tray_detection:
                    try:
                        row_measurement, perspective_info = rectify_tray_perspective(
                            row_measurement,
                            tray_detection,
                            max_dimension=max(row_measurement.width, row_measurement.height),
                        )
                        mm_per_px = 1000.0 / max(1, row_measurement.width)
                        perspective_applied = True
                        st.caption(
                            "透視校正已套用；沿列比例尺依每列 1.0 m 名義長度換算。"
                            + perspective_info.get("warning", "")
                        )
                    except Exception as exc:
                        st.warning(f"透視校正未套用：{exc}；改用旋轉後原圖繼續分析。")
                crop_meta = None
                if crop_enabled:
                    try:
                        row_measurement, crop_meta = crop_tray_insets(
                            row_measurement, left_pct, right_pct, top_pct, bottom_pct
                        )
                    except Exception as exc:
                        st.warning(f"托盤邊框裁切未套用：{exc}；保留前一步影像繼續分析。")
                measured_row = row_measurement
                if rotation or crop_enabled or perspective_applied:
                    analysis, break_result = _cached_row_analysis(
                        row_measurement, mm_per_px, engine_fingerprint
                    )
                    corrected_overlay = draw_core_row_analysis_v8(row_measurement, analysis)
                    corrected_overlay = draw_core_fracture_candidates(corrected_overlay, break_result)
                    st.image(corrected_overlay, caption="旋轉／裁切校正後疊圖", use_container_width=True)
                    if crop_meta:
                        st.caption(crop_meta["warning"])
                if calibrate:
                    width = row_measurement.width
                    x_span = st.slider(
                        "1 m 量測範圍（像素起點、終點）",
                        min_value=0,
                        max_value=width,
                        value=(0, width),
                        step=1,
                        key=f"core_span_{file_digest[:10]}_{index}_{_image_digest(row_measurement)[:10]}",
                    )
                    try:
                        measured_row, row_cal = calibrate_row_measurement_span(
                            row_measurement, x_span[0], x_span[1], 1000.0
                        )
                        mm_per_px = row_cal["mm_per_px"]
                        analysis, break_result = _cached_row_analysis(
                            measured_row, row_cal["mm_per_px"], engine_fingerprint
                        )
                        measured_overlay = draw_core_row_analysis_v8(measured_row, analysis)
                        measured_overlay = draw_core_fracture_candidates(measured_overlay, break_result)
                        st.image(measured_overlay, caption="校正後量測影像與偵測疊圖", use_container_width=True)
                        st.caption(row_cal["warning"])
                    except Exception as exc:
                        st.error(f"量測範圍校正失敗：{exc}")
                        final_rows.append({
                            "深度": _row_label(record), "採取率初估 (%)": None,
                            "RQD (%)": None, "疑似斷裂": 0, "覆核": "校正失敗",
                        })
                        continue

                review_fingerprint = _core_review_fingerprint(
                    measured_row, mm_per_px, engine_fingerprint
                )
                candidates = list(break_result.get("candidates", []))
                if break_result.get("success"):
                    candidates.extend(build_core_gap_review_candidates(analysis, mm_per_px))
                reviewed_breaks = []
                if candidates:
                    st.markdown("**疑似斷裂／岩心間隙位置（請逐一確認）**")
                    for candidate_index, candidate in enumerate(candidates):
                        distance = float(candidate.get("distance_mm", 0.0))
                        suggested = candidate.get("suggested_class", "不確定／需人工確認")
                        if candidate.get("candidate_type") == "core_gap":
                            gap_start = float(candidate.get("gap_start_mm", distance))
                            gap_end = float(candidate.get("gap_end_mm", distance))
                            candidate_label = (
                                f"{candidate['candidate_id']}｜岩心間隙 {gap_start:.0f}–{gap_end:.0f} mm"
                                f"｜建議：{suggested}"
                            )
                            review_options = [
                                "待確認", "天然節理", "機械破損",
                                "岩心缺失／採取損失", "非斷裂／誤判",
                            ]
                        else:
                            candidate_label = (
                                f"{candidate['candidate_id']}｜距量測起點 {distance:.0f} mm"
                                f"｜建議：{suggested}"
                            )
                            review_options = ["待確認", "天然節理", "機械破損", "非斷裂／誤判"]
                        review = st.selectbox(
                            candidate_label,
                            review_options,
                            index=0,
                            key=f"core_break_review_{file_digest[:10]}_{index}_{review_fingerprint}_{candidate_index}",
                        )
                        reviewed_breaks.append({**candidate, "review_class": review})
                no_breaks_confirmed = False
                if not break_result.get("candidates") and analysis.get("success") and break_result.get("success"):
                    no_breaks_confirmed = st.checkbox(
                        "已人工檢視所有連續岩心本體區段，確認沒有漏掉需要切分 RQD 的天然節理",
                        value=False,
                        key=f"core_no_breaks_{file_digest[:10]}_{index}_{review_fingerprint}",
                    )

                result = estimate_rqd_from_image_segments(
                    _rqd_segments_from_analysis(analysis),
                    reviewed_breaks,
                    mm_per_px,
                    row_length_mm=1000.0,
                    no_breaks_confirmed=no_breaks_confirmed,
                )
                m1, m2, m3 = st.columns(3)
                recovery = result.get("recovery_percent")
                rqd = result.get("rqd_percent")
                m1.metric("採取率初估", "—" if recovery is None else f"{recovery:.1f}%")
                m2.metric("RQD 初估", "待覆核" if rqd is None else f"{rqd:.1f}%")
                m3.metric("疑似斷裂／間隙候選", str(len(candidates)))
                if result.get("warning"):
                    st.caption(result["warning"])
                uncertain_regions = analysis.get("uncertain", []) if isinstance(analysis, dict) else []
                if uncertain_regions:
                    st.warning(
                        f"本列有 {len(uncertain_regions)} 個黃色不確定區，尚未納入岩心本體長度；"
                        "採取率與 RQD 可能偏低，請依原始影像逐區覆核。"
                    )
                if not analysis.get("success"):
                    st.warning(analysis.get("warning", "本列影像分析未通過品質檢核。"))
                if not break_result.get("success"):
                    st.warning(break_result.get("warning", "斷裂候選分析未通過品質檢核。"))

                final_rows.append({
                    "深度": _row_label(record),
                    "採取率初估 (%)": recovery,
                    "RQD (%)": rqd,
                    "疑似斷裂／間隙": len(candidates),
                    "不確定區": len(uncertain_regions),
                    "覆核": "完成" if result.get("ready") else "待覆核",
                })

        st.markdown("**本孔逐深度成果表**")
        summary = pd.DataFrame(final_rows)
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.caption(
            "以上為影像初估與人工覆核成果；遮擋、岩心旋轉、比例尺、托盤背景及破裂面漏檢都可能影響結果。"
            "正式 RQD 仍須依現場岩心編錄確認；照片不能直接推算完整岩石 UCS。"
        )
