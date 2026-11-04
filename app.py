import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
import base64
import hashlib
from io import BytesIO
from pathlib import Path
import streamlit.components.v1 as components

from core_photo_analysis import inspect_image, pixel_scale_mm_per_px, parse_piece_lengths, calculate_core_indices, detect_tray_rows, draw_row_candidates, detect_blue_tray_rows, draw_combined_row_candidates, detect_blue_tray_quadrilateral, draw_tray_quadrilateral, rectify_tray_perspective, calculate_fixed_tray_row_layout, draw_fixed_tray_row_layout, crop_fixed_tray_rows, detect_core_discontinuity_candidates, draw_core_discontinuity_candidates, segment_lengths_from_confirmed_cuts, calibrate_row_measurement_span, segment_core_occupancy, draw_core_occupancy_segments, analyze_core_row_v8, draw_core_row_analysis_v8, rotate_image, validate_tray_quadrilateral, crop_tray_insets

core_tray_editor = components.declare_component(
    "core_tray_editor", path=str(Path(__file__).parent / "point_editor")
)

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
with st.expander("⛰️ 模組一：Hoek-Brown 岩體裂隙組成推估等效 c', ϕ' (含 GSI 現場對照矩陣)", expanded=exp_1):
    st.subheader("⛰️ Hoek-Brown 岩體裂隙與等效莫耳－庫倫參數推估")


    # --- 岩芯照片分析（第一階段：照片建檔、比例校正與 RQD 計算） ---
    with st.expander("📷 岩芯照片分析（旋轉、透視校正與分列判識）", expanded=False):
        st.markdown(
            "上傳岩芯箱照片並建立深度資料。可先檢查照片，並試行水平列界候選定位；"
            "**目前尚未自動量測每段岩芯長度，也未辨識天然節理／機械斷裂**，因此不會把影像候選冒充為正式 RQD。"
        )
        photo_col1, photo_col2 = st.columns([1, 1])
        with photo_col1:
            core_borehole = st.text_input("鑽孔編號（選填）", key="core_borehole_id")
            depth_start = st.number_input("照片代表深度起點 [m]", min_value=0.0, value=12.0, step=0.5, key="core_depth_start")
            depth_end = st.number_input("照片代表深度終點 [m]", min_value=0.1, value=15.0, step=0.5, key="core_depth_end")
            core_photos = st.file_uploader(
                "上傳岩芯箱照片（可多選）",
                type=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
                key="core_photo_upload",
                help="建議使用原始照片，讓岩芯完整入鏡、避免透視變形，並保留岩芯箱刻度或尺寸參照。",
            )
        with photo_col2:
            st.markdown("**比例校正**")
            st.caption("若照片中有尺或已知尺寸的岩芯箱構件，可量取其像素長度後換算比例。")
            ref_mm = st.number_input("參照物實際長度 [mm]", min_value=0.0, value=100.0, step=10.0, key="core_ref_mm")
            ref_px = st.number_input("同一參照物在照片中的像素長度 [px]", min_value=0.0, value=0.0, step=1.0, key="core_ref_px")
            if ref_px > 0 and ref_mm > 0:
                st.success(f"比例：{pixel_scale_mm_per_px(ref_mm, ref_px):.4f} mm/px")
            else:
                st.warning("尚未完成比例校正；目前不能從照片像素換算岩芯實際長度。")

        if core_photos:
            st.markdown("**照片前處理與岩芯列判識**")
            st.caption("每張照片獨立保存旋轉、四角、裁切與列界設定。標準箱型以 4 列 × 每列 1,000 mm 處理；請確認四角框住同一箱體，並確認裁切沒有切掉岩芯端部。")
            for idx, uploaded in enumerate(core_photos, start=1):
                try:
                    raw_bytes = uploaded.getvalue()
                    image, info = inspect_image(raw_bytes)
                    photo_token = hashlib.sha1(raw_bytes).hexdigest()[:12]
                    with st.container(border=True):
                        st.markdown(f"**{idx}. {uploaded.name}**")
                        st.caption(f"原始照片：{info.width_px} × {info.height_px} px｜{info.file_size_bytes / 1024:.1f} KB")
                        rotate_key = f"core_rotate_{photo_token}"
                        rotation = st.selectbox(
                            "照片旋轉（順時針）", [0, 90, 180, 270], index=0,
                            format_func=lambda x: f"{x}°" if x else "0°（不旋轉）", key=rotate_key,
                        )
                        working_image = rotate_image(image, rotation)
                        st.image(working_image, caption=f"旋轉後影像｜{working_image.width} × {working_image.height} px", use_container_width=True)

                        config_key = f"core_quad_{photo_token}_{rotation}"
                        if config_key not in st.session_state:
                            detected = detect_blue_tray_quadrilateral(working_image)
                            if detected.get("success"):
                                initial_corners = detected["corners"]
                                st.session_state[f"{config_key}_source"] = "藍色箱體自動偵測候選"
                                st.session_state[f"{config_key}_detect_info"] = detected
                            else:
                                margin_x, margin_y = working_image.width * 0.04, working_image.height * 0.04
                                initial_corners = [[margin_x, margin_y], [working_image.width-margin_x, margin_y],
                                                   [working_image.width-margin_x, working_image.height-margin_y],
                                                   [margin_x, working_image.height-margin_y]]
                                st.session_state[f"{config_key}_source"] = "人工調整用初始框（自動偵測未成功）"
                                st.session_state[f"{config_key}_detect_info"] = detected
                            st.session_state[config_key] = initial_corners
                            st.session_state[f"{config_key}_initial"] = [point[:] for point in initial_corners]

                        detect_info = st.session_state.get(f"{config_key}_detect_info", {})
                        if detect_info.get("success"):
                            st.success("已取得藍色托盤外框候選；仍須拖曳檢查四角位置。")
                        else:
                            st.warning("自動偵測未成功，已提供照片內縮 4% 的初始框。請手動拖曳四角，不要直接假設初始框正確。")
                        st.caption("四角編輯器：拖曳 1 左上、2 右上、3 右下、4 左下控制點；完成後按編輯器內的「套用目前四角」。")
                        preview_buf = BytesIO()
                        working_image.save(preview_buf, format="JPEG", quality=88)
                        image_data = "data:image/jpeg;base64," + base64.b64encode(preview_buf.getvalue()).decode("ascii")
                        editor_value = core_tray_editor(
                            image_data=image_data, corners=st.session_state[config_key],
                            initial_corners=st.session_state.get(f"{config_key}_initial", st.session_state[config_key]),
                            key=f"core_editor_{photo_token}_{rotation}", default=None,
                    )
                        if isinstance(editor_value, dict) and editor_value.get("applied"):
                            try:
                                checked = validate_tray_quadrilateral(
                                    editor_value.get("corners"), working_image.width, working_image.height
                                )
                                st.session_state[config_key] = checked
                                st.success("四角設定已套用並通過幾何檢查。")
                            except Exception as corner_exc:
                                st.error(f"四角設定未接受：{corner_exc}")

                        use_quad = st.checkbox(
                            "使用目前四角進行透視校正", key=f"core_use_quad_{photo_token}_{rotation}", value=False
                        )
                        if use_quad:
                            try:
                                corners = validate_tray_quadrilateral(
                                    st.session_state[config_key], working_image.width, working_image.height
                                )
                                rectified, rect_info = rectify_tray_perspective(
                                    working_image, {"success": True, "corners": corners}
                                )
                                st.image(rectified, caption=f"透視校正｜{rectified.width} × {rectified.height} px", use_container_width=True)
                                st.caption(rect_info["warning"])

                                st.markdown("**逐張照片裁切有效箱體範圍**")
                                crop_col1, crop_col2 = st.columns(2)
                                with crop_col1:
                                    left_pct = st.slider("左側裁切 (%)", 0.0, 15.0, 2.0, 0.5, key=f"core_crop_l_{photo_token}")
                                    top_pct = st.slider("上側裁切 (%)", 0.0, 15.0, 2.0, 0.5, key=f"core_crop_t_{photo_token}")
                                with crop_col2:
                                    right_pct = st.slider("右側裁切 (%)", 0.0, 15.0, 2.0, 0.5, key=f"core_crop_r_{photo_token}")
                                    bottom_pct = st.slider("下側裁切 (%)", 0.0, 15.0, 2.0, 0.5, key=f"core_crop_b_{photo_token}")
                                cropped_tray, crop_info = crop_tray_insets(
                                    rectified, left_pct, right_pct, top_pct, bottom_pct
                                )
                                st.image(cropped_tray, caption=f"裁切後有效箱體｜{crop_info['width_px']} × {crop_info['height_px']} px", use_container_width=True)
                                st.caption(crop_info["warning"])

                                st.markdown("**4 列 × 每列 1,000 mm：分列與判識**")
                                st.caption("列界預設等分，但實際照片可能因箱體透視、列間隔或裁切而不完全等高；可在此逐張調整三條水平分界線。")
                                row_boundary_cols = st.columns(3)
                                with row_boundary_cols[0]:
                                    row_b1 = st.slider("第 1／2 列分界 (%)", 10.0, 40.0, 25.0, 0.5, key=f"core_row_b1_{photo_token}")
                                with row_boundary_cols[1]:
                                    row_b2 = st.slider("第 2／3 列分界 (%)", 30.0, 70.0, 50.0, 0.5, key=f"core_row_b2_{photo_token}")
                                with row_boundary_cols[2]:
                                    row_b3 = st.slider("第 3／4 列分界 (%)", 60.0, 90.0, 75.0, 0.5, key=f"core_row_b3_{photo_token}")
                                row_layout = calculate_fixed_tray_row_layout(
                                    cropped_tray, row_count=4, row_length_mm=1000.0,
                                    row_boundaries_pct=[row_b1, row_b2, row_b3],
                                )
                                st.image(
                                    draw_fixed_tray_row_layout(cropped_tray, row_layout),
                                    caption="黃色框＝目前設定的四列範圍。請確認每列完整對應實際箱格，且沿列方向有效長度為 1 m。",
                                    use_container_width=True,
                                )
                                st.metric("每列名義比例尺", f"{row_layout['mm_per_px']:.4f} mm/px")
                                row_crops = crop_fixed_tray_rows(cropped_tray, row_layout)
                                crop_cols = st.columns(4)
                                for row_i, row_crop in enumerate(row_crops):
                                    with crop_cols[row_i]:
                                        st.image(row_crop, caption=f"第 {row_i+1} 列｜1 m", use_container_width=True)

                                for row_i, row_crop in enumerate(row_crops):
                                    with st.expander(f"第 {row_i+1} 列｜岩芯本體／空隙判識", expanded=(row_i == 0)):
                                        st.caption("系統以多高度區帶判斷影像占據情形；只產生岩芯本體與空隙候選，不自動判定天然節理、機械破損或 RQD 合格段。")
                                        x_start, x_end = st.slider(
                                            "本列有效 1 m 左右端點 (px)", 0, row_crop.width,
                                            (0, row_crop.width), 1, key=f"core_v8_span_{photo_token}_{row_i}"
                                        )
                                        measured_row, row_cal = calibrate_row_measurement_span(
                                            row_crop, x_start, x_end, 1000.0
                                        )
                                        result = analyze_core_row_v8(measured_row, row_cal["mm_per_px"])
                                        if result.get("success"):
                                            st.image(
                                                draw_core_row_analysis_v8(measured_row, result),
                                                caption="綠色＝岩芯本體候選；紅色＝疑似空隙；黃色＝不確定區。",
                                                use_container_width=True,
                                            )
                                            st.write({
                                                "岩芯本體候選數": len(result["segments"]),
                                                "候選長度 (mm)": [round(x["length_mm"], 1) for x in result["segments"]],
                                                "候選信心": [x["confidence"] for x in result["segments"]],
                                                "疑似空隙 (mm)": [round(x["length_mm"], 1) for x in result["gaps"]],
                                                "不確定區 (mm)": [round(x["length_mm"], 1) for x in result["uncertain"]],
                                            })
                                            st.warning(result["warning"])
                                        else:
                                            st.warning(result.get("warning", "本列無法判識。"))
                                        st.caption(row_cal["warning"])
                            except Exception as rect_exc:
                                st.error(f"前處理／分列失敗：{rect_exc}。請檢查四角、裁切比例及三條列界是否由上至下遞增。")
                except Exception as exc:
                    st.error(f"{uploaded.name}：圖片讀取失敗（{exc}）")

        st.divider()
        st.markdown("**RQD 計算資料（第一階段採可追溯的段長輸入）**")
        st.caption(
            "請依照片量測每一段可計入的岩芯長度，單位 mm，以逗號或換行分隔。"
            "只輸入確認屬於天然岩芯段的長度；鑽取／搬運造成的機械斷裂須先依現場紀錄判別。"
        )
        piece_lengths_text = st.text_area(
            "岩芯段長度 [mm]",
            placeholder="例如：125, 180, 95, 210, 110",
            key="core_piece_lengths",
            height=90,
        )
        if st.button("計算採取率與 RQD", key="calculate_core_rqd"):
            if depth_end <= depth_start:
                st.error("深度終點必須大於起點。")
            elif not piece_lengths_text.strip():
                st.error("請先輸入可確認的岩芯段長度。")
            else:
                try:
                    lengths = parse_piece_lengths(piece_lengths_text)
                    indices = calculate_core_indices(depth_end - depth_start, lengths)
                    st.session_state["core_rqd_result"] = indices
                    st.session_state["core_rqd_depth"] = (depth_start, depth_end)
                    st.session_state["core_rqd_borehole"] = core_borehole
                except ValueError as exc:
                    st.error(str(exc))

        if "core_rqd_result" in st.session_state:
            result = st.session_state["core_rqd_result"]
            if result["over_recovery"]:
                st.warning("回收岩芯總長超過鑽進長度，請檢查深度區間、重複量測或比例校正。")
            r1, r2, r3 = st.columns(3)
            r1.metric("岩芯採取率", f"{result['recovery_percent']:.1f}%")
            r2.metric("RQD", f"{result['rqd_percent']:.1f}%")
            r3.metric("符合 ≥100 mm 段數", f"{result['qualifying_piece_count']} / {result['piece_count']}")
            st.caption(
                f"鑽進長度 {result['drilled_length_mm']:.0f} mm；"
                f"回收長度 {result['recovered_length_mm']:.0f} mm；"
                f"RQD 計入長度 {result['rqd_length_mm']:.0f} mm。"
                "此結果依人工確認段長計算，並非 AI 自動辨識成果。"
            )
            st.download_button(
                "下載本區間 RQD 計算 JSON",
                data=__import__("json").dumps({
                    "borehole_id": st.session_state.get("core_rqd_borehole", ""),
                    "depth_start_m": st.session_state.get("core_rqd_depth", (None, None))[0],
                    "depth_end_m": st.session_state.get("core_rqd_depth", (None, None))[1],
                    **result,
                    "method_note": "RQD calculated from user-confirmed core piece lengths; natural/mechanical break classification is not automated.",
                }, ensure_ascii=False, indent=2),
                file_name="core_rqd_result.json",
                mime="application/json",
            )
    
    # --- 新增：GSI 視覺化交叉查表工具 ---
    with st.expander("🗺️ 點擊展開：GSI 現場岩芯/露頭條件交叉查表（自動判定 GSI）", expanded=False):
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
        st.plotly_chart(fig_hb, use_container_width=True)


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
