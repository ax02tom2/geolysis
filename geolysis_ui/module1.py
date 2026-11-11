"""Streamlit UI for engineering module 1."""
import streamlit as st
import logging
import math
import plotly.graph_objects as go
from geolysis_engine import hoek_brown_parameters


def render_module_1(expanded=False):
    # ==============================================================================
    # 模組一：Hoek-Brown (2002) 岩體裂隙推估等效 c', phi' (含 GSI 視覺化查表)
    # ==============================================================================
    with st.expander("⛰️ 模組一：Hoek–Brown 岩體參數分析", expanded):
        st.subheader("Hoek–Brown 岩體強度參數")
    
    
        # GSI 交叉判讀表：依 Hoek & Marinos (2000) 原始圖的結構／表面品質趨勢作初步區間估讀。
        # 數值是工程初判範圍，不是原圖提供的精確格點值；N/A 組合不強行產生 GSI。
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
            gsi_struct = st.selectbox("① 岩體結構／破碎型態", gsi_struct_options, index=1, key="gsi_structure_class")
            gsi_cond = st.selectbox("② 不連續面表面品質", gsi_cond_options, index=2, key="gsi_surface_class")
            _struct_code = gsi_struct[0]
            _cond_code = {"I":0,"II":1,"III":2,"IV":3,"V":4}.get(gsi_cond.split(".")[0], 2)
            _gsi_recommended = gsi_range_matrix[_struct_code][_cond_code]
            if _gsi_recommended is None:
                st.error("此組合不適用一般 GSI 判讀圖，請改採片理／剪切帶專用評估；系統不會自行編造數值。")
            else:
                _rec_lo, _rec_hi = _gsi_recommended
                _rec_mid = int(round((_rec_lo + _rec_hi) / 2))
                st.markdown("**依目前兩項選擇得到的 GSI 初判**")
                result_col1, result_col2 = st.columns(2)
                result_col1.metric("建議區間", f"{_rec_lo}–{_rec_hi}")
                result_col2.metric("建議代表值", str(_rec_mid))
                st.caption("此值依岩體結構與不連續面表面品質交叉判讀；下方計算欄位會以此代表值作為該組合的初始 GSI，可再人工修正。")
    
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
            with st.expander("案例來源與文獻", expanded=False):
                st.markdown("""
    - [北部侯硐案例與七類岩性參數研究（國立臺灣科技大學，2022）](https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi?search=s%3Did%3D%22110NTUS5512077%22.)
    - [國道 3 號汐止崩塌案例](https://doi.org/10.1016/j.sandf.2023.101316)
    - [北部南莊層隧道岩體參數案例](https://ws.thb.gov.tw/001/Upload/OldFile/resource/html/doc/%E5%87%BA%E7%89%88%E5%93%81-%E5%8F%B0%E7%81%A3%E5%85%AC%E8%B7%AF%E5%B7%A5%E7%A8%8B/%E7%AC%AC40%E5%8D%B7%E7%AC%AC1%E6%9C%9F.pdf)
    - [中部廬山板岩深層變形](https://doi.org/10.1016/j.enggeo.2019.105387)｜[梨山地滑案例](https://www.geotech.org.tw/purchase-inner.php?id=116)｜[明德水庫 2022 崩塌](https://doi.org/10.3390/w17243556)｜[中部岩坡地震反算研究](https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi?search=s%3Did%3D%22100NCU05503042%22.)
    - [南部燕巢泥岩崩塌](https://doi.org/10.1007/s10346-019-01250-3)｜[南部深層潛移邊坡研究](https://doi.org/10.1007/s10346-024-02453-z)｜[台灣大型深層山崩地形研究](https://doi.org/10.1016/j.geomorph.2012.11.004)
    - [東部蘇花公路 115.9k 案例](https://doi.org/10.29974/JCSWC.201306_44(2).0001)｜[安通混雜岩層崩塌](https://doi.org/10.3390/w12020480)
    - [Somodi et al. (2021), GSI Figure 1](https://doi.org/10.3390/app11083351)
                """)
    
        _struct_code = gsi_struct[0]
        _cond_code = {"I":0,"II":1,"III":2,"IV":3,"V":4}.get(gsi_cond.split(".")[0],2)
        _gsi_recommended = gsi_range_matrix[_struct_code][_cond_code]
        gsi_selection_valid = _gsi_recommended is not None
        if gsi_selection_valid:
            _rec_lo, _rec_hi = _gsi_recommended
            gsi_lower = int(st.session_state.get(f"gsi_lower_{_struct_code}_{_cond_code}", _rec_lo))
            gsi_upper = int(st.session_state.get(f"gsi_upper_{_struct_code}_{_cond_code}", _rec_hi))
            gsi_default = int(round((gsi_lower + gsi_upper) / 2)) if gsi_lower <= gsi_upper else int(round((_rec_lo + _rec_hi)/2))
        else:
            gsi_lower, gsi_upper, gsi_default = 0, 100, 50
    
    
        hb_col1, hb_col2, hb_col3 = st.columns(3)
        
        with hb_col1:
            st.markdown("##### 1. 岩塊強度與裂隙結構 (GSI & mi)")
            default_gsi_val = gsi_default if 'gsi_default' in locals() else 50
            gsi_key = f"gsi_representative_value_{_struct_code}_{_cond_code}"
            if gsi_key not in st.session_state:
                st.session_state[gsi_key] = int(default_gsi_val)
            gsi = st.number_input("GSI 代表值（可直接調整）", min_value=0, max_value=100, step=1, key=gsi_key)
            if 'gsi_lower' in locals() and 'gsi_upper' in locals() and gsi_lower <= gsi_upper and not (gsi_lower <= gsi <= gsi_upper):
                st.warning("目前 GSI 代表值超出人工判讀區間，請確認是否有意調整。")
            
            rock_preset = st.selectbox("選擇完整岩石的岩性（供 mi 初估）", [
                "砂岩 Sandstone", "頁岩 Shale", "泥岩／黏土岩 Mudstone / Claystone",
                "粉砂岩 Siltstone", "板岩 Slate", "片岩 Schist",
                "礫岩／角礫岩 Conglomerate / Breccia", "石灰岩 Limestone",
                "安山岩 Andesite", "花崗岩 Granite", "砂岩 Sandstone（台灣南莊層三軸案例）", "片岩 Schist（蘇花公路案例）", "自訂輸入 mi"
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
                "砂岩 Sandstone（台灣南莊層三軸案例）": (7.752, 7.752, 7.752, "台灣南莊層單一完整岩心案例三軸反算 mi=7.752；不是砂岩通用值。"),
                "片岩 Schist（蘇花公路案例）": (10, 10, 10, "蘇花公路工程報告採用 mi=10；屬工程分析採用值，不等同完整三軸試驗統計值。")
            }
            if rock_preset == "自訂輸入 mi":
                mi_low = mi_high = mi = st.number_input("完整岩石材料常數 mi（自訂）", min_value=1.0, max_value=50.0,
                    value=17.0, step=0.5, key="hb_mi_custom")
                st.caption("自訂 mi 應優先由完整岩石三軸試驗擬合取得；若無試驗，需註明採用的文獻依據。")
            else:
                mi_default, mi_low, mi_high, mi_source = mi_reference[rock_preset]
                mi = float(mi_default)
                mi = st.number_input("mi（可直接調整）", min_value=1.0, max_value=50.0, value=float(mi_default), step=0.5, key=f"hb_mi_{rock_preset}")
                st.caption(f"mi 初估：{mi_low}–{mi_high}；採用 {mi:g}。{mi_source}。")
    
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
    
            # 台灣案例／工程資料的完整岩石 UCS。kgf/cm² 以 0.0980665 換算為 MPa。
            # 區間是來源資料範圍，不代表特定工址；使用者仍須核對岩性、風化與含水狀態。
            _ucs_case_data = {
                "南莊層砂岩｜隧道完整岩心試驗單一案例": (5.022, 5.022, 5.022,
                    "完整岩心 UCS = 5.022 MPa；同一案例三軸反算 mi = 7.752。這是單一試體／案例，不是南莊層通用值。",
                    "https://www.thb.gov.tw/FileResource.axd?path=html%2Fdoc%2F%E5%87%BA%E7%89%88%E5%93%81-%E5%8F%B0%E7%81%A3%E5%85%AC%E8%B7%AF%E5%B7%A5%E7%A8%8B%2F%E7%AC%AC40%E5%8D%B7%E7%AC%AC1%E6%9C%9F.pdf"),
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
                    "https://www.nusc.gov.tw/share/file/fcma/S4j6ydizyqbQti9UaY3KmQ__.pdf")
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
                    f"表 5 單一試體 UCS={_ucs_value:.2f} MPa；{_location}。非地層統計範圍；使用前須核對試體風化、含水狀態與代表性。",
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

            st.caption("地區適用性：2025 年逐試體案例涵蓋台灣北部與中部西部麓山帶；2009 年區域彙整另提供東部中央山脈東翼變質岩與大理岩概略範圍。平原沖積層屬土壤，不適用完整岩石 UCS；海岸山脈亦缺少可直接套用的本批 UCS 數據，勿以其他地區案例代替。")
            _sandstone_cases = [k for k in _ucs_case_data if "砂岩" in k and "互層" not in k]
            _case_by_rock = {
                "砂岩 Sandstone": _sandstone_cases,
                "安山岩 Andesite": [k for k in _ucs_case_data if "安山岩" in k],
                "花崗岩 Granite": [k for k in _ucs_case_data if "花崗岩" in k],
                "砂岩 Sandstone（台灣南莊層三軸案例）": [k for k in _ucs_case_data if "南莊層砂岩｜隧道" in k],
                "片岩 Schist（蘇花公路案例）": [k for k in _ucs_case_data if "片岩／片麻岩" in k],
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
            
            app_type = st.radio("選擇圍壓上限 (σ3_max) 決定方式：", [
                "邊坡穩定分析 (Slope Stability - 依邊坡高度 H)",
                "隧道/深基礎分析 (Tunnels - 依深度 H)",
                "一般淺層/自訂有效圍壓 (General σ3_max)"
            ])
            gamma_default = 23.0
            gamma_rock = st.number_input("岩體單位重 γ [kN/m³]", min_value=15.0, max_value=30.0, value=gamma_default, step=0.5, key="geolysis_gamma_general")
            h_slope = st.number_input("分析邊坡高度或覆蓋深度 H [m]", min_value=1.0, max_value=500.0,
                value=20.0, step=1.0, key="hb_analysis_height_m")
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
            if gsi_lower > gsi_upper:
                raise ValueError("GSI 初判下限不可大於上限，請修正區間。")
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
                st.caption(f"現場判讀選項：{gsi_struct.split(':')[0]} × {gsi_cond.split(':')[0]}。")
                if gsi_lower <= gsi_upper:
                    try:
                        _gsi_values = sorted(set([gsi_lower, gsi_upper]))
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
                            f"本次採用區間：GSI {gsi_lower}–{gsi_upper}；mi {mi_low:g}–{mi_high:g}；"
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
