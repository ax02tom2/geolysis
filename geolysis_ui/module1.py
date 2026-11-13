"""Streamlit UI for engineering module 1."""
import streamlit as st
import logging
import math
import plotly.graph_objects as go
from geolysis_engine import (
    hoek_brown_parameters, hoek_brown_structure_applicability,
    gsi_scale_effect_warning,
)


def _gsi_sensitivity_values(structure_code, lower, upper):
    """Return GSI sensitivity endpoints that remain within the HB applicability range."""
    lo, hi = int(lower), int(upper)
    if lo > hi:
        raise ValueError("GSI 初判下限不可大於上限")
    if structure_code == "A":
        hi = min(hi, 75)
        if lo > hi:
            return []
    return sorted(set((lo, hi)))


_HB_PAIRED_CASES = {
    "砂岩 Sandstone（台灣南莊層三軸案例）":
        "南莊層砂岩｜隧道完整岩心試驗單一案例",
    "砂岩 Sandstone（東北部宜蘭線瑞芳段崩塌案例）":
        "東北部宜蘭線瑞芳段風化砂岩｜崩塌回算案例",
}
_HB_CASE_MI_WITHOUT_PAIRED_UCS = {
    "片岩 Schist（蘇花公路案例）",
}
_HB_CASE_MI_UCS_OPTIONS = {
    "砂岩／頁岩互層（阿里山森林鐵路42號隧道案例）": {
        "阿里山42號隧道｜邊坡設計 UCS 43.3 MPa",
        "阿里山42號隧道｜隧道 II 類設計 UCS 65.7 MPa",
        "阿里山42號隧道｜隧道 III 類設計 UCS 43.3 MPa",
        "阿里山42號隧道｜隧道 IV 類設計 UCS 21.4 MPa",
    },
}


def _hb_case_parameter_warning(rock_preset, mi, gsi, disturbance):
    """Flag mi/GSI/D values outside the selected Taiwan case's reported ranges."""
    mi_value = float(mi)
    gsi_value = float(gsi)
    d_value = float(disturbance)
    if rock_preset == "砂岩 Sandstone（台灣南莊層三軸案例）":
        if abs(mi_value - 7.752) > 1e-6:
            return f"南莊層單一三軸案例反算 mi=7.752；目前 mi={mi_value:g}，已偏離該案例採用值。"
        if not 40.0 <= gsi_value <= 55.0:
            return (
                f"南莊層案例的岩體 GSI 參考範圍為 40–55；目前 GSI={gsi_value:g}。"
                "若採用不同 GSI，請確認其來自本工址岩體判釋，不要直接沿用完整岩心參數反算條件。"
            )
    if rock_preset == "砂岩 Sandstone（東北部宜蘭線瑞芳段崩塌案例）":
        if not 13.0 <= mi_value <= 21.0 or not 20.0 <= gsi_value <= 30.0 or not 0.8 <= d_value <= 0.9:
            return (
                f"瑞芳段案例的 mi 文獻敏感度範圍為 13–21，回算較佳範圍為 GSI=20–30、D=0.8–0.9；"
                f"目前 mi={mi_value:g}、GSI={gsi_value:g}、D={d_value:g}。"
                "超出範圍不代表本工址必然錯誤，但已不是該案例回算組合，須以現地資料重新論證。"
            )
    if rock_preset == "片岩 Schist（蘇花公路案例）":
        if abs(mi_value - 10.0) > 1e-6 or gsi_value not in (15.0, 25.0, 35.0) or abs(d_value - 0.7) > 1e-9:
            return (
                f"蘇花公路案例採用 mi=10、D=0.7，並依不同地質區分別採 GSI=15、25、35；"
                f"目前 mi={mi_value:g}、GSI={gsi_value:g}、D={d_value:g}。"
                "請確認是否屬於不同地質分區的另行判釋。"
            )
    if rock_preset == "砂岩／頁岩互層（阿里山森林鐵路42號隧道案例）":
        valid_cases = ((10.0, 60.0, 0.7), (10.0, 80.0, 0.5),
                       (10.0, 60.0, 0.5), (10.0, 40.0, 0.5))
        if not any(abs(mi_value-mi0)<=1e-6 and abs(gsi_value-gsi0)<=1e-6
                   and abs(d_value-d0)<=1e-6 for mi0,gsi0,d0 in valid_cases):
            return (
                "阿里山42號隧道計畫表 3-2-1 的組合為 mi=10，"
                "(GSI,D)=(60,0.7) 邊坡、(80,0.5) 隧道 II 類、"
                "(60,0.5) 隧道 III 類、(40,0.5) 隧道 IV 類；"
                f"目前 mi={mi_value:g}、GSI={gsi_value:g}、D={d_value:g}，"
                "不是該計畫表列組合。另報告註記砂岩 mi=17±4、頁岩 mi=6±2，"
                "不可把計畫採用 mi=10 當作岩性通用值。"
            )
    return None


def _hb_case_pair_warning(rock_preset, ucs_case_label, ucs_mode):
    """Warn when a case-derived mi is paired with another case's UCS."""
    if (rock_preset in (_HB_CASE_MI_WITHOUT_PAIRED_UCS | set(_HB_PAIRED_CASES) | set(_HB_CASE_MI_UCS_OPTIONS))
            and ucs_mode == "依現場敲擊分級初估"):
        return (
            f"目前 mi 來自「{rock_preset}」的特定案例，但 UCS 改採現場敲擊分級估值；"
            "兩者不是同一組試驗參數。此組合僅供初步敏感度分析，正式設計應優先取得同岩性完整岩心 UCS／三軸資料。"
        )
    if ucs_mode != "採用台灣岩性案例參考值" or not ucs_case_label:
        return None
    if rock_preset in _HB_CASE_MI_WITHOUT_PAIRED_UCS:
        return (
            f"目前 mi 來自「{rock_preset}」工程案例，但目前沒有同一案例可配對的完整岩心 UCS；"
            f"所選 UCS「{ucs_case_label}」是另一份資料。請確認岩性／風化程度相符，並以本工址試驗或敏感度分析驗證。"
        )
    case_options = _HB_CASE_MI_UCS_OPTIONS.get(rock_preset)
    if case_options is not None:
        if ucs_case_label not in case_options:
            return (
                f"阿里山42號隧道案例的 mi=10 僅能配對同一計畫表列 UCS 案例；"
                f"目前選擇「{ucs_case_label}」，不是該計畫的四個設計組合之一。"
            )
        return None
    for case_name, allowed_ucs in _HB_CASE_MI_UCS_OPTIONS.items():
        if ucs_case_label in allowed_ucs and rock_preset != case_name:
            return (
                f"目前 UCS「{ucs_case_label}」來自阿里山42號隧道計畫，"
                f"但 mi 岩性預設為「{rock_preset}」。請改用「{case_name}」"
                "重現該計畫組合，或改用與本工址相符的完整岩石三軸試驗 mi。"
            )
    expected_ucs = _HB_PAIRED_CASES.get(rock_preset)
    if expected_ucs is not None and ucs_case_label != expected_ucs:
        return (
            f"目前 mi 選用「{rock_preset}」，其案例配對 UCS 應為「{expected_ucs}」。"
            f"目前 UCS 選用「{ucs_case_label}」；兩者不是同一案例。"
            "請改選配對案例，或改用本工址完整岩心三軸／單壓試驗值。"
        )
    reverse = {value: key for key, value in _HB_PAIRED_CASES.items()}
    expected_mi = reverse.get(ucs_case_label)
    if expected_mi is not None and rock_preset != expected_mi:
        return (
            f"目前 UCS 選用「{ucs_case_label}」，同一案例反算 mi 對應「{expected_mi}」，"
            f"但目前 mi 選用「{rock_preset}」。請改選配對 mi，或確認兩項參數分別來自適用於本工址的試驗。"
        )
    return None


def render_module_1(expanded=False):
    # ==============================================================================
    # 模組一：Hoek-Brown (2002) 岩體裂隙推估等效 c', phi' (含 GSI 視覺化查表)
    # ==============================================================================
    with st.expander("⛰️ 模組一：Hoek–Brown 岩體參數分析", expanded):
        st.subheader("Hoek–Brown 岩體強度參數")
    
    
        # GSI 定性矩陣是原圖趨勢的工程初判估讀，不是文獻提供的精確數值格點。
        gsi_struct_options = [
            "A. 巨塊狀／完整 (Intact or Massive)：完整岩塊或少量、間距很大的不連續面",
            "B. 塊狀 (Blocky)：三組左右不連續面交切，塊體互鎖、近立方體",
            "C. 極塊狀 (Very Blocky)：四組以上節理，形成多面體塊體，仍具互鎖性",
            "D. 塊狀／擾動／層狀 (Blocky/Disturbed/Seamy)：多組交切、褶皺或層理／片理持續發育",
            "E. 解體狀 (Disintegrated)：互鎖性差，岩體嚴重破碎、角狀至次圓狀碎塊混雜",
            "F. 層狀／剪切狀 (Laminated/Sheared)：弱片理或剪裂面密集，岩體缺乏塊狀性"
        ]
        gsi_cond_options = [
            "I. 極佳 (Very Good)：非常粗糙、新鮮、未風化表面",
            "II. 良好 (Good)：粗糙、微風化，可能有鐵染",
            "III. 普通 (Fair)：平滑至中等粗糙、中度風化或蝕變",
            "IV. 不良 (Poor)：擦痕／鏡面化或高度風化，具緻密塗層或填充物",
            "V. 極差 (Very Poor)：高度風化，具軟弱黏土塗層或填充物"
        ]
        gsi_range_matrix = {
            "A": [(90,100),(80,90),(70,80),None,None],
            "B": [(75,85),(65,75),(55,65),(45,55),(35,45)],
            "C": [(65,75),(55,65),(45,55),(35,45),(25,35)],
            "D": [(50,60),(40,50),(30,40),(20,30),(10,20)],
            "E": [None,(25,35),(18,27),(10,20),(5,15)],
            "F": [None,None,(15,20),(10,15),(5,10)]
        }
    
        # GSI 現場判讀：只保留會直接影響 GSI 的兩項判讀；移除無效的區域／地形背景。
        judge_col, visual_col = st.columns([0.42, 0.58], gap="large")
        with judge_col:
            st.markdown("**岩體現況判讀**")
            gsi_method = "定性圖表初判"
            gsi_struct = st.selectbox("① 岩體結構／破碎型態", gsi_struct_options, index=1, key="gsi_structure_class")
            _struct_code = gsi_struct[0]
            gsi_selection_valid = False
            _gsi_recommended = None
            _rec_lo, _rec_hi, _rec_mid = 0, 100, 50
            gsi_cond = st.selectbox("② 不連續面表面品質", gsi_cond_options, index=2, key="gsi_surface_class")
            _cond_code = {"I":0,"II":1,"III":2,"IV":3,"V":4}.get(gsi_cond.split(".")[0], 2)
            _gsi_recommended = gsi_range_matrix[_struct_code][_cond_code]
            if _gsi_recommended is None:
                st.error("此組合在目前定性判讀矩陣中沒有可用的初判區間；請改採其他適用的岩體／結構面分析，不會自行補造數值。")
            else:
                _rec_lo, _rec_hi = _gsi_recommended
                _rec_mid = int(round((_rec_lo + _rec_hi) / 2))
                gsi_selection_valid = True
                st.markdown("**定性圖表初判結果**")
                result_col1, result_col2 = st.columns(2)
                result_col1.metric("工程初判區間", f"{_rec_lo}–{_rec_hi}")
                result_col2.metric("建議代表值", str(_rec_mid))
                st.caption("此區間是依圖表趨勢作工程初判估讀，不是原文獻逐格列出的精確數值；正式設計仍須以現地岩體結構與節理狀況覆核。")
    
        with visual_col:
            st.markdown("**GSI 判讀參考圖**")
            fig_col1, fig_col2 = st.columns(2, gap="small")
            with fig_col1:
                st.markdown("<div style='text-align:center;font-weight:600'>文獻原圖</div>", unsafe_allow_html=True)
                st.markdown("""
    <style>
    .gsi-lit-details { width:100%; }
    .gsi-lit-details summary { cursor:zoom-in; list-style:none; display:flex; justify-content:center;
      align-items:center; min-height:285px; overflow:hidden; }
    .gsi-lit-details summary::-webkit-details-marker { display:none; }
    .gsi-lit-details summary img { max-width:100%; max-height:280px; width:auto; height:auto; object-fit:contain; }
    .gsi-lit-details[open] summary { cursor:zoom-out; min-height:0; }
    .gsi-lit-details[open] summary img { max-height:120px; opacity:.55; }
    .gsi-lit-expanded { display:flex; justify-content:center; align-items:center; width:100%; padding:8px 0; }
    .gsi-lit-expanded img { display:block; max-width:100%; max-height:72vh; width:auto; height:auto; object-fit:contain; }
    .gsi-lit-zoom-hint { text-align:center; font-size:.75rem; opacity:.72; margin-top:2px; }
    </style>
    <details class="gsi-lit-details">
      <summary title="點擊放大／縮小">
        <img src="https://www.mdpi.com/applsci/applsci-11-03351/article_deploy/html/images/applsci-11-03351-g001.png"
             alt="Somodi et al. (2021), Figure 1">
      </summary>
      <div class="gsi-lit-expanded">
        <img src="https://www.mdpi.com/applsci/applsci-11-03351/article_deploy/html/images/applsci-11-03351-g001.png"
             alt="Somodi et al. (2021), Figure 1 enlarged">
      </div>
    </details>
    <div class="gsi-lit-zoom-hint">點擊圖片放大，再點一次縮小；放大時左側 GSI 選項仍可操作</div>
    <div class="gsi-lit-zoom-hint"><a href="https://doi.org/10.3390/app11083351" target="_blank" rel="noopener">Somodi et al. (2021), Figure 1 — DOI 原文</a>；開放授權 CC BY 4.0，使用時保留作者與來源標示</div>
    """, unsafe_allow_html=True)
            with fig_col2:
                st.markdown("<div style='text-align:center;font-weight:600'>系統示意圖</div>", unsafe_allow_html=True)
                gsi_demo = go.Figure(data=go.Heatmap(
                    z=[[5,4,3,2,1],[4,4,3,2,1],[4,3,2,1,1],[3,2,2,1,0],[2,2,1,0,0],[2,1,1,0,0]],
                    x=["極佳","良好","普通","不良","極差"],
                    y=["A 巨塊狀","B 塊狀","C 極塊狀","D 擾動／層狀","E 解體狀","F 剪切狀"],
                    text=[["較高","較高","中高","中低","較低"],
                          ["較高","中高","中高","中低","較低"],
                          ["中高","中高","中等","較低","較低"],
                          ["中高","中等","中等","較低","低"],
                          ["中等","中等","較低","低","低"],
                          ["中等","較低","較低","低","低"]],
                    texttemplate="%{text}", colorscale="RdYlGn", showscale=False,
                    xgap=2, ygap=2,
                    hovertemplate="節理面品質：%{x}<br>岩體結構：%{y}<br>相對判讀：%{text}<extra></extra>"
                ))
                gsi_demo.update_layout(height=285, margin=dict(l=4,r=4,t=8,b=8),
                    font=dict(size=9), xaxis_title=None, yaxis_title=None,
                    xaxis=dict(automargin=True), yaxis=dict(automargin=True))
                st.plotly_chart(gsi_demo, use_container_width=True, config={"displayModeBar":False})
            st.caption("文獻圖與系統示意圖並列；自製圖僅協助理解相對趨勢，不取代原始 GSI 判讀。")
            st.caption("適用限制：GSI 假設岩體有足夠節理組數，可視為互鎖塊體連續體；若破壞由少數持續性弱面、層面或楔形塊體控制，應另做結構面／楔形分析。濕潤或軟化會降低節理面品質評級；孔隙水壓仍須另以有效應力處理，不可直接當作 GSI 折減。FHWA 量化圖另指出，約 10 m 隧道跨度及小於 20 m 邊坡高度為其適用尺度參考，較大開挖需考慮尺度效應。")
            with st.expander("案例來源與文獻", expanded=False):
                st.markdown("""
    - [北部侯硐案例與七類岩性參數研究（國立臺灣科技大學，2022）](https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi?search=s%3Did%3D%22110NTUS5512077%22.)
    - [國道 3 號汐止崩塌案例](https://doi.org/10.1016/j.sandf.2023.101316)
    - [北部南莊層隧道岩體參數案例](https://ws.thb.gov.tw/001/Upload/OldFile/resource/html/doc/%E5%87%BA%E7%89%88%E5%93%81-%E5%8F%B0%E7%81%A3%E5%85%AC%E8%B7%AF%E5%B7%A5%E7%A8%8B/%E7%AC%AC40%E5%8D%B7%E7%AC%AC1%E6%9C%9F.pdf)
    - [中部廬山板岩深層變形](https://doi.org/10.1016/j.enggeo.2019.105387)｜[梨山地滑案例](https://www.geotech.org.tw/purchase-inner.php?id=116)｜[明德水庫 2022 崩塌](https://doi.org/10.3390/w17243556)｜[中部岩坡地震反算研究](https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi?search=s%3Did%3D%22100NCU05503042%22.)
    - [南部燕巢泥岩崩塌](https://doi.org/10.1007/s10346-019-01250-3)｜[南部深層潛移邊坡研究](https://doi.org/10.1007/s10346-024-02453-z)｜[台灣大型深層山崩地形研究](https://doi.org/10.1016/j.geomorph.2012.11.004)
    - [東部蘇花公路 115.9k 案例](https://doi.org/10.29974/JCSWC.201306_44(2).0001)｜[安通混雜岩層崩塌](https://doi.org/10.3390/w12020480)
    - [Somodi et al. (2021), GSI Figure 1](https://doi.org/10.3390/app11083351)
    - [FHWA-NHI-16-072 (2016), Figures 9-23/9-24：GSI 適用限制與 GSI>75 注意事項](https://www.fhwa.dot.gov/engineering/geotech/pubs/nhi16072.pdf)
    - [Hoek & Brown (2018), The Hoek–Brown failure criterion and GSI](https://doi.org/10.1016/j.jrmge.2018.08.001)
                """)
    
        if gsi_selection_valid:
            gsi_lower = int(st.session_state.get(f"gsi_lower_{gsi_method}_{_struct_code}_{_cond_code}", _rec_lo))
            gsi_upper = int(st.session_state.get(f"gsi_upper_{gsi_method}_{_struct_code}_{_cond_code}", _rec_hi))
            gsi_default = min(gsi_upper, max(gsi_lower, round(float(_rec_mid) * 2.0) / 2.0)) if gsi_lower <= gsi_upper else round(float(_rec_mid) * 2.0) / 2.0
        else:
            gsi_lower, gsi_upper, gsi_default = 0, 100, 50
    
    
        hb_col1, hb_col2, hb_col3 = st.columns(3)
        
        with hb_col1:
            st.markdown("##### 1. 岩塊強度與裂隙結構 (GSI & mi)")
            default_gsi_val = gsi_default if 'gsi_default' in locals() else 50
            gsi_key = f"gsi_representative_value_{gsi_method}_{_struct_code}_{_cond_code}"
            gsi_signature_key = f"{gsi_key}_source_signature"
            gsi_source_signature = (
                gsi_method, _struct_code, _cond_code,
                round(float(_rec_mid), 4) if gsi_selection_valid else None,
            )
            if st.session_state.get(gsi_signature_key) != gsi_source_signature:
                st.session_state[gsi_key] = float(default_gsi_val)
                st.session_state[gsi_signature_key] = gsi_source_signature
            elif gsi_key not in st.session_state:
                st.session_state[gsi_key] = float(default_gsi_val)
            gsi = st.number_input("GSI 代表值（可直接調整）", min_value=0.0, max_value=100.0, step=0.5, format="%.1f", key=gsi_key, disabled=not gsi_selection_valid)
            if 'gsi_lower' in locals() and 'gsi_upper' in locals() and gsi_lower <= gsi_upper and not (gsi_lower <= gsi <= gsi_upper):
                st.warning("目前 GSI 代表值超出人工判讀區間，請確認是否有意調整。")
            
            rock_preset = st.selectbox("選擇完整岩石的岩性（供 mi 初估）", [
                "砂岩 Sandstone", "頁岩 Shale", "泥岩／黏土岩 Mudstone / Claystone",
                "粉砂岩 Siltstone", "板岩 Slate", "片岩 Schist",
                "礫岩／角礫岩 Conglomerate / Breccia", "石灰岩 Limestone",
                "安山岩 Andesite", "花崗岩 Granite", "片麻岩 Gneiss", "大理岩 Marble", "砂岩 Sandstone（台灣南莊層三軸案例）", "砂岩 Sandstone（東北部宜蘭線瑞芳段崩塌案例）", "片岩 Schist（蘇花公路案例）", "砂岩／頁岩互層（阿里山森林鐵路42號隧道案例）", "自訂輸入 mi"
            ], key="hb_rock_type_for_mi")
            # Hoek / Marinos & Hoek 文獻表列典型值與變異範圍；用於初估，非特定工址試驗值。
            mi_reference = {
                "砂岩 Sandstone": (17, 13, 21, "Hoek/Marinos & Hoek：17 ± 4"),
                "頁岩 Shale": (6, 4, 8, "Hoek/Marinos & Hoek：6 ± 2"),
                "泥岩／黏土岩 Mudstone / Claystone": (4, 2, 6, "Hoek/Marinos & Hoek：4 ± 2"),
                "粉砂岩 Siltstone": (7, 5, 9, "Hoek/Marinos & Hoek：7 ± 2"),
                "板岩 Slate": (7, 3, 11, "Hoek：7 ± 4；片理方向會影響"),
                "片岩 Schist": (12, 9, 15, "Marinos & Hoek：12 ± 3；片理方向會影響"),
                "礫岩／角礫岩 Conglomerate / Breccia": (20, 15, 25, "文獻估計值；膠結物差異大"),
                "石灰岩 Limestone": (10, 8, 12, "Marinos & Hoek：10 ± 2"),
                "安山岩 Andesite": (20, 2, 38, "USGS 2022：不同安山岩實測 mi 約 2–38；以 20 作區間中點初估，離散性極高"),
                "花崗岩 Granite": (32, 29, 35, "Hoek：32 ± 3；一般文獻初估，非台灣特定工址值"),
                "片麻岩 Gneiss": (28, 23, 33, "Hoek：28 ± 5；完整試體垂直片理方向的典型值，片理方向會影響。"),
                "大理岩 Marble": (9, 6, 12, "Hoek/Marinos：9 ± 3；一般完整岩石文獻值，非特定工址試驗值。"),
                "砂岩 Sandstone（台灣南莊層三軸案例）": (7.752, 7.752, 7.752, "台灣南莊層單一完整岩心案例三軸反算 mi=7.752；不是砂岩通用值。"),
                "砂岩 Sandstone（東北部宜蘭線瑞芳段崩塌案例）": (15, 13, 21, "台鐵宜蘭線瑞芳段風化砂岩回算案例：研究初始參考 mi=17±4，案例分析採用 mi=15；敏感度範圍保留初始參考值。"),
                "片岩 Schist（蘇花公路案例）": (10, 10, 10, "蘇花公路工程報告採用 mi=10；屬工程分析採用值，不等同完整三軸試驗統計值。"),
                "砂岩／頁岩互層（阿里山森林鐵路42號隧道案例）": (10, 10, 10, "阿里山42號隧道計畫表 3-2-1 採用 mi=10；同表註記砂岩 mi=17±4、頁岩 mi=6±2。mi=10 僅供重現該計畫設計組合，不是砂岩／頁岩通用值。")
            }
            if rock_preset == "自訂輸入 mi":
                mi_low = mi_high = mi = st.number_input("完整岩石材料常數 mi（自訂）", min_value=1.0, max_value=50.0,
                    value=17.0, step=0.5, key="hb_mi_custom")
                st.caption("自訂 mi 應優先由完整岩石三軸試驗擬合取得；若無試驗，需註明採用的文獻依據。")
            else:
                mi_default, mi_low, mi_high, mi_source = mi_reference[rock_preset]
                mi = float(mi_default)
                mi = st.number_input("mi（可直接調整）", min_value=1.0, max_value=50.0, value=float(mi_default), step=0.5, key=f"hb_mi_{rock_preset}")
                _mi_range_text = f"{mi_low:g}–{mi_high:g}" if mi_low != mi_high else f"{mi_low:g}（單一案例／採用值）"
                st.caption(f"mi 參考值：{_mi_range_text}；採用 {mi:g}。{mi_source}。")
                if rock_preset == "砂岩 Sandstone（台灣南莊層三軸案例）":
                    st.markdown("[查看南莊層砂岩三軸反算案例](https://ws.thb.gov.tw/001/Upload/OldFile/resource/html/doc/%E5%87%BA%E7%89%88%E5%93%81-%E5%8F%B0%E7%81%A3%E5%85%AC%E8%B7%AF%E5%B7%A5%E7%A8%8B/%E7%AC%AC40%E5%8D%B7%E7%AC%AC1%E6%9C%9F.pdf)")
                elif rock_preset == "片岩 Schist（蘇花公路案例）":
                    st.markdown("[查看蘇花公路片岩工程參數來源](https://dptrc.sinotech.org.tw/chinese/02_about/download.php%40f%3Dmenu01361588416.pdf)")
                if rock_preset == "砂岩 Sandstone（台灣南莊層三軸案例）":
                    st.info("同一 2014 年南莊層隧道案例：完整岩心三軸反算 mi=7.752、單壓強度 σci=5.022 MPa；報告另將隧道岩體 GSI 評估為 40–55。請區分完整岩心 GSI=100（用於完整岩石參數反算）與岩體 GSI=40–55（用於岩體分析），不可混用。")
                elif rock_preset == "片岩 Schist（蘇花公路案例）":
                    st.info("同一 2012 年蘇花公路片岩案例：mi=10、擾動係數 D=0.7；不同區域的岩體 GSI 分別採 15（崩坍區）、25（崩積層）、35（塊狀岩盤）。這些是三種不同地質區的案例值，不是同一岩體的統計範圍；請依現地條件選用。")
                elif rock_preset == "砂岩 Sandstone（東北部宜蘭線瑞芳段崩塌案例）":
                    st.info("2020 年台鐵宜蘭線瑞芳段風化砂岩崩塌回算案例（Shao et al., 2021）：分析採用 mi=15、σci=25–35 MPa；回算適用範圍 GSI=20–30、D=0.8–0.9。研究內文的初始參數範圍較寬（GSI=15–40、D=0.7–0.9），上述較窄區間是回算後的案例結果，不是台灣砂岩通用值。")
                    st.markdown("[查看台鐵宜蘭線瑞芳段風化砂岩回算研究](https://www.mdpi.com/2071-1050/13/23/13452)")
                elif rock_preset == "砂岩／頁岩互層（阿里山森林鐵路42號隧道案例）":
                    st.info("阿里山森林鐵路42號隧道計畫（2018）表 3-2-1：邊坡 UCS=43.3 MPa、GSI=60、mi=10、D=0.7；隧道 II 類 UCS=65.7 MPa、GSI=80、mi=10、D=0.5；III 類 UCS=43.3 MPa、GSI=60、mi=10、D=0.5；IV 類 UCS=21.4 MPa、GSI=40、mi=10、D=0.5。報告註記砂岩 mi=17±4、頁岩 mi=6±2；計畫表的 mi=10 是特定設計採用值，不能泛化。")
                    st.markdown("[查看阿里山森林鐵路42號隧道計畫（表 3-2-1）](https://www.forest.gov.tw/file/70068)")
    
            st.markdown("**完整岩石單軸抗壓強度 σci（UCS）**")
            st.caption("UCS 是完整岩塊強度，會直接進入 Hoek–Brown 計算。沒有試驗值時，可先選同岩性案例參考值；不可用岩體強度或節理面強度替代。")
            # 舊版曾有「目前沒有可用資料」選項，將舊 session state 平順轉到案例參考模式。
            if st.session_state.get("hb_ucs_source_mode") == "目前沒有可用資料":
                st.session_state["hb_ucs_source_mode"] = "採用台灣岩性案例參考值"
            ucs_mode = st.radio("UCS 資料來源", [
                "已有實驗室 UCS 試驗值",
                "採用台灣岩性案例參考值",
                "依現場敲擊分級初估"
            ], index=1, key="hb_ucs_source_mode")
            ucs_valid = False
            _ucs_range_low = _ucs_range_high = None
            _ucs_range_label = None
            ucs_case_selected_label = None
    
            # 台灣案例／工程資料的完整岩石 UCS。kgf/cm² 以 0.0980665 換算為 MPa。
            # 區間是來源資料範圍，不代表特定工址；使用者仍須核對岩性、風化與含水狀態。
            _ucs_case_data = {
                "南莊層砂岩｜隧道完整岩心試驗單一案例": (5.022, 5.022, 5.022,
                    "完整岩心 UCS = 5.022 MPa；同一案例三軸反算 mi = 7.752。這是單一試體／案例，不是南莊層通用值。",
                    "https://www.thb.gov.tw/FileResource.axd?path=html%2Fdoc%2F%E5%87%BA%E7%89%88%E5%93%81-%E5%8F%B0%E7%81%A3%E5%85%AC%E8%B7%AF%E5%B7%A5%E7%A8%8B%2F%E7%AC%AC40%E5%8D%B7%E7%AC%AC1%E6%9C%9F.pdf"),
                "東北部宜蘭線瑞芳段風化砂岩｜崩塌回算案例": (25.0, 35.0, 30.0,
                    "Liao (2018) 砂岩試驗原始 σci 範圍 15–40 MPa；Shao et al. (2021) 為避免低值過度保守，案例分析採用 25–35 MPa。這是分析採用範圍，不是原始試驗統計信賴區間。",
                    "https://www.mdpi.com/2071-1050/13/23/13452"),
                "五指山層砂岩｜台灣岩石工程性質彙整": (34.3, 83.4, 58.9,
                    "350–850 kgf/cm²，換算約 34.3–83.4 MPa。",
                    "https://www.nusc.gov.tw/share/file/fcma/S4j6ydizyqbQti9UaY3KmQ__.pdf"),
                "木山層砂岩｜台灣岩石工程性質彙整": (29.4, 63.7, 46.6,
                    "300–650 kgf/cm²，換算約 29.4–63.7 MPa。",
                    "https://www.nusc.gov.tw/share/file/fcma/S4j6ydizyqbQti9UaY3KmQ__.pdf"),
                "大寮層砂岩｜台灣岩石工程性質彙整": (20.6, 58.8, 39.7,
                    "210–600 kgf/cm²，換算約 20.6–58.8 MPa；資料列孔隙率部分大於 15%。",
                    "https://www.nusc.gov.tw/share/file/fcma/S4j6ydizyqbQti9UaY3KmQ__.pdf"),
                "石底層砂岩｜台灣岩石工程性質彙整": (13.7, 62.8, 38.3,
                    "140–640 kgf/cm²，換算約 13.7–62.8 MPa。",
                    "https://www.nusc.gov.tw/share/file/fcma/S4j6ydizyqbQti9UaY3KmQ__.pdf"),
                "南港層砂岩｜台灣岩石工程性質彙整": (9.8, 39.2, 24.5,
                    "100–400 kgf/cm²，換算約 9.8–39.2 MPa；資料列孔隙率 10–20%。",
                    "https://www.nusc.gov.tw/share/file/fcma/S4j6ydizyqbQti9UaY3KmQ__.pdf"),
                "安山岩（未風化）｜台灣岩石工程性質彙整": (78.5, 147.1, 112.8,
                    "800–1500 kgf/cm²，換算約 78.5–147.1 MPa。",
                    "https://www.nusc.gov.tw/share/file/fcma/S4j6ydizyqbQti9UaY3KmQ__.pdf"),
                "安山岩（風化）｜台灣岩石工程性質彙整": (14.7, 34.3, 24.5,
                    "150–350 kgf/cm²，換算約 14.7–34.3 MPa；不可與未風化安山岩混用。",
                    "https://www.nusc.gov.tw/share/file/fcma/S4j6ydizyqbQti9UaY3KmQ__.pdf"),
                "花崗岩｜台灣岩石工程性質彙整（下限資料）": (196.1, 300.0, 250.0,
                    "來源僅列 >2000 kgf/cm²（>196.1 MPa），沒有上限；250 MPa 是供初步情境分析的暫用代表值，300 MPa 僅作敏感度上限，不是來源實測上限。",
                    "https://www.nusc.gov.tw/share/file/fcma/S4j6ydizyqbQti9UaY3KmQ__.pdf"),
                "玄武岩｜台灣岩石工程性質彙整": (68.6, 343.2, 205.9,
                    "700–3500 kgf/cm²，換算約 68.6–343.2 MPa；範圍很寬，應做敏感度分析。",
                    "https://www.nusc.gov.tw/share/file/fcma/S4j6ydizyqbQti9UaY3KmQ__.pdf"),
                "阿里山42號隧道｜邊坡設計 UCS 43.3 MPa": (43.3, 43.3, 43.3,
                    "阿里山森林鐵路42號隧道計畫表 3-2-1 邊坡設計參數；單一計畫設計輸入值，不是地層統計範圍。",
                    "https://www.forest.gov.tw/file/70068"),
                "阿里山42號隧道｜隧道 II 類設計 UCS 65.7 MPa": (65.7, 65.7, 65.7,
                    "阿里山森林鐵路42號隧道計畫表 3-2-1 隧道 II 類設計參數；單一計畫設計輸入值，不是地層統計範圍。",
                    "https://www.forest.gov.tw/file/70068"),
                "阿里山42號隧道｜隧道 III 類設計 UCS 43.3 MPa": (43.3, 43.3, 43.3,
                    "阿里山森林鐵路42號隧道計畫表 3-2-1 隧道 III 類設計參數；單一計畫設計輸入值，不是地層統計範圍。",
                    "https://www.forest.gov.tw/file/70068"),
                "阿里山42號隧道｜隧道 IV 類設計 UCS 21.4 MPa": (21.4, 21.4, 21.4,
                    "阿里山森林鐵路42號隧道計畫表 3-2-1 隧道 IV 類設計參數；單一計畫設計輸入值，不是地層統計範圍。",
                    "https://www.forest.gov.tw/file/70068")
            }
            # 2025 年《台灣中北部西部麓山帶沉積岩之力學特性》表 5：
            # 各項為表列單一試體 UCS，不應誤讀成地層統計上下限。
            _ucs_2025_source = "https://swcdis.nchu.edu.tw/AllDataPos/JournalPos/%E7%B7%A8%E8%99%9F61/%E7%AC%AC1%E6%9C%9F/%E5%8F%B0%E7%81%A3%E4%B8%AD%E5%8C%97%E9%83%A8%E8%A5%BF%E9%83%A8%E9%BA%93%E5%B1%B1%E5%B8%B6%E6%B2%89%E7%A9%8D%E5%B2%A9%E5%8A%9B%E5%AD%B8%E6%80%A7%E8%B3%AA.pdf"
            _ucs_2025_samples = [
                ("五指山層砂岩 Wc1｜北部・新北萬里萬瑞公路", "砂岩", 34.09, "萬瑞公路工址"),
                ("五指山層砂岩 Wc2｜北部・新北萬里萬瑞公路", "砂岩", 47.45, "萬瑞公路工址"),
                ("木山層砂岩 Ms1｜北部・新北中和圓通寺", "砂岩", 48.50, "中和圓通寺附近"),
                ("木山層砂岩 Ms2｜北部・台北北投", "砂岩", 37.13, "台北市北投地區"),
                ("木山層砂岩 Ms3｜北部・台北南港隧道", "砂岩", 82.69, "南港二號隧道工程"),
                ("木山層砂岩 Ms4｜北部・新北中和圓通寺", "砂岩", 32.83, "中和圓通寺附近"),
                ("大寮層砂岩 Tl1｜北部・新北石碇北宜公路", "砂岩", 68.70, "石碇北宜高速公路工地"),
                ("大寮層砂岩 Tl2｜北部・新北平溪平湖村", "砂岩", 77.46, "平溪鄉平湖村"),
                ("石底層砂岩 St｜北部・新北瑞芳四腳亭", "砂岩", 38.43, "瑞芳四腳亭附近"),
                ("南港層砂岩 Nk1｜北部・新竹關西", "砂岩", 100.50, "關西亞泥礦場"),
                ("南港層砂岩 Nk2｜北部・新北瑞芳深澳坑", "砂岩", 89.05, "瑞芳深澳坑"),
                ("南港層砂岩 Nk3｜北部・新北平溪新寮村", "砂岩", 85.95, "平溪新寮村"),
                ("東坑層砂岩 Te｜中北部・苗栗公館", "砂岩", 69.00, "公館南河村出磺坑背斜附近"),
                ("上福基砂岩 Sf1｜中北部・苗栗獅潭", "砂岩", 14.48, "獅潭鳳村出磺坑背斜東翼"),
                ("上福基砂岩 Sf2｜中北部・苗栗獅潭", "砂岩", 46.41, "獅潭鳳村出磺坑背斜東翼"),
                ("關刀山砂岩段 Kck1｜中部・苗栗獅潭／頭屋", "砂岩", 60.99, "獅潭與頭屋交界鳳鳴古道"),
                ("關刀山砂岩段 Kck2｜中部・苗栗造橋", "砂岩", 16.70, "苗栗造橋"),
                ("卓蘭層砂岩 Cl1｜中部・南投市", "砂岩", 19.86, "南投服務區工地"),
                ("卓蘭層砂岩 Cl2｜中部・地點未載明", "砂岩", 6.26, "原表未載明取樣地點"),
                ("卓蘭層砂岩 Cl5｜中部・地點未載明", "砂岩", 5.91, "原表未載明取樣地點"),
                ("卓蘭層砂岩 Cl9｜中部・台中石岡壩", "砂岩", 1.67, "石岡壩"),
                ("頭嵙山層砂岩 Tk1｜中部・南投集集", "砂岩", 28.50, "集集攔河堰"),
                ("頭嵙山層砂岩 Tk4｜中部・地點未載明", "砂岩", 28.40, "原表未載明取樣地點"),
                ("卓蘭層頁岩 Cl4｜中部・地點未載明", "頁岩", 2.65, "原表未載明取樣地點"),
                ("卓蘭層頁岩 Cl7｜中部・地點未載明", "頁岩", 2.46, "原表未載明取樣地點"),
                ("卓蘭層頁岩 Cl10｜中部・地點未載明", "頁岩", 4.30, "原表未載明取樣地點"),
                ("頭嵙山層頁岩 Tk2｜中部・地點未載明", "頁岩", 10.00, "原表未載明取樣地點"),
                ("頭嵙山層頁岩 Tk5｜中部・地點未載明", "頁岩", 10.50, "原表未載明取樣地點"),
                ("卓蘭層砂頁岩互層 Cl3｜中部・大安溪", "砂頁岩互層", 4.39, "大安溪"),
                ("卓蘭層砂頁岩互層 Cl6｜中部・大安溪", "砂頁岩互層", 4.69, "大安溪"),
                ("頭嵙山層砂頁岩互層 Tk3｜中部・地點未載明", "砂頁岩互層", 2.00, "原表未載明取樣地點"),
                ("頭嵙山層砂頁岩互層 Tk6｜中部・地點未載明", "砂頁岩互層", 1.95, "原表未載明取樣地點"),
            ]
            for _label, _lithology, _ucs_value, _location in _ucs_2025_samples:
                _ucs_case_data[_label] = (
                    _ucs_value, _ucs_value, _ucs_value,
                    f"表 5 彙整之單一試體 UCS={_ucs_value:.2f} MPa；{_location}。該文係彙整前人試驗資料，非作者於 2025 年新採樣；非地層統計範圍，使用前須核對試體風化、含水狀態與代表性。",
                    _ucs_2025_source,
                )

            # 2009 台電 SNFD2009 區域性彙整：以下是地質區概略範圍，不是單一工址或單一試體。
            _ucs_regional_source = "https://www.nusc.gov.tw/share/file/fcma/uVWo3J-onVl5yVBu0WiQNA__.pdf?v=2019121246"
            _ucs_case_data.update({
                "中央山脈東翼變質雜岩片岩／片麻岩｜東部山區區域範圍": (
                    24.5, 49.0, 36.75,
                    "250–500 kgf/cm²，換算約 24.5–49.0 MPa；區域性概略範圍，非工址試驗值。",
                    _ucs_regional_source),
                "中央山脈東翼大理岩｜東部山區區域範圍": (
                    24.5, 49.0, 36.75,
                    "250–500 kgf/cm²，換算約 24.5–49.0 MPa；區域性概略範圍，非工址試驗值。",
                    _ucs_regional_source),
                "西部麓山帶砂頁岩互層｜區域性概略範圍": (
                    4.9, 19.6, 12.25,
                    "50–200 kgf/cm²，換算約 4.9–19.6 MPa；區域性概略範圍。",
                    _ucs_regional_source),
                "古亭坑層泥岩｜西部麓山帶區域範圍": (
                    2.45, 4.90, 3.675,
                    "25–50 kgf/cm²，換算約 2.45–4.90 MPa；區域性概略範圍。",
                    _ucs_regional_source),
                "離島花崗岩｜台灣離島區域範圍": (
                    68.6, 166.7, 117.65,
                    "700–1700 kgf/cm²，換算約 68.6–166.7 MPa；區域性概略範圍。",
                    _ucs_regional_source),
            })

            # 台電 SNFD-AR2021 表 3-24：台灣本島東部結晶岩彙整統計。
            # 報告提醒鑽井分布有限，僅宜用於特定小範圍，不可泛化為整個東部山區。
            _ucs_east_source = "https://nbmi.taipower.com.tw/downloads/file_info/20240726111202.pdf"
            _ucs_case_data.update({
                "東部結晶岩花崗片麻岩｜台電 SNFD-AR2021 統計 n=84": (
                    28.9, 153.6, 103.3,
                    "單軸壓縮試驗 n=84；最小 28.9、最大 153.6、Q1 79.1、中位數 108.3、Q3 132.0、平均 103.3 MPa。資料彙整範圍有限，僅宜作相似小範圍工址參考。",
                    _ucs_east_source),
                "東部結晶岩大理岩｜台電 SNFD-AR2021 統計 n=29": (
                    19.1, 148.9, 105.7,
                    "單軸壓縮試驗 n=29；最小 19.1、最大 148.9、Q1 83.0、中位數 113.4、Q3 132.1、平均 105.7 MPa。資料彙整範圍有限，僅宜作相似小範圍工址參考。",
                    _ucs_east_source),
            })
            st.caption("地區適用性：2025 年論文方法段稱彙整 31 筆資料，但表 5 逐列可辨識 32 個試體編號；系統依表 5 原列逐筆登錄，並保留單一試體性質，不將其視為統計區間。案例涵蓋台灣北部與中部西部麓山帶；台電 SNFD-AR2021 表 3-24 另提供東部花崗片麻岩與大理岩統計（n=84／29），但報告提醒鑽井分布有限，僅宜作特定小範圍參考；2009 年區域彙整保留作概略對照。平原沖積層屬土壤，不適用完整岩石 UCS；海岸山脈亦缺少可直接套用的本批 UCS 數據，勿以其他地區案例代替。")
            _sandstone_cases = [k for k in _ucs_case_data if "砂岩" in k and "互層" not in k]
            _case_by_rock = {
                "砂岩 Sandstone": _sandstone_cases,
                "安山岩 Andesite": [k for k in _ucs_case_data if "安山岩" in k],
                "花崗岩 Granite": [k for k in _ucs_case_data if "花崗岩" in k],
                "片麻岩 Gneiss": [k for k in _ucs_case_data if "片麻岩" in k],
                "大理岩 Marble": [k for k in _ucs_case_data if "大理岩" in k],
                "砂岩 Sandstone（台灣南莊層三軸案例）": [k for k in _ucs_case_data if "南莊層砂岩｜隧道" in k],
                "砂岩 Sandstone（東北部宜蘭線瑞芳段崩塌案例）": [k for k in _ucs_case_data if "東北部宜蘭線瑞芳段風化砂岩" in k],
                "片岩 Schist（蘇花公路案例）": [k for k in _ucs_case_data if "片岩／片麻岩" in k],
                "砂岩／頁岩互層（阿里山森林鐵路42號隧道案例）": [
                    "阿里山42號隧道｜邊坡設計 UCS 43.3 MPa",
                    "阿里山42號隧道｜隧道 II 類設計 UCS 65.7 MPa",
                    "阿里山42號隧道｜隧道 III 類設計 UCS 43.3 MPa",
                    "阿里山42號隧道｜隧道 IV 類設計 UCS 21.4 MPa",
                ],
                "頁岩 Shale": [k for k in _ucs_case_data if "頁岩" in k and "砂頁岩互層" not in k],
                "泥岩／黏土岩 Mudstone / Claystone": [k for k in _ucs_case_data if "泥岩" in k],
                "粉砂岩 Siltstone": [],
                "板岩 Slate": [],
                "片岩 Schist": [k for k in _ucs_case_data if "片岩／片麻岩" in k],
                "礫岩／角礫岩 Conglomerate / Breccia": [],
                "石灰岩 Limestone": [],
                "自訂輸入 mi": list(_ucs_case_data.keys())
            }
            if ucs_mode == "已有實驗室 UCS 試驗值":
                sig_ci = st.number_input("輸入試驗報告的 UCS [MPa]", min_value=0.1, max_value=1000.0,
                    value=25.0, step=1.0, key="hb_ucs_lab_value")
                lab_value_confirmed = st.checkbox("我已確認上方數值是試驗報告中的完整岩石 UCS", value=False,
                    key="hb_ucs_lab_confirmed")
                ucs_valid = bool(lab_value_confirmed)
                _ucs_range_low = _ucs_range_high = sig_ci
                _ucs_range_label = f"{sig_ci:g} MPa（試驗值）"
                if not ucs_valid:
                    st.warning("請先確認數值確實來自試驗報告；未確認前不會用於計算。")
                st.caption("輸入完整岩塊試體 UCS，不是岩體或節理面強度。")
            elif ucs_mode == "採用台灣岩性案例參考值":
                _available_ucs_cases = _case_by_rock.get(rock_preset, [])
                if not _available_ucs_cases:
                    sig_ci = 25.0
                    st.warning(f"目前選擇的岩性「{rock_preset}」沒有可直接對應的台灣 UCS 案例數值。請改選「依現場敲擊分級初估」，或輸入實驗室試驗值；系統不會拿其他岩性數值代替。")
                else:
                    _case_placeholder = "請選擇符合工址地層的案例"
                    _case_options = [_case_placeholder] + _available_ucs_cases
                    _case_key = f"hb_ucs_case_{rock_preset}"
                    _case_index = st.selectbox("選擇可參考的台灣岩性／試驗案例", _case_options,
                        index=0, key=_case_key)
                    if _case_index == _case_placeholder:
                        sig_ci = 25.0
                        st.warning("請依鑽探柱狀圖、岩性描述及風化程度選擇相符案例；未選定前不會將任意 UCS 值帶入計算。")
                    else:
                        ucs_case_selected_label = _case_index
                        _ucs_low, _ucs_high, _ucs_mid, _ucs_note, _ucs_source = _ucs_case_data[_case_index]
                        _ucs_range_low, _ucs_range_high = _ucs_low, _ucs_high
                        _ucs_range_label = f"{_ucs_low:g}–{_ucs_high:g} MPa" if _ucs_low != _ucs_high else f"{_ucs_low:g} MPa（單一案例）"
                        sig_ci = st.number_input("UCS 採用代表值 [MPa]（可直接調整）",
                            min_value=0.1, max_value=1000.0, value=float(_ucs_mid), step=0.5,
                            key=f"hb_ucs_case_value_{_case_index}")
                        ucs_valid = True
                        st.info(f"參考範圍：{_ucs_range_label}；採用值：{sig_ci:g} MPa。{_ucs_note}")
                        st.markdown(f"[查看案例／資料來源]({_ucs_source})")
                        if _ucs_low != _ucs_high:
                            st.caption("敏感度分析會使用來源區間上下限；上方代表值則用於目前這次計算。")
                        else:
                            st.caption("這是單一案例數值，沒有可供推定的統計區間；敏感度分析暫以此值計算。")
            else:
                isrm_grade = st.selectbox("依完整岩塊現場敲擊／刻劃反應選擇 ISRM 強度等級", [
                    "請選擇現場等級",
                    "R6 極強（>250 MPa）：地質鎚多次敲擊僅崩小片，敲擊有清脆聲",
                    "R5 非常強（100–250 MPa）：需多次地質鎚敲擊才可打破完整岩塊",
                    "R4 強（50–100 MPa）：手持岩塊以地質鎚單次敲擊可打破",
                    "R3 中等強（25–50 MPa）：地質鎬用力敲擊可壓入約 5 mm，刀僅能刮痕",
                    "R2 弱（5–25 MPa）：刀可切削，但材料仍難以製作標準試體",
                    "R1 非常弱（1–5 MPa）：地質鎬用力敲擊會碎裂，可用刀削形",
                    "R0 極弱（0.25–1 MPa）：指甲可壓出凹痕"
                ], key="hb_isrm_ucs_grade")
                isrm_ranges = {
                    "R6": (250.0, 300.0, 300.0), "R5": (100.0, 250.0, 175.0),
                    "R4": (50.0, 100.0, 75.0), "R3": (25.0, 50.0, 37.5),
                    "R2": (5.0, 25.0, 15.0), "R1": (1.0, 5.0, 3.0), "R0": (0.25, 1.0, 0.625)
                }
                if isrm_grade.startswith("R"):
                    _grade = isrm_grade[:2]
                    _ucs_low, _ucs_high, _ucs_mid = isrm_ranges[_grade]
                    if _grade == "R6":
                        _ucs_range_low = _ucs_range_high = _ucs_mid
                        _ucs_range_label = ">250 MPa（無有限上限；暫用 300 MPa 情境值）"
                    else:
                        _ucs_range_low, _ucs_range_high = _ucs_low, _ucs_high
                        _ucs_range_label = f"{_ucs_low:g}–{_ucs_high:g} MPa"
                    sig_ci = st.number_input("UCS 代表值 [MPa]（可直接調整）", min_value=0.1, max_value=1000.0,
                        value=float(_ucs_mid), step=1.0, key=f"hb_ucs_field_{_grade}")
                    ucs_valid = True
                    if _grade == "R6":
                        st.warning("R6 僅表示 UCS 大於 250 MPa，沒有有限上限；300 MPa 只是暫用情境值，不是區間中點。請優先安排試驗或敏感度分析。")
                    else:
                        st.info(f"ISRM 現場分級對應 UCS 約 {_ucs_low:g}–{_ucs_high:g} MPa；系統先以區間中點作初估，請勿當作試驗值。")
                else:
                    sig_ci = 25.0
                    st.warning("尚未選擇現場強度等級，因此暫不執行 Hoek–Brown 計算。")
            _case_pair_warning = _hb_case_pair_warning(rock_preset, ucs_case_selected_label, ucs_mode)
            if _case_pair_warning:
                st.warning(_case_pair_warning)
            st.caption(f"換算應力單位：$\\sigma_{{ci}} = {sig_ci * 1000.0:.0f}\\text{{ kPa}}$")
    
        with hb_col2:
            st.markdown("##### 2. 擾動因子與工程應用尺度")
            d_preset = st.selectbox("開挖/自然擾動程度參考 (D)", [
                "自然坡面（無近期開挖或爆破；仍須檢查長期卸荷）(D = 0.0)",
                "控制預裂／光面爆破，損傷較小 (D = 0.5)",
                "弱岩機械開挖且有明顯應力鬆弛損傷 (D = 0.7)",
                "未良好控制的生產爆破，近坡面嚴重損傷 (D = 1.0)",
                "自訂擾動因子 D"
            ])
            if "0.0" in d_preset: d_default = 0.0
            elif "0.5" in d_preset: d_default = 0.5
            elif "0.7" in d_preset: d_default = 0.7
            elif "1.0" in d_preset: d_default = 1.0
            else: d_default = 0.0
            d_range_low, d_range_high = d_default, d_default
            d_factor = d_default
            d_factor = st.slider("擾動因子 D（可直接調整）", min_value=0.0, max_value=1.0, value=d_default, step=0.05)
            d_range_low = d_range_high = d_factor
            st.caption("D 表示開挖／爆破損傷；天然節理破碎已由 GSI 反映。")
            _case_parameter_warning = _hb_case_parameter_warning(rock_preset, mi, gsi, d_factor)
            if _case_parameter_warning:
                st.warning(_case_parameter_warning)
            
            app_type = st.radio("選擇圍壓上限 (σ3_max) 決定方式：", [
                "邊坡穩定分析 (Slope Stability - 依邊坡高度 H)",
                "隧道/深基礎分析 (Tunnels - 依深度 H)",
                "一般淺層/自訂有效圍壓 (General σ3_max)"
            ])
            gamma_default = 23.0
            gamma_rock = st.number_input("岩體單位重 γ [kN/m³]", min_value=15.0, max_value=30.0, value=gamma_default, step=0.5, key="geolysis_gamma_general")
            h_slope = st.number_input("分析邊坡高度或覆蓋深度 H [m]", min_value=1.0, max_value=500.0,
                value=20.0, step=1.0, key="hb_analysis_height_m")
            _gsi_scale_warning = gsi_scale_effect_warning(
                application=("slope" if "邊坡" in app_type else ("tunnel" if "隧道" in app_type else "general")),
                height_m=h_slope,
            )
            if _gsi_scale_warning:
                st.warning(_gsi_scale_warning)
            sigma3_general = None
            if "一般淺層" in app_type:
                sigma3_general = st.number_input("自訂有效圍壓上限 σ3_max [MPa]", min_value=0.001, max_value=250.0, value=1.0, step=0.1, key="hb_sigma3_general")
                st.warning("一般淺層分析不再自動假設 σ3_max = UCS/4。請依分析深度、原位應力、破壞範圍或適用規範輸入代表圍壓。")
    
    
        # --- Hoek-Brown (2002) 核心運算 ---
        hb_application = "slope" if "邊坡" in app_type else ("tunnel" if "隧道" in app_type else "general")
        hb_current=None
        hb_error=None
        try:
            if not ucs_valid:
                raise ValueError("缺少 UCS 試驗值或有效的 ISRM 現場強度分級，請先補足資料。")
            if not gsi_selection_valid:
                raise ValueError("目前選取的岩體結構與不連續面品質組合不適用基本 GSI 圖，請重新選擇。")
            _hb_applicability = hoek_brown_structure_applicability(gsi=gsi, structure_code=_struct_code)
            if _hb_applicability["warning"]:
                st.warning(_hb_applicability["warning"])
            if not _hb_applicability["applicable"]:
                raise ValueError(_hb_applicability["warning"] or "目前 GSI 代表值超出 Hoek–Brown 適用範圍。")
            if gsi_lower > gsi_upper:
                raise ValueError("GSI 初判下限不可大於上限，請修正區間。")
            if _struct_code == "A" and gsi_upper > 75.0:
                st.warning("完整／巨塊狀岩體的 GSI>75 需另作脆性剝落評估；本次代表值若不超過 75，仍可進行 Hoek–Brown 初估，但敏感度分析會排除大於 75 的端點。")
            hb_current = hoek_brown_parameters(gsi=gsi,mi=mi,sigma_ci_mpa=sig_ci,disturbance=d_factor,
                application=hb_application,gamma_rock_kn_m3=gamma_rock,height_m=h_slope,
                sigma3_custom_mpa=sigma3_general)
        except Exception as exc:
            logging.exception("Unhandled application calculation error")
            hb_error=str(exc)
            st.error(f"Hoek–Brown 參數計算未完成：{hb_error}。請檢查 GSI、UCS、擾動因子與 σ3,max 適用範圍。")
        if hb_current is not None:
            mb=hb_current['mb']; s_hb=hb_current['s']; a_hb=hb_current['a']
            sig_cm=hb_current['sigma_cm_mpa']; sig_c_mass=hb_current['sigma_c_mass_mpa']; sig_t_mass=hb_current['sigma_t_mass_mpa']
            sig3_max=hb_current['sigma3_max_mpa']; sig3n=hb_current['sigma3n']
            phi_hb_deg=hb_current['phi_equiv_deg']; sin_phi=math.sin(math.radians(phi_hb_deg)); c_hb_mpa=hb_current['c_equiv_mpa']
            c_hb_kpa=hb_current['c_equiv_kpa']; em_gpa=hb_current['Em_gpa']
        else:
            mb=s_hb=a_hb=sig_cm=sig_c_mass=sig_t_mass=sig3_max=sig3n=phi_hb_deg=sin_phi=c_hb_mpa=c_hb_kpa=em_gpa=0.0

        # Explicit, current cross-module handoff.  Module 5 must not depend on
        # local variables from this renderer or silently reuse stale values.
        st.session_state["geolysis_hb_current"] = hb_current
        st.session_state["geolysis_hb_metadata"] = {
            "gsi": float(gsi),
            "mi": float(mi),
            "sigma_ci_mpa": float(sig_ci),
            "disturbance": float(d_factor),
            "sigma3_max_mpa": float(sig3_max),
            "application": str(hb_application),
            "structure_code": str(_struct_code),
        }
    
        with hb_col3:
            st.markdown("##### 3. 等效莫耳－庫倫與岩體參數成果")
            if hb_current is None:
                st.warning("目前輸入條件超出 Hoek–Brown 參數計算範圍，因此不提供 c′、ϕ′、Em 或破壞包絡線；請先修正輸入。")
            else:
                st.success(rf"""#### 等效凝聚力 $c'$：`{c_hb_kpa:.1f} kPa` ({c_hb_mpa:.3f} MPa)
    #### 等效內摩擦角 $\phi'$：`{phi_hb_deg:.2f}°`""")
                st.metric("岩體變形模數 $E_m$", f"{em_gpa:.2f} GPa ({em_gpa*1000:.0f} MPa)")
                st.metric(r"岩體整體抗壓強度 $\sigma_{cm}$", f"{sig_cm:.2f} MPa ({sig_cm*1000:.0f} kPa)")
                st.metric(r"岩體抗拉強度 $\sigma_t$", f"{sig_t_mass:.3f} MPa（負值代表拉應力）")
                st.caption(rf"**Hoek-Brown 準則常數**：$m_b = {mb:.3f}$ ｜ $s = {s_hb:.5f}$ ｜ $a = {a_hb:.3f}$ ｜ $\sigma_{{3,max}}={sig3_max:.3f}$ MPa")
                if gsi_method == "定性圖表初判":
                    st.caption(f"現場判讀選項：{gsi_struct.split(':')[0]} × {gsi_cond.split(':')[0]}。")
                elif gsi_quant_result is not None:
                    st.caption(f"定量依據：RQD={gsi_quant_result['RQD_percent']:.1f}%、JCond₈₉={gsi_quant_result['JCond89']}、GSI={gsi_quant_result['GSI']:.1f}。")
                if gsi_lower <= gsi_upper:
                    try:
                        _gsi_values = _gsi_sensitivity_values(_struct_code, gsi_lower, gsi_upper)
                        if not _gsi_values:
                            raise ValueError("完整／巨塊狀岩體的 GSI 敏感度區間全部高於 75；請重新檢視 GSI 判讀，不計算超出適用範圍的端點。")
                        _mi_values = sorted(set([mi_low, mi_high]))
                        _ucs_values = sorted(set([_ucs_range_low if _ucs_range_low is not None else sig_ci,
                                                   _ucs_range_high if _ucs_range_high is not None else sig_ci]))
                        _d_values = sorted(set([d_range_low, d_range_high]))
                        _sens_rows = []
                        for _gv in _gsi_values:
                            for _mv in _mi_values:
                                for _uv in _ucs_values:
                                    for _dv in _d_values:
                                        _sens_rows.append(hoek_brown_parameters(
                                            gsi=_gv, mi=_mv, sigma_ci_mpa=_uv, disturbance=_dv,
                                            application=hb_application, gamma_rock_kn_m3=gamma_rock,
                                            height_m=h_slope, sigma3_custom_mpa=sigma3_general))
                        st.caption(
                            f"參數範圍敏感度（GSI、mi、UCS、D 同時變動；γ、H 固定）："
                            f"c′ = {min(x['c_equiv_kpa'] for x in _sens_rows):.1f}–{max(x['c_equiv_kpa'] for x in _sens_rows):.1f} kPa；"
                            f"ϕ′ = {min(x['phi_equiv_deg'] for x in _sens_rows):.1f}–{max(x['phi_equiv_deg'] for x in _sens_rows):.1f}°；"
                            f"Em = {min(x['Em_gpa'] for x in _sens_rows):.2f}–{max(x['Em_gpa'] for x in _sens_rows):.2f} GPa。")
                        st.caption(
                            f"本次採用區間：GSI 初判 {gsi_lower}–{gsi_upper}（HB 敏感度 {min(_gsi_values)}–{max(_gsi_values)}）；mi {mi_low:g}–{mi_high:g}；"
                            f"UCS {_ucs_range_label or str(sig_ci) + ' MPa'}；"
                            f"D {d_range_low:g}–{d_range_high:g}。"
                            "此為參數端點組合的敏感度範圍，不代表統計信賴區間。")
                    except Exception as exc:
                        logging.exception("Unhandled application calculation error")
                        st.warning(f"參數區間敏感度計算未完成：{exc}；請檢查區間端點是否超出模型適用範圍。")
    
        with st.expander("📈 展開檢視：Hoek-Brown 非線性破壞包絡線 vs. 等效莫耳－庫倫直線圖", expanded=False):
            if hb_current is None:
                st.info("目前 Hoek–Brown 參數無效，無法繪製破壞包絡線。")
            else:
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
