import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
import base64
import hashlib
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import streamlit.components.v1 as components

from core_log_parser import parse_core_log
from core_photo_analysis import inspect_image, parse_piece_lengths, calculate_core_indices, detect_tray_rows, draw_row_candidates, detect_blue_tray_rows, draw_combined_row_candidates, detect_blue_tray_quadrilateral, draw_tray_quadrilateral, rectify_tray_perspective, calculate_fixed_tray_row_layout, draw_fixed_tray_row_layout, crop_fixed_tray_rows, detect_core_discontinuity_candidates, draw_core_discontinuity_candidates, segment_lengths_from_confirmed_cuts, calibrate_row_measurement_span, segment_core_occupancy, draw_core_occupancy_segments, analyze_core_row_v8, draw_core_row_analysis_v8, detect_core_break_candidates_v1, draw_core_fracture_candidates, estimate_rqd_from_image_segments, rotate_image, validate_tray_quadrilateral

core_tray_editor = components.declare_component(
    "core_tray_editor", path=str(Path(__file__).parent / "point_editor")
)


# 圖片處理快取：Streamlit 每次 widget 互動都會重跑 app.py，
# 因此將昂貴的解碼、托盤偵測、透視校正與列判識結果快取，避免反覆計算。
@st.cache_data(show_spinner=False, max_entries=2)
def _cached_parse_core_log(raw_bytes: bytes, filename: str):
    # Parse document structure first; depth is applied after metadata review.
    return parse_core_log(raw_bytes, filename, start_depth_m=None, row_length_m=1.0)


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_inspect_image(raw_bytes: bytes):
    return inspect_image(raw_bytes)


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_rotate_image(image, rotation: int):
    return rotate_image(image, rotation)


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_detect_tray_quad(image):
    return detect_blue_tray_quadrilateral(image)


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_editor_image_data(image):
    preview = BytesIO()
    image.save(preview, format="JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(preview.getvalue()).decode("ascii")


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_rectify_tray(image, corners_tuple):
    corners = [list(point) for point in corners_tuple]
    return rectify_tray_perspective(image, {"success": True, "corners": corners})


@st.cache_data(show_spinner=False, max_entries=128)
def _cached_row_analysis(image, mm_per_px):
    result = analyze_core_row_v8(image, mm_per_px)
    fracture_result = detect_core_break_candidates_v1(image, mm_per_px)
    result = dict(result)
    result["break_candidates"] = fracture_result.get("candidates", [])
    result["break_detection_warning"] = fracture_result.get("warning", "")
    overlay = draw_core_row_analysis_v8(image, result) if result.get("success") else image.convert("RGB").copy()
    if fracture_result.get("success") and fracture_result.get("candidates"):
        overlay = draw_core_fracture_candidates(overlay, fracture_result)
    return result, overlay


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_editor_display(image):
    # 顯示用縮圖不影響原始像素座標與後續量測影像。
    preview = image.copy()
    preview.thumbnail((1600, 1600))
    return preview


def _record_key(rec):
    return (rec.page, rec.box_index, rec.row_in_box, rec.row_number)


def _analyze_log_row(rec):
    if rec.row_number is None:
        return {"success": False, "warning": "未讀取到可靠列號，暫不建立判釋結果。",
                "segments": [], "gaps": [], "uncertain": []}
    row_measurement, row_scale = calibrate_row_measurement_span(
        rec.image, 0, rec.image.width, 1000.0
    )
    result, overlay = _cached_row_analysis(row_measurement, row_scale["mm_per_px"])
    result = dict(result)
    result["_overlay"] = overlay
    return result


def _candidate_length(items):
    return round(sum(float(item.get("length_mm", 0)) for item in items), 1)


def _load_review_font(size=18):
    """Prefer a Traditional-Chinese-capable font; never rasterize CJK with DejaVu."""
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/msjhbd.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size), True
            except Exception:
                continue
    # ASCII-only fallback is intentional: Pillow's default font cannot render CJK.
    return ImageFont.load_default(), False


def _compose_full_page_review(page_image, row_records, analyses=None, show_analysis=True):
    """Overlay image-derived candidates on the full PDF page without changing source data."""
    canvas = page_image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    font, has_cjk_font = _load_review_font(18)

    analyses = analyses or {}
    for rec in row_records:
        if not rec.page_bbox_px:
            continue
        x0, y0, x1, y1 = [int(v) for v in rec.page_bbox_px]
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(canvas.width, x1), min(canvas.height, y1)
        if x1 <= x0 or y1 <= y0:
            continue

        result = analyses.get(_record_key(rec), {})
        status = "待人工確認"
        if show_analysis:
            if result.get("success"):
                overlay = result.get("_overlay")
                if overlay is not None:
                    target_size = (x1 - x0, y1 - y0)
                    overlay_resized = overlay.convert("RGB").resize(target_size, Image.Resampling.BILINEAR)
                    original_crop = canvas.crop((x0, y0, x1, y1))
                    canvas.paste(Image.blend(original_crop, overlay_resized, 0.55), (x0, y0))
                if result.get("uncertain"):
                    status = "需確認"
                elif result.get("segments") and result.get("gaps"):
                    status = "岩心與缺失候選"
                elif result.get("gaps"):
                    status = "有缺失候選"
                elif result.get("segments"):
                    status = "有岩心候選"
                else:
                    status = "未辨識到明確候選"
            elif result:
                status = "無法判釋"

        color = {
            "有岩心候選": (20, 145, 65),
            "有缺失候選": (195, 55, 45),
            "岩心與缺失候選": (215, 145, 20),
            "未辨識到明確候選": (215, 145, 20),
            "需確認": (215, 145, 20),
            "無法判釋": (215, 145, 20),
            "待人工確認": (215, 145, 20),
        }.get(status, (215, 145, 20))
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=color, width=3)
        depth_label = (f"{rec.depth_start_m:.1f}-{rec.depth_end_m:.1f}m"
                       if rec.depth_start_m is not None else ("深度待確認" if has_cjk_font else "DEPTH N/A"))
        row_label = f"第{rec.row_number}列" if rec.row_number is not None else f"頁{rec.page}-箱{rec.box_index}-列{rec.row_in_box}"
        label = (f"{row_label} | {depth_label} | {status}" if has_cjk_font
                 else f"ROW {rec.row_number or rec.row_in_box} | {depth_label} | REVIEW")
        text_box = draw.textbbox((0, 0), label, font=font)
        label_w = min(canvas.width - 8, text_box[2] - text_box[0] + 12)
        label_h = text_box[3] - text_box[1] + 10
        label_y = max(0, y0 - label_h)
        draw.rectangle((x0, label_y, min(canvas.width - 1, x0 + label_w), label_y + label_h), fill=color)
        draw.text((x0 + 6, label_y + 4), label, fill=(255, 255, 255), font=font)
    return canvas


def _build_page_result_table(page_rows, analyses):
    rows = []
    for rec in page_rows:
        result = analyses.get(_record_key(rec), {})
        if result.get("success"):
            core_mm = _candidate_length(result.get("segments", []))
            gap_mm = _candidate_length(result.get("gaps", []))
            uncertain_mm = _candidate_length(result.get("uncertain", []))
            if uncertain_mm > 0:
                status = "需人工確認"
            elif core_mm > 0 and gap_mm > 0:
                status = "岩心與缺失候選"
            elif gap_mm > 0:
                status = "有疑似缺失"
            elif core_mm > 0:
                status = "有岩心候選"
            else:
                status = "未辨識到明確候選"
            note = "影像候選，尚未人工確認"
        else:
            core_mm = gap_mm = uncertain_mm = None
            status = "無法判釋" if result else "待確認"
            note = result.get("warning", "缺少可靠列號或分析資料")
        breaks = result.get("break_candidates", [])
        break_summary = "；".join(
            f"{b.get('candidate_id', 'F?')} {b.get('distance_mm', 0):.0f}mm：{b.get('suggested_class', '待確認')}"
            for b in breaks
        ) or "未找到明確候選（不代表沒有斷裂）"
        rows.append({
            "列號": rec.row_number if rec.row_number is not None else "未辨識",
            "深度區間 (m)": (f"{rec.depth_start_m:.1f}–{rec.depth_end_m:.1f}"
                             if rec.depth_start_m is not None else "待確認"),
            "岩心影像候選長度 (mm)": core_mm,
            "疑似缺失長度 (mm)": gap_mm,
            "不確定區長度 (mm)": uncertain_mm,
            "疑似斷裂數": len(breaks),
            "斷裂位置與系統提示": break_summary,
            "系統初步結果": status,
            "說明": note,
        })
    return pd.DataFrame(rows)


def _build_break_review_table(page_rows, analyses):
    rows = []
    for rec in page_rows:
        result = analyses.get(_record_key(rec), {})
        for candidate in result.get("break_candidates", []):
            rows.append({
                "列號": rec.row_number if rec.row_number is not None else "未辨識",
                "深度區間 (m)": (f"{rec.depth_start_m:.1f}–{rec.depth_end_m:.1f}"
                                 if rec.depth_start_m is not None else "待確認"),
                "候選編號": candidate.get("candidate_id", "F?"),
                "距本列起點 (mm)": float(candidate.get("distance_mm", 0)),
                "系統影像提示": candidate.get("suggested_class", "不確定／需人工確認"),
                "信心": candidate.get("confidence", "低"),
                "人工覆核分類": "待確認",
            })
    return pd.DataFrame(rows, columns=[
        "列號", "深度區間 (m)", "候選編號", "距本列起點 (mm)",
        "系統影像提示", "信心", "人工覆核分類",
    ])


def _build_image_rqd_review_table(page_rows, analyses, reviewed_break_df):
    rows = []
    reviewed_by_row = {}
    if reviewed_break_df is not None and not reviewed_break_df.empty:
        for _, item in reviewed_break_df.iterrows():
            reviewed_by_row.setdefault(item.get("列號"), []).append({
                "distance_mm": float(item.get("距本列起點 (mm)", 0)),
                "review_class": item.get("人工覆核分類", "待確認"),
            })
    for rec in page_rows:
        result = analyses.get(_record_key(rec), {})
        if not result.get("success"):
            estimate = {"ready": False, "recovery_percent": None, "rqd_percent": None,
                        "warning": result.get("warning", "影像判識失敗")}
        else:
            row_id = rec.row_number if rec.row_number is not None else "未辨識"
            estimate = estimate_rqd_from_image_segments(
                result.get("segments", []), reviewed_by_row.get(row_id, []),
                float(result.get("mm_per_px", 1.0)), row_length_mm=1000.0,
            )
        rows.append({
            "列號": rec.row_number if rec.row_number is not None else "未辨識",
            "深度區間 (m)": (f"{rec.depth_start_m:.1f}–{rec.depth_end_m:.1f}"
                             if rec.depth_start_m is not None else "待確認"),
            "影像初估採取率 (%)": estimate.get("recovery_percent"),
            "影像初估 RQD (%)": estimate.get("rqd_percent"),
            "判釋狀態": (
                ("候選已覆核；初估值待確認" if result.get("break_candidates") else "未檢出斷裂；需目視核對")
                if estimate.get("ready") else "待覆核／無法估算"
            ),
            "說明": estimate.get("warning", ""),
        })
    return pd.DataFrame(rows)


def _build_depth_metrics_table(page_rows, analyses, edited_rows):
    """Build per-metre preliminary image estimates and user-confirmed indices."""
    output = []
    for idx, rec in enumerate(page_rows):
        result = analyses.get(_record_key(rec), {})
        image_core_mm = _candidate_length(result.get("segments", [])) if result.get("success") else None
        image_recovery = round(image_core_mm / 10.0, 1) if image_core_mm is not None else None
        edit = edited_rows.iloc[idx] if idx < len(edited_rows) else {}
        recovered = edit.get("實際回收長度 (mm)") if hasattr(edit, "get") else None
        pieces_raw = edit.get("天然節理分段長度 (mm；逗號分隔)", "") if hasattr(edit, "get") else ""
        confirmed_recovery = None
        confirmed_rqd = None
        rqd_note = "待確認天然節理分段"
        validation_note = ""
        try:
            recovered_mm = None
            if recovered is not None and pd.notna(recovered) and float(recovered) > 0:
                recovered_mm = float(recovered)
                confirmed_recovery = round(recovered_mm / 10.0, 1)
                if recovered_mm > 1000.0:
                    validation_note = "回收長度超過 1,000 mm，請核對"
            if isinstance(pieces_raw, str) and pieces_raw.strip():
                piece_values = parse_piece_lengths(pieces_raw)
                qualifying_mm = sum(v for v in piece_values if v >= 100.0)
                confirmed_rqd = round(qualifying_mm / 10.0, 1)
                rqd_note = "已依輸入天然節理段長計算"
                if qualifying_mm > 1000.0:
                    validation_note = "RQD 計入長度超過鑽進長度，請核對"
                elif recovered_mm is not None and qualifying_mm > recovered_mm:
                    validation_note = "RQD 計入長度大於回收長度，請核對"
        except (ValueError, TypeError):
            rqd_note = "段長格式需檢查"
            validation_note = "請檢查輸入是否為正數，並以逗號分隔"
        output.append({
            "深度區間 (m)": (f"{rec.depth_start_m:.1f}–{rec.depth_end_m:.1f}"
                             if rec.depth_start_m is not None else "待確認"),
            "影像估計岩心長度 (mm)": image_core_mm,
            "影像初估採取率 (%)": image_recovery,
            "人工確認採取率 (%)": confirmed_recovery,
            "人工確認 RQD (%)": confirmed_rqd,
            "RQD 狀態": rqd_note,
            "資料檢核": validation_note,
        })
    return pd.DataFrame(output)


st.set_page_config(page_title="geolysis 大地工程分析系統", page_icon="🧱", layout="wide")

st.title("🧱 geolysis 大地工程分析系統")
st.markdown(r"""
本系統結合 **Hoek-Brown (2002) 岩體裂隙參數推估** 與開源套件 **[geolysis](https://github.com/patrickboateng/geolysis)** 核心工程模組：
- **模組一：Hoek-Brown 岩體裂隙推估 ($c', \phi'$)** — 依據地質強度指標 (GSI，內建現場結構×節理交叉查表)、岩性常數 ($m_i$)、單壓強度與邊坡深度，自動轉換等效莫耳－庫倫參數
- **模組二：土壤分類系統** — USCS 統一土壤分類法 & AASHTO 公路土壤分類法（含群指數 $GI$ 與雙重符號判定）
- **模組三：SPT 標準貫入試驗全修正** — 器材四項修正 ($E_m, C_B, C_S, C_R$)、7 大學者覆土壓力修正 ($C_N$) 與全鑽孔剖面批次繪圖
- **模組四：容許承載力與沉陷控制** — Bowles & Meyerhof 控制沉陷量之淺基礎與筏基設計
- **模組五：極限承載力四大理論** — Terzaghi / Meyerhof / Hansen / Vesic 全套修正係數與三階段地下水折減
""")

# ==============================================================================
# 側邊欄：快速檢視模式
# ==============================================================================
st.sidebar.title("🛠️ 畫面顯示設定")
display_mode = st.sidebar.radio(
    "選擇展開模式：",
    [
        "全部展開",
        "模組一：Hoek-Brown 岩體參數",
        "模組二：土壤分類",
        "模組三：SPT 全修正",
        "模組四：容許承載力",
        "模組五：極限承載力"
    ]
)

exp_1 = display_mode in ["全部展開", "模組一：Hoek-Brown 岩體參數"]
exp_2 = display_mode in ["全部展開", "模組二：土壤分類"]
exp_3 = display_mode in ["全部展開", "模組三：SPT 全修正"]
exp_4 = display_mode in ["全部展開", "模組四：容許承載力"]
exp_5 = display_mode in ["全部展開", "模組五：極限承載力"]


# ==============================================================================
# 模組一：Hoek-Brown (2002) 岩體裂隙推估等效 c', phi' (含 GSI 視覺化查表)
# ==============================================================================
with st.expander("⛰️ 模組一：Hoek–Brown 岩體參數分析", expanded=exp_1):
    st.subheader("Hoek–Brown 岩體強度參數")


    # --- 岩芯照片分析：固定 4 m／箱、每列 1 m ---
    with st.expander("📷 岩心照片分析與 RQD", expanded=False):
        st.caption("標準岩心箱固定 4,000 mm、4 列，每列 1,000 mm。系統完成照片校正後自動分列，不需另設列數、列長或比例尺。")

        core_borehole = ""
        depth_start = None
        depth_end = None

        st.markdown("**整孔柱狀圖匯入（主要方式）**")
        st.caption("優先以完整 PDF 頁面呈現原始資料，判釋標記直接疊在原頁面上；原始文件不會被修改。")
        core_log_file = st.file_uploader(
            "上傳整孔岩心柱狀圖（DOCX／PDF）",
            type=["docx", "pdf"],
            accept_multiple_files=False,
            key="core_log_upload",
            help="支援 Core-photo-depth-matching-alignment 工具輸出的 Word／PDF 格式。PDF 可完整呈現原頁面並疊加判釋標記。",
        )
        if core_log_file is not None:
            try:
                parsed_log = _cached_parse_core_log(core_log_file.getvalue(), core_log_file.name)
                row_records = parsed_log["records"]
                detected_borehole = parsed_log.get("borehole_id") or ""
                detected_range = parsed_log.get("header_depth_range_m")
                st.markdown("**文件資料確認**")
                core_borehole = st.text_input(
                    "鑽孔編號", value=detected_borehole,
                    key=f"core_borehole_id_{hashlib.md5(core_log_file.name.encode()).hexdigest()[:8]}",
                    help="若文件頁首可讀取，會自動帶入；否則可留白或補填。",
                )
                if detected_range:
                    depth_start = float(detected_range[0])
                    st.caption(f"已從 PDF 可選取文字讀取頁首深度範圍：{detected_range[0]:g}–{detected_range[1]:g} m。請核對頁面內容。")
                else:
                    depth_start = st.number_input(
                        "起始深度（m；文件無法自動辨識時才需填寫）",
                        min_value=0.0, value=0.0, step=0.5,
                        key=f"core_depth_start_{hashlib.md5(core_log_file.name.encode()).hexdigest()[:8]}",
                    )
                for rec in row_records:
                    if rec.row_number is not None and depth_start is not None:
                        rec.depth_start_m = float(depth_start) + (rec.row_number - 1)
                        rec.depth_end_m = rec.depth_start_m + 1.0
                depth_values = [r.depth_end_m for r in row_records if r.depth_end_m is not None]
                depth_end = max(depth_values) if depth_values else None
                if depth_end is not None and depth_start is not None:
                    st.caption(f"整孔索引深度：{depth_start:g}–{depth_end:g} m（結束深度由列號自動計算，不需另外輸入）。")
                st.success(f"已讀取 {parsed_log['pages_detected']} 頁，建立 {len(row_records)} 列索引。")

                if parsed_log.get("format") == "pdf" and parsed_log.get("page_views"):
                    page_views = parsed_log["page_views"]
                    page_numbers = [v["page"] for v in page_views]
                    selected_page = st.selectbox(
                        "檢視原始頁面", page_numbers,
                        format_func=lambda p: f"第 {p} 頁／共 {len(page_numbers)} 頁",
                        key="core_log_active_page",
                    )
                    page_view = next(v for v in page_views if v["page"] == selected_page)
                    page_rows = [r for r in row_records if r.page == selected_page]
                    analyses = {}
                    for rec in page_rows:
                        try:
                            analyses[_record_key(rec)] = _analyze_log_row(rec)
                        except Exception as row_exc:
                            analyses[_record_key(rec)] = {"success": False, "warning": f"分析失敗：{row_exc}",
                                                          "segments": [], "gaps": [], "uncertain": []}
                    page_display_mode = st.radio(
                        "頁面顯示", ["判釋疊圖", "原始頁面"], horizontal=True,
                        key=f"core_log_display_mode_{selected_page}",
                    )
                    review_image = _compose_full_page_review(
                        page_view["image"], page_rows, analyses,
                        show_analysis=(page_display_mode == "判釋疊圖"),
                    )
                    st.image(
                        review_image,
                        caption=f"第 {selected_page} 頁完整頁面預覽｜{page_view['width_px']} × {page_view['height_px']} px（2.5× PDF 頁面渲染）",
                        width="stretch",
                    )
                    st.caption("區塊顏色：綠色＝可能有岩心；紅色＝可能缺失；黃色＝看不清楚。斷裂線標記：紅線＝斜向線跡提示、橘線＝較直且近垂直線跡提示、黃線＝特徵不足；F1、F2 為候選編號。這些顏色及幾何提示都不是天然節理／機械破損的正式判定。")
                    st.markdown("**本頁逐深度成果表**")
                    st.dataframe(
                        _build_page_result_table(page_rows, analyses),
                        hide_index=True, width="stretch",
                        column_config={
                            "岩心影像候選長度 (mm)": st.column_config.NumberColumn(format="%.1f"),
                            "疑似缺失長度 (mm)": st.column_config.NumberColumn(format="%.1f"),
                            "不確定區長度 (mm)": st.column_config.NumberColumn(format="%.1f"),
                        },
                    )
                    st.caption("以上是系統對每一公尺影像的初步辨識。斷裂線只代表疑似位置；斜向或較直的外觀不是天然／機械破損的可靠證明。")
                    st.markdown("**疑似斷裂位置覆核**")
                    break_review_df = _build_break_review_table(page_rows, analyses)
                    if not break_review_df.empty:
                        st.caption("請逐一確認系統找到的斷裂候選。天然節理會切分岩心段；機械破損若可接合，不切分 RQD；誤判可標記為非斷裂。")
                        break_review_key = f"core_break_review_{hashlib.md5(core_log_file.name.encode()).hexdigest()[:8]}_{selected_page}"
                        reviewed_break_df = st.data_editor(
                            break_review_df, key=break_review_key, hide_index=True,
                            width="stretch", num_rows="fixed",
                            disabled=["列號", "深度區間 (m)", "候選編號", "距本列起點 (mm)", "系統影像提示", "信心"],
                            column_config={
                                "距本列起點 (mm)": st.column_config.NumberColumn(format="%.1f"),
                                "人工覆核分類": st.column_config.SelectboxColumn(
                                    "人工覆核分類",
                                    options=["待確認", "天然節理", "機械破損", "非斷裂／誤判"],
                                    required=True,
                                    help="這是人工確認欄位。只有確認為天然節理的候選才會切分影像估算 RQD。",
                                ),
                            },
                        )
                    else:
                        reviewed_break_df = break_review_df
                        st.info("本頁未找到明確的橫向斷裂線候選；這不代表岩心沒有天然節理，仍需目視檢查原始照片。")
                    st.markdown("**每 1 m 影像初估採取率與 RQD**")
                    st.dataframe(
                        _build_image_rqd_review_table(page_rows, analyses, reviewed_break_df),
                        hide_index=True, width="stretch",
                    )
                    st.caption("這是依影像岩心區間與人工覆核斷裂分類計算的初估值，可能漏掉不明顯節理或受遮擋影響；不得取代實際岩心量測及正式 RQD。")
                    st.markdown("**逐深度確認採取率與 RQD**")
                    edit_rows = []
                    for rec in page_rows:
                        edit_rows.append({
                            "深度區間 (m)": (f"{rec.depth_start_m:.1f}–{rec.depth_end_m:.1f}"
                                             if rec.depth_start_m is not None else "待確認"),
                            "實際回收長度 (mm)": None,
                            "天然節理分段長度 (mm；逗號分隔)": "",
                        })
                    edit_df = pd.DataFrame(edit_rows)
                    edit_key = f"core_depth_metrics_{hashlib.md5(core_log_file.name.encode()).hexdigest()[:8]}_{selected_page}"
                    edited_df = st.data_editor(
                        edit_df, key=edit_key, hide_index=True, width="stretch",
                        num_rows="fixed",
                        disabled=["深度區間 (m)"],
                        column_config={
                            "實際回收長度 (mm)": st.column_config.NumberColumn(
                                "實際回收長度 (mm)", min_value=0.0, max_value=1000.0, step=1.0,
                                help="填入該 1 m 深度內實際取回的全部岩心長度；機械破損但可接合者仍計入。",
                            ),
                            "天然節理分段長度 (mm；逗號分隔)": st.column_config.TextColumn(
                                "天然節理分段長度 (mm；逗號分隔)",
                                help="填入天然節理界定的每段長度，例如 125, 180, 95。可接合的機械破損先接合。",
                            ),
                        },
                    )
                    metrics_df = _build_depth_metrics_table(page_rows, analyses, edited_df)
                    st.markdown("**每一深度的計算結果**")
                    st.dataframe(metrics_df, hide_index=True, width="stretch")
                    st.caption("影像初估採取率＝影像中的岩心外觀候選長度 ÷ 1,000 mm；人工確認採取率與 RQD 只在填入該深度的實際量測資料後顯示。RQD 只加總 ≥100 mm 的天然節理分段。")
                else:
                    st.warning("DOCX 已擷取照片與列號，但目前尚未能忠實重建 Word 實際分頁。建議使用同一份文件匯出的 PDF，以檢視完整原頁與判釋疊圖。")
                    row_labels = [
                        (f"第 {r.row_number} 列｜{r.depth_start_m:.1f}–{r.depth_end_m:.1f} m"
                         if r.row_number is not None and r.depth_start_m is not None
                         else f"頁 {r.page}／箱 {r.box_index}／第 {r.row_in_box} 列｜深度待確認")
                        for r in row_records
                    ]
                    selected_log_row = st.selectbox(
                        "檢視單列岩心影像", list(range(len(row_records))),
                        format_func=lambda i: row_labels[i], key="core_log_active_row",
                    )
                    st.image(row_records[selected_log_row].image, width="stretch")

                with st.expander("匯入索引與解析警告", expanded=False):
                    import json as _json
                    index_payload = {
                        "borehole_id": core_borehole or None,
                        "start_depth_m": float(depth_start) if depth_start is not None else None,
                        "end_depth_m": float(depth_end) if depth_end is not None else None,
                        "depth_source": "PDF 頁首可選取文字" if parsed_log.get("header_depth_range_m") else "使用者補填起始深度",
                        "row_length_m": 1.0,
                        "rows_per_box": 4,
                        "pages_detected": parsed_log["pages_detected"],
                        "rows_detected": len(row_records),
                        "rows": [rec.metadata() for rec in row_records],
                        "warnings": parsed_log["warnings"],
                        "note": "Embedded row images are extracted at their original embedded pixel dimensions without additional JPEG recompression. Full-page preview is rendered separately at 2.5x. Candidate lengths are image heuristics, not measured core recovery or RQD.",
                    }
                    st.download_button(
                        "下載岩心列深度索引（JSON）",
                        data=_json.dumps(index_payload, ensure_ascii=False, indent=2),
                        file_name="core_log_depth_index.json", mime="application/json",
                        key="download_core_log_index",
                    )
                    for warning in parsed_log["warnings"]:
                        st.warning(warning)
                for warning in parsed_log.get("metadata_warnings", []):
                    st.warning(warning)
                st.caption("系統目前只提供影像初判。天然節理、機械破損及實際岩心段長仍須人工確認，確認後才能計算正式採取率與 RQD。")
            except Exception as log_exc:
                st.error(f"柱狀圖解析失敗：{log_exc}")

        st.divider()
        st.markdown("**原始岩心箱照片（備用方式）**")
        core_photos = st.file_uploader(
            "上傳單張或多張原始岩心箱照片",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="core_photo_upload",
        )

        if core_photos:
            photo_labels = [f"{i + 1}. {photo.name}" for i, photo in enumerate(core_photos)]
            selected_photo_index = st.selectbox(
                "選擇要處理的照片", options=list(range(len(core_photos))),
                format_func=lambda i: photo_labels[i], key="core_active_photo_index",
            )
            uploaded = core_photos[selected_photo_index]
            try:
                raw_bytes = uploaded.getvalue()
                image, info = _cached_inspect_image(raw_bytes)
                photo_token = hashlib.sha1(raw_bytes).hexdigest()[:12]
                rotate_key = f"core_rotate_{photo_token}"
                rotation = st.selectbox(
                    "照片方向", [0, 90, 180, 270], index=0,
                    format_func=lambda x: f"旋轉 {x}°" if x else "原始方向",
                    key=rotate_key,
                )
                working_image = _cached_rotate_image(image, rotation)

                config_key = f"core_quad_{photo_token}_{rotation}"
                rectified_key = f"core_rectified_{photo_token}_{rotation}"
                if config_key not in st.session_state:
                    detected = _cached_detect_tray_quad(working_image)
                    if detected.get("success"):
                        initial_corners = detected["corners"]
                        st.session_state[f"{config_key}_source"] = "自動偵測"
                    else:
                        mx, my = working_image.width * 0.04, working_image.height * 0.04
                        initial_corners = [
                            [mx, my], [working_image.width - mx, my],
                            [working_image.width - mx, working_image.height - my],
                            [mx, working_image.height - my],
                        ]
                        st.session_state[f"{config_key}_source"] = "初始框，請人工修正"
                    st.session_state[config_key] = initial_corners
                    st.session_state[f"{config_key}_initial"] = [point[:] for point in initial_corners]
                    st.session_state[rectified_key] = False

                with st.expander("照片四角校正（需要時再展開調整）", expanded=not st.session_state.get(rectified_key, False)):
                    editor_col, _ = st.columns([3, 1])
                    with editor_col:
                        st.caption("拖曳四個角點，讓框線貼齊整個岩心箱外緣。")
                        editor_value = core_tray_editor(
                            image_data=_cached_editor_image_data(working_image),
                            corners=st.session_state[config_key],
                            initial_corners=st.session_state.get(f"{config_key}_initial", st.session_state[config_key]),
                            key=f"core_editor_{photo_token}_{rotation}", default=None,
                        )
                        if isinstance(editor_value, dict) and editor_value.get("applied"):
                            try:
                                checked = validate_tray_quadrilateral(
                                    editor_value.get("corners"), working_image.width, working_image.height
                                )
                                if checked != st.session_state[config_key]:
                                    st.session_state[config_key] = checked
                                    st.session_state[rectified_key] = False
                                    st.success("照片四角已更新。")
                            except Exception as corner_exc:
                                st.error(f"四角設定無效：{corner_exc}")

                        if st.button("確認四角並校正照片", key=f"core_rectify_btn_{photo_token}_{rotation}", type="primary"):
                            st.session_state[rectified_key] = True

                if st.session_state.get(rectified_key, False):
                    try:
                        corners = validate_tray_quadrilateral(
                            st.session_state[config_key], working_image.width, working_image.height
                        )
                        rectified, _ = _cached_rectify_tray(
                            working_image, tuple(tuple(float(v) for v in point) for point in corners)
                        )
                        layout = calculate_fixed_tray_row_layout(
                            rectified, row_count=4, row_length_mm=1000.0
                        )
                        row_crops = crop_fixed_tray_rows(rectified, layout)

                        st.success("照片校正完成：已依固定規格分成 4 列，每列 1 m。")
                        row_index = st.selectbox(
                            "選擇岩心列", options=[0, 1, 2, 3],
                            format_func=lambda i: f"第 {i + 1} 列（1,000 mm）",
                            key=f"core_active_row_{photo_token}_{rotation}",
                        )
                        row_crop = row_crops[row_index]
                        measured_row, row_cal = calibrate_row_measurement_span(
                            row_crop, 0, row_crop.width, 1000.0
                        )
                        result, analysis_overlay = _cached_row_analysis(measured_row, row_cal["mm_per_px"])

                        preview_col, _ = st.columns([3, 1])
                        with preview_col:
                            if result.get("success"):
                                st.image(
                                    _cached_editor_display(analysis_overlay),
                                    caption=f"第 {row_index + 1} 列判識結果｜綠色：岩心候選；紅色：空隙候選；黃色：不確定區",
                                    width="stretch",
                                )
                                result_cols = st.columns(3)
                                result_cols[0].metric("岩心候選", len(result["segments"]))
                                result_cols[1].metric("空隙候選", len(result["gaps"]))
                                result_cols[2].metric("不確定區", len(result["uncertain"]))
                                with st.expander("查看候選長度", expanded=False):
                                    st.write({
                                        "岩心候選長度（mm）": [round(x["length_mm"], 1) for x in result["segments"]],
                                        "疑似空隙長度（mm）": [round(x["length_mm"], 1) for x in result["gaps"]],
                                        "不確定區長度（mm）": [round(x["length_mm"], 1) for x in result["uncertain"]],
                                    })
                                st.caption("影像判識僅提供候選區段；天然節理與機械破損仍須人工確認，不能直接視為 RQD。")
                            else:
                                st.info(result.get("warning", "目前照片無法判識，請調整四角或照片方向。"))

                    except Exception as rect_exc:
                        st.error(f"照片校正或分列失敗：{rect_exc}")
            except Exception as exc:
                st.error(f"{uploaded.name}：圖片讀取失敗（{exc}）")

        if core_log_file is None:
            st.divider()
            st.markdown("**原始照片模式：人工計算採取率與 RQD**")
            st.caption("此模式沒有整孔列深度索引，請自行指定計算深度；採取率與 RQD 分開計算。機械破損若可接合，應先接合，不可當成天然節理切段。")
            if depth_start is None or depth_end is None:
                rqd_depth_cols = st.columns(2)
                with rqd_depth_cols[0]:
                    rqd_depth_start = st.number_input("本次計算起始深度（m）", min_value=0.0, value=0.0, step=0.5, key="core_rqd_manual_start")
                with rqd_depth_cols[1]:
                    rqd_depth_end = st.number_input("本次計算結束深度（m）", min_value=0.1, value=1.0, step=0.5, key="core_rqd_manual_end")
            else:
                rqd_depth_start, rqd_depth_end = float(depth_start), float(depth_end)
                st.caption(f"計算深度範圍：{rqd_depth_start:g}–{rqd_depth_end:g} m（由柱狀圖列號推算）。")
            recovered_total_mm = st.number_input(
                "實際取回岩心總長度（mm；所有取回岩心都計入）",
                min_value=0.0, value=0.0, step=10.0, key="core_recovered_total_mm",
            )
            rqd_piece_lengths_text = st.text_area(
                "依天然節理分段後的岩心長度（mm；以逗號分隔）",
                placeholder="例如：125, 180, 95, 210, 110（僅天然節理界定的段長；95 mm 不計入 RQD）",
                key="core_rqd_piece_lengths",
                height=72,
            )
            if st.button("計算採取率與 RQD", key="calculate_core_rqd"):
                if rqd_depth_end <= rqd_depth_start:
                    st.error("結束深度必須大於起始深度。")
                elif recovered_total_mm <= 0:
                    st.error("請先輸入實際取回岩心總長度。")
                elif not rqd_piece_lengths_text.strip():
                    st.error("請輸入依天然節理分段後的岩心長度，才能計算 RQD。")
                else:
                    try:
                        natural_piece_lengths = parse_piece_lengths(rqd_piece_lengths_text)
                        indices = calculate_core_indices(
                            rqd_depth_end - rqd_depth_start, [recovered_total_mm],
                            rqd_piece_lengths_mm=natural_piece_lengths,
                        )
                        st.session_state["core_rqd_result"] = indices
                        st.session_state["core_rqd_depth"] = (rqd_depth_start, rqd_depth_end)
                        st.session_state["core_rqd_borehole"] = core_borehole
                    except ValueError as exc:
                        st.error(str(exc))

            if "core_rqd_result" in st.session_state:
                result = st.session_state["core_rqd_result"]
                if result["over_recovery"]:
                    st.warning("回收岩心總長超過鑽進長度，請檢查深度區間或段長輸入。")
                if result.get("rqd_exceeds_recovered"):
                    st.warning("RQD 計入長度大於實際回收長度，請檢查天然節理分段資料。")
                if result.get("rqd_exceeds_drilled"):
                    st.warning("RQD 計入長度超過鑽進長度，請檢查輸入資料。")
                r1, r2, r3 = st.columns(3)
                r1.metric("岩心採取率", f"{result['recovery_percent']:.1f}%")
                r2.metric("RQD", f"{result['rqd_percent']:.1f}%")
                r3.metric("RQD 合格天然岩心段數", f"{result['qualifying_piece_count']} / {result['piece_count']}")
                st.caption(
                    f"鑽進長度 {result['drilled_length_mm']:.0f} mm；"
                    f"回收長度 {result['recovered_length_mm']:.0f} mm；"
                    f"RQD 計入長度 {result['rqd_length_mm']:.0f} mm。"
                )
                st.download_button(
                    "下載 RQD 計算結果（JSON）",
                    data=__import__("json").dumps({
                        "borehole_id": st.session_state.get("core_rqd_borehole", ""),
                        "depth_start_m": st.session_state.get("core_rqd_depth", (None, None))[0],
                        "depth_end_m": st.session_state.get("core_rqd_depth", (None, None))[1],
                        **result,
                        "method_note": "Core recovery uses total physically recovered core length. RQD uses only user-confirmed natural-discontinuity-bounded piece lengths >= 100 mm; mechanical breaks should be fitted together and must not be treated as natural discontinuities.",
                    }, ensure_ascii=False, indent=2),
                    file_name="core_rqd_result.json",
                    mime="application/json",
                )

    # --- 新增：GSI 視覺化交叉查表工具 ---
    with st.expander("🗺️ GSI 現場評估", expanded=False):
        st.markdown("請依據現場岩體狀況，分別選取 **「岩體結構 (Structure)」** 與 **「節理面狀況 (Surface Condition)」**：")
        
        gsi_struct = st.selectbox("1. 岩體結構評估 (Structure)", [
            "A. 巨塊狀 (Intact/Massive): 岩石塊體巨大，裂隙極少或無 (極佳)",
            "B. 塊狀 (Blocky): 幾組互相交切之節理，岩塊呈方塊狀互鎖 (良好)",
            "C. 次塊狀/夾雜碎屑 (Very Blocky / Disturbed): 多組密集節理，常受擾動或輕微風化",
            "D. 碎裂/高度解體 (Blocky/Seamy/Broken): 節理極度發育，破碎成多角形小塊",
            "E. 泥化破碎/極度揉屬 (Crushed/Sheared/Faulted): 如斷層泥、極度風化碎屑或土石混合崩積料"
        ])
        
        gsi_cond = st.selectbox("2. 節理面狀況評估 (Joint Condition)", [
            "I. 節理面極佳：平滑、未風化、面緊密閉合、無填充物",
            "II. 節理面良好：輕微粗糙、微風化、面微開口 (<1mm)",
            "III. 節理面普通：平滑至中等粗糙、中度風化、有軟弱夾層填充物",
            "IV. 節理面不良：風化嚴重、夾有黏土質軟弱填充物、面開口較大 (>1-5mm)",
            "V. 節理面極差：極度風化碎裂、厚層泥質填充物、遇水易軟化崩解"
        ])
        
        # 簡易 GSI 矩陣對照邏輯
        struct_idx = ["A", "B", "C", "D", "E"].index(gsi_struct[0])
        cond_idx = ["I", "II", "III", "IV", "V"].index(gsi_cond[0])
        
        # 經典 GSI 矩陣估算矩陣
        gsi_matrix = [
            [85, 75, 65, 55, 40], # Massive (A)
            [75, 65, 55, 45, 30], # Blocky (B)
            [65, 55, 45, 35, 25], # Very Blocky (C)
            [50, 45, 35, 25, 15], # Broken (D)
            [35, 30, 25, 20, 10]  # Crushed (E)
        ]
        matrix_gsi = gsi_matrix[struct_idx][cond_idx]
        st.success(f"🎯 依據現場條件交叉對照，建議 **GSI = {matrix_gsi}**。您可以直接在下方滑桿套用此數值！")
        
        apply_matrix_gsi = st.button("📥 一鍵套用此 GSI 建議值")

    hb_col1, hb_col2, hb_col3 = st.columns(3)
    
    with hb_col1:
        st.markdown("##### 1. 岩塊強度與裂隙結構 (GSI & mi)")
        default_gsi_val = matrix_gsi if 'apply_matrix_gsi' in locals() and apply_matrix_gsi else 45
        gsi = st.slider("地質強度指標 (GSI)", min_value=10, max_value=95, value=default_gsi_val, step=1)
        
        rock_preset = st.selectbox("選擇台灣常見岩性組成 (自動帶入常數 mi)", [
            "砂岩 Sandstone (mi = 17)",
            "頁岩 Shale (mi = 6)",
            "泥岩 / 黏土岩 Mudstone / Claystone (mi = 4)",
            "粉砂岩 Siltstone (mi = 7)",
            "板岩 Slate (mi = 7)",
            "片岩 Schist (mi = 10)",
            "礫岩 Conglomerate (mi = 21)",
            "石灰岩 Limestone (mi = 10)",
            "安山岩 Andesite (mi = 25)",
            "花崗岩 Granite (mi = 32)",
            "自訂輸入 mi"
        ])
        mi_dict = {"17": 17, "6": 6, "4": 4, "7": 7, "10": 10, "21": 21, "25": 25, "32": 32}
        default_mi = 17
        for k, v in mi_dict.items():
            if f"mi = {k})" in rock_preset:
                default_mi = v
                break
        mi = st.number_input("完整岩石材料常數 (mi)", min_value=1, max_value=40, value=default_mi, step=1, key="geolysis_number_input_line_351")
        sig_ci = st.number_input("完整岩石單軸抗壓強度 σci (UCS) [MPa]", min_value=0.5, max_value=250.0, value=25.0, step=1.0, key="geolysis_number_input_line_352")
        st.caption(f"換算應力單位：$\\sigma_{{ci}} = {sig_ci * 1000.0:.0f}\\text{{ kPa}}$")

    with hb_col2:
        st.markdown("##### 2. 擾動因子與工程應用尺度")
        d_preset = st.selectbox("開挖/自然擾動程度參考 (D)", [
            "自然邊坡 / 人工精細開挖或機械開挖 (D = 0.0)",
            "小規模控制爆破或輕微解壓邊坡 (D = 0.5)",
            "大規模開挖鬆動 / 嚴重應力釋放或崩塌擾動邊坡 (D = 0.7)",
            "劣質爆破岩坡 (D = 1.0)",
            "自訂擾動因子 D"
        ])
        if "0.0" in d_preset: d_default = 0.0
        elif "0.5" in d_preset: d_default = 0.5
        elif "0.7" in d_preset: d_default = 0.7
        elif "1.0" in d_preset: d_default = 1.0
        else: d_default = 0.0
        d_factor = st.slider("擾動因子 (Disturbance Factor, D)", min_value=0.0, max_value=1.0, value=d_default, step=0.05)
        
        app_type = st.radio("選擇圍壓上限 (σ3_max) 決定方式：", [
            "邊坡穩定分析 (Slope Stability - 依邊坡高度 H)",
            "隧道/深基礎分析 (Tunnels - 依深度 H)",
            "一般淺層/自訂國家有效圍壓 (General σ3_max)"
        ])
        gamma_rock = st.number_input("岩體單位重 γ [kN/m³]", min_value=15.0, max_value=30.0, value=23.0, step=0.5, key="geolysis_number_input_line_376")
        h_slope = st.number_input("分析邊坡高度或覆蓋深度 H [m]", min_value=1.0, max_value=500.0, value=20.0, step=1.0, key="geolysis_number_input_line_377")

    # --- Hoek-Brown (2002) 核心運算 ---
    mb = mi * math.exp((gsi - 100.0) / (28.0 - 14.0 * d_factor))
    s_hb = math.exp((gsi - 100.0) / (9.0 - 3.0 * d_factor))
    a_hb = 0.5 + (1.0 / 6.0) * (math.exp(-gsi / 15.0) - math.exp(-20.0 / 3.0))
    
    sig_c_mass = sig_ci * (s_hb ** a_hb)
    sig_cm = sig_ci * ((mb + 4.0 * s_hb - a_hb * (mb - 8.0 * s_hb)) * ((mb / 4.0 + s_hb) ** (a_hb - 1.0))) / (2.0 * (1.0 + a_hb) * (2.0 + a_hb))
    
    gamma_mpa = gamma_rock / 1000.0
    if "邊坡" in app_type:
        sig3_max = sig_cm * 0.72 * ((sig_cm / (gamma_mpa * h_slope)) ** (-0.91))
    elif "隧道" in app_type:
        sig3_max = sig_cm * 0.47 * ((sig_cm / (gamma_mpa * h_slope)) ** (-0.94))
    else:
        sig3_max = sig_ci / 4.0
        
    sig3n = max(1e-5, sig3_max / sig_ci)
    
    num_phi = 6.0 * a_hb * mb * ((s_hb + mb * sig3n) ** (a_hb - 1.0))
    den_phi = 2.0 * (1.0 + a_hb) * (2.0 + a_hb) + 6.0 * a_hb * mb * ((s_hb + mb * sig3n) ** (a_hb - 1.0))
    sin_phi = max(0.0, min(0.99, num_phi / den_phi))
    phi_hb_deg = math.degrees(math.asin(sin_phi))
    
    num_c = sig_ci * ((1.0 + 2.0 * a_hb) * s_hb + (1.0 - a_hb) * mb * sig3n) * ((s_hb + mb * sig3n) ** (a_hb - 1.0))
    den_c = (1.0 + a_hb) * (2.0 + a_hb) * math.sqrt(1.0 + (6.0 * a_hb * mb * ((s_hb + mb * sig3n) ** (a_hb - 1.0))) / ((1.0 + a_hb) * (2.0 + a_hb)))
    c_hb_mpa = num_c / den_c
    c_hb_kpa = c_hb_mpa * 1000.0
    
    if sig_ci <= 100.0:
        em_gpa = (1.0 - d_factor / 2.0) * math.sqrt(sig_ci / 100.0) * (10.0 ** ((gsi - 10.0) / 40.0))
    else:
        em_gpa = (1.0 - d_factor / 2.0) * (10.0 ** ((gsi - 10.0) / 40.0))

    with hb_col3:
        st.markdown("##### 3. 等效莫耳－庫倫與岩體參數成果")
        st.success(f"#### 等效凝聚力 $c'$：`{c_hb_kpa:.1f} kPa` ({c_hb_mpa:.3f} MPa)\n#### 等效內摩擦角 $\\phi'$：`{phi_hb_deg:.2f}°`")
        st.metric("岩體變形模數 $E_m$", f"{em_gpa:.2f} GPa ({em_gpa*1000:.0f} MPa)")
        st.metric("岩體整體抗壓強度 $\\sigma_{cm}$", f"{sig_cm:.2f} MPa ({sig_cm*1000:.0f} kPa)")
        st.caption(f"**Hoek-Brown 準則常數**：$m_b = {mb:.3f}$ ｜ $s = {s_hb:.5f}$ ｜ $a = {a_hb:.3f}$")

    with st.expander("📈 展開檢視：Hoek-Brown 非線性破壞包絡線 vs. 等效莫耳－庫倫直線圖", expanded=False):
        s3_vals_kpa = [sig3_max * 1000.0 * (i / 50.0) for i in range(51)]
        s1_hb_kpa = []
        s1_mc_kpa = []
        tan_phi = math.tan(math.radians(phi_hb_deg))
        kp = (1.0 + sin_phi) / (1.0 - sin_phi)
        sig_cm_mc_kpa = 2.0 * c_hb_kpa * math.sqrt(kp)
        
        for s3_k in s3_vals_kpa:
            s3_m = s3_k / 1000.0
            s1_m = s3_m + sig_ci * ((mb * (s3_m / sig_ci) + s_hb) ** a_hb)
            s1_hb_kpa.append(s1_m * 1000.0)
            s1_mc_kpa.append(sig_cm_mc_kpa + kp * s3_k)
            
        fig_hb = go.Figure()
        fig_hb.add_trace(go.Scatter(x=s3_vals_kpa, y=s1_hb_kpa, mode='lines', name='Hoek-Brown 非線性準則', line=dict(color='#d62728', width=3)))
        fig_hb.add_trace(go.Scatter(x=s3_vals_kpa, y=s1_mc_kpa, mode='lines', name=f"等效 Mohr-Coulomb (c'={c_hb_kpa:.0f}kPa, ϕ'={phi_hb_deg:.1f}°)", line=dict(color='#1f77b4', width=2, dash='dash')))
        fig_hb.update_layout(title="主應力空間破壞包絡線擬合 (σ1 vs. σ3)", xaxis_title="最小主應力 / 圍壓 σ3 [kPa]", yaxis_title="最大主應力 σ1 [kPa]", height=380)
        st.plotly_chart(fig_hb, width="stretch")


# ==============================================================================
# 模組二：土壤分類系統
# ==============================================================================
with st.expander("🌱 模組二：土壤分類系統 (USCS & AASHTO)", expanded=exp_2):
    st.subheader("🌱 土壤分類系統")
    col_a, col_b = st.columns(2)
    with col_a:
        ll = st.number_input("液性限度 Liquid Limit (LL) [%]", min_value=0.0, max_value=200.0, value=42.0, step=1.0, key="geolysis_number_input_line_447")
        pl = st.number_input("塑性限度 Plastic Limit (PL) [%]", min_value=0.0, max_value=200.0, value=22.0, step=1.0, key="geolysis_number_input_line_448")
        is_np = st.checkbox("無塑性 (Non-Plastic, NP)", value=False)
        organic = st.checkbox("含高有機質 (Organic Soil)", value=False)
        pi = 0.0 if is_np else max(0.0, ll - pl)
    with col_b:
        fines = st.number_input("過 200 號篩百分比 (Fines < 0.075mm) [%]", min_value=0.0, max_value=100.0, value=38.0, step=1.0, key="geolysis_number_input_line_453")
        sand = st.number_input("砂粒含量 (Sand, 0.075mm ~ 4.75mm) [%]", min_value=0.0, max_value=100.0, value=42.0, step=1.0, key="geolysis_number_input_line_454")
        gravel = max(0.0, 100.0 - fines - sand)
        d10 = st.number_input("有效粒徑 D10 [mm]", min_value=0.001, value=0.15, format="%.3f", key="geolysis_number_input_line_456")
        d30 = st.number_input("粒徑 D30 [mm]", min_value=0.001, value=0.60, format="%.3f", key="geolysis_number_input_line_457")
        d60 = st.number_input("粒徑 D60 [mm]", min_value=0.001, value=1.80, format="%.3f", key="geolysis_number_input_line_458")
        cu = d60 / d10 if d10 > 0 else 0.0
        cc = (d30 ** 2) / (d10 * d60) if (d10 * d60) > 0 else 0.0

    a_line = 0.73 * (ll - 20.0)
    if fines >= 50.0:
        uscs_sym, uscs_desc = ("CL", "無機低塑性黏土") if ll < 50 else ("CH", "無機高塑性黏土")
    else:
        uscs_sym, uscs_desc = "SC", "黏土質砂土"
    
    gi = max(0, round((fines - 35.0) * (0.2 + 0.005 * (ll - 40.0)) + 0.01 * (fines - 15.0) * (pi - 10.0)))
    aashto_sym, aashto_desc = ("A-7-6", "普通至不良（粉土－黏土材料）") if fines > 35 else ("A-2-4", "優良至良好（粒料土壤）")

    res_col1, res_col2 = st.columns(2)
    with res_col1:
        st.success(f"#### USCS 分類結果：`{uscs_sym}` — {uscs_desc}")
    with res_col2:
        st.info(f"#### AASHTO 分類結果：`{aashto_sym} ({gi})` — {aashto_desc}")


# ==============================================================================
# 模組三：SPT 標準貫入試驗全修正
# ==============================================================================
with st.expander("🔨 模組三：SPT 標準貫入試驗全修正", expanded=exp_3):
    st.subheader("🔨 SPT 標準貫入試驗全修正")
    col_spt1, col_spt2, col_spt3 = st.columns(3)
    with col_spt1:
        n_measured = st.number_input("現場量測 SPT-N 值", min_value=1, max_value=100, value=18, key="geolysis_number_input_line_485")
        em = 0.80
        cb, cs, cr = 1.0, 1.0, 0.95
    with col_spt2:
        sigma_v = st.number_input("有效覆土應力 σ'_v [kPa]", min_value=5.0, value=95.0, step=5.0, key="geolysis_number_input_line_489")
        cn = min(2.0, math.sqrt(100.0 / sigma_v))
    n60 = (n_measured * em * cb * cs * cr) / 0.60
    n1_60_corr = n60 * cn
    phi_hat = min(45.0, math.sqrt(20.0 * n1_60_corr) + 15.0)
    with col_spt3:
        st.metric("能量與器材修正值 N60", f"{n60:.2f}")
        st.metric("最終設計貫入值 (N1)'60", f"{n1_60_corr:.2f}")
        st.info(f"💡 推估內摩擦角：**{phi_hat:.1f}°**")


# ==============================================================================
# 模組四：容許承載力與沉陷控制
# ==============================================================================
with st.expander("📏 模組四：容許承載力與沉陷控制", expanded=exp_4):
    st.subheader("📏 容許承載力與沉陷控制")
    c_abc1, c_abc2, c_abc3 = st.columns(3)
    with c_abc1:
        n_design = st.number_input("影響深度內設計平均 N 值", min_value=1.0, value=float(round(n1_60_corr, 1)), step=1.0, key="geolysis_number_input_line_507")
    with c_abc2:
        b_abc = st.number_input("基礎寬度 B [m]", min_value=0.3, value=2.5, step=0.1, key="geolysis_number_input_line_509")
        df_abc = st.number_input("基礎埋深 Df [m]", min_value=0.0, value=1.5, step=0.1, key="geolysis_number_input_line_510")
    with c_abc3:
        qa = (n_design / 0.08) * min(1.0 + 0.33 * (df_abc / b_abc), 1.33)
        st.success(f"#### 容許承載力 qa：`{qa:.2f} kPa`")


# ==============================================================================
# 模組五：極限承載力四大理論
# ==============================================================================
with st.expander("🏗️ 模組五：極限承載力四大理論", expanded=exp_5):
    st.subheader("🏗️ 極限承載力四大理論")
    u_col1, u_col2, u_col3, u_col4 = st.columns(4)
    with u_col1:
        ubc_theory = st.selectbox("選擇理論公式", ["Vesic (1973)", "Hansen (1970)", "Meyerhof (1963)", "Terzaghi (1943)"])
        f_shape = st.selectbox("基礎形狀", ["連續/條形 (Strip)", "方形 (Square)", "圓形 (Circle)", "矩形 (Rectangle)"])
        b_ubc = st.number_input("基礎寬度 B [m]", min_value=0.2, value=2.0, step=0.1, key="geolysis_number_input_line_525")
        df_ubc = st.number_input("基礎埋深 Df [m]", min_value=0.0, value=1.5, step=0.1, key="geolysis_number_input_line_526")
    with u_col2:
        param_source = st.selectbox("力學參數來源", ["手動輸入 c, ϕ", "帶入模組一：Hoek-Brown 等效 c', ϕ'", "帶入模組三：SPT 經驗估算 ϕ"])
        default_c = float(round(c_hb_kpa, 1)) if "模組一" in param_source else 15.0
        default_phi = float(round(phi_hb_deg, 1)) if "模組一" in param_source else (float(round(phi_hat, 1)) if "模組三" in param_source else 30.0)
        c_ubc = st.number_input("凝聚力 c [kPa]", min_value=0.0, value=default_c, step=1.0, key="geolysis_number_input_line_531")
        phi_ubc = st.number_input("內摩擦角 ϕ [度]", min_value=0.0, max_value=55.0, value=min(55.0, default_phi), step=1.0, key="geolysis_number_input_line_532")
        gamma_ubc = st.number_input("濕單位重 γ [kN/m³]", min_value=10.0, value=18.5, step=0.5, key="geolysis_number_input_line_533")
        fs_ubc = st.number_input("安全係數 (FS)", min_value=1.0, value=3.0, step=0.5, key="geolysis_number_input_line_534")
    with u_col3:
        dw_ubc = st.number_input("地下水位深度 Dw [m]", min_value=0.0, value=1.2, step=0.2, key="geolysis_number_input_line_536")
    
    # 簡易極限承載力運算
    phi_r = math.radians(phi_ubc)
    nq = math.exp(math.pi * math.tan(phi_r)) * (math.tan(math.radians(45.0) + phi_r / 2.0) ** 2)
    nc = (nq - 1.0) / math.tan(phi_r) if phi_ubc > 0 else 5.14
    q_ult = (c_ubc * nc) + (gamma_ubc * df_ubc * nq)
    q_allow = q_ult / fs_ubc

    with u_col4:
        st.metric("總極限承載力 q_ult", f"{q_ult:.2f} kPa")
        st.metric(f"總容許承載力 q_all (FS={fs_ubc})", f"{q_allow:.2f} kPa")
