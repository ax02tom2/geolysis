import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math
from io import StringIO
from geolysis_engine import classify_uscs_aashto, spt_correct, spt_profile, consolidation_time_rate, secondary_compression_settlement, immediate_elastic_settlement, excavation_rebound_recompression, differential_settlement, usace_meyerhof_settlement_allowable, burland_burbidge_2025_settlement, burland_burbidge_2025_allowable_pressure, burland_burbidge_average_n60_from_profile, consolidation_allowable_pressure, consolidation_allowable_pressure_layers, boussinesq_rectangular_center_factor, bearing_capacity, hoek_brown_parameters

st.set_page_config(page_title="geolysis 大地工程分析系統", page_icon="🧱", layout="wide")

# 展開區版面修正：避免 expander 內容因內層容器溢出設定而被裁切。
# 所有模組仍可獨立收合／展開；不改動計算欄位或分析流程。
st.markdown("""
<style>
/* Streamlit expander：內容高度依實際內容延伸，不限制在固定高度 */
div[data-testid="stExpander"],
div[data-testid="stExpander"] details,
div[data-testid="stExpander"] details > div,
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
}
/* 避免巢狀 expander 與欄位容器截斷圖表、說明或表單下緣 */
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] > div {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
    min-height: 0 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🧱 geolysis 大地工程分析系統")
st.caption("岩土工程參數初估與分析｜選擇模組後輸入必要資料即可計算。")

# ==============================================================================
# 側邊欄：保留模組快速選擇；預設全部收合
# ==============================================================================
st.sidebar.title("🛠️ 分析模組")
display_mode = st.sidebar.radio(
    "選擇要展開的模組：",
    [
        "全部收合",
        "全部展開",
        "模組一：Hoek-Brown 岩體參數",
        "模組二：土壤分類",
        "模組三：SPT 全修正",
        "模組四：容許承載力",
        "模組五：極限承載力"
    ],
    index=0,
    key="analysis_module_display_mode"
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
<div class="gsi-lit-zoom-hint">Somodi et al. (2021), Figure 1</div>
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
            "安山岩 Andesite", "花崗岩 Granite", "自訂輸入 mi"
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
            "花崗岩 Granite": (32, 29, 35, "Hoek：32 ± 3")
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
        _sandstone_cases = [k for k in _ucs_case_data if "砂岩" in k]
        _case_by_rock = {
            "砂岩 Sandstone": _sandstone_cases,
            "安山岩 Andesite": [k for k in _ucs_case_data if "安山岩" in k],
            "花崗岩 Granite": [k for k in _ucs_case_data if "花崗岩" in k],
            "頁岩 Shale": [],
            "泥岩／黏土岩 Mudstone / Claystone": [],
            "粉砂岩 Siltstone": [],
            "板岩 Slate": [],
            "片岩 Schist": [],
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
            value=20.0, step=1.0, key="geolysis_number_input_line_377")
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
        hb_error=str(exc)
        st.error(f"Hoek–Brown 參數計算未完成：{hb_error}。請檢查 GSI、UCS、擾動因子與 σ3,max 適用範圍。")
    if hb_current is not None:
        mb=hb_current['mb']; s_hb=hb_current['s']; a_hb=hb_current['a']
        sig_cm=hb_current['sigma_cm_mpa']; sig_c_mass=hb_current['sigma_c_mass_mpa']
        sig3_max=hb_current['sigma3_max_mpa']; sig3n=hb_current['sigma3n']
        phi_hb_deg=hb_current['phi_equiv_deg']; sin_phi=math.sin(math.radians(phi_hb_deg)); c_hb_mpa=hb_current['c_equiv_mpa']
        c_hb_kpa=hb_current['c_equiv_kpa']; em_gpa=hb_current['Em_gpa']
    else:
        mb=s_hb=a_hb=sig_cm=sig_c_mass=sig3_max=sig3n=phi_hb_deg=sin_phi=c_hb_mpa=c_hb_kpa=em_gpa=0.0

    with hb_col3:
        st.markdown("##### 3. 等效莫耳－庫倫與岩體參數成果")
        if hb_current is None:
            st.warning("目前輸入條件超出 Hoek–Brown 參數計算範圍，因此不提供 c′、ϕ′、Em 或破壞包絡線；請先修正輸入。")
        else:
            st.success(rf"""#### 等效凝聚力 $c'$：`{c_hb_kpa:.1f} kPa` ({c_hb_mpa:.3f} MPa)
#### 等效內摩擦角 $\phi'$：`{phi_hb_deg:.2f}°`""")
            st.metric("岩體變形模數 $E_m$", f"{em_gpa:.2f} GPa ({em_gpa*1000:.0f} MPa)")
            st.metric(r"岩體整體抗壓強度 $\sigma_{cm}$", f"{sig_cm:.2f} MPa ({sig_cm*1000:.0f} kPa)")
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


# ==============================================================================
# 模組二：土壤分類系統
# ==============================================================================
with st.expander("🌱 模組二：土壤分類系統 (USCS & AASHTO)", expanded=exp_2):
    st.subheader("🌱 土壤分類系統")
    st.caption("依 ASTM D2487 與 AASHTO M 145 判別邏輯進行工程初判。篩分析通過率必須符合 P4 ≥ P10 ≥ P40 ≥ P200；分類百分比以通過 3 in（75 mm）篩的土樣為基準。LL／PL 應採通過 #40（0.425 mm）篩的細料試驗值；若含卵石／漂石須另加描述。")
    peat=st.checkbox("泥炭／高度有機土（依現場外觀、纖維質與有機特徵辨識）",key="m2_peat")
    if peat:
        st.info("泥炭依現場辨識分類為 USCS PT、AASHTO A-8；此分類不需要篩分析、LL 或 PL。下列試驗欄位暫停使用。")
    a,b,c=st.columns(3)
    with a:
        p4=st.number_input("#4 篩通過率 P4 [%]",0.0,100.0,85.0,1.0,key="m2_p4",disabled=peat)
        p10=st.number_input("#10 篩通過率 P10 [%]",0.0,100.0,75.0,1.0,key="m2_p10",disabled=peat)
        p40=st.number_input("#40 篩通過率 P40 [%]",0.0,100.0,55.0,1.0,key="m2_p40",disabled=peat)
        p200=st.number_input("#200 篩通過率 P200 [%]",0.0,100.0,12.0,1.0,key="m2_p200",disabled=peat)
    with b:
        ll=st.number_input("液性限度 LL [%]",0.0,200.0,42.0,1.0,key="m2_ll",disabled=peat)
        np_flag=st.checkbox("NP（無塑性）",key="m2_np",disabled=peat)
        pl=None if np_flag or peat else st.number_input("塑性限度 PL [%]",0.0,200.0,22.0,1.0,key="m2_pl",disabled=peat)
        organic=st.checkbox("疑似有機土（需另行確認）",key="m2_org",disabled=peat)
        organic_test_done=st.checkbox("已完成烘乾前後 LL 比值試驗",value=False,disabled=(not organic or peat),key='m2_org_test_done')
        ll_od=st.number_input("烘乾後 LL [%]（有機土確認用）",0.0,200.0,25.0,1.0,key="m2_llod",disabled=(not organic or not organic_test_done or peat))
    with c:
        coarse_soil=(p200<50) and not peat
        use_grad=st.checkbox("輸入粒徑曲線 D10/D30/D60（僅粗粒土級配判定）",value=True,key="m2_use_grad",disabled=not coarse_soil)
        if use_grad and coarse_soil:
            d10=st.number_input("D10 [mm]",min_value=0.0001,value=0.15,format="%.4f",key="m2_d10")
            d30=st.number_input("D30 [mm]",min_value=0.0001,value=0.60,format="%.4f",key="m2_d30")
            d60=st.number_input("D60 [mm]",min_value=0.0001,value=1.80,format="%.4f",key="m2_d60")
        else:
            d10=d30=d60=None
        if not peat and p200>=50:
            st.caption("目前 P200 ≥ 50%，屬細粒土；USCS 細粒土分類不使用 Cu／Cc，故不要求 D10/D30/D60。")
    m2_input_signature=(float(p4),float(p10),float(p40),float(p200),float(ll),
        None if pl is None else float(pl),bool(np_flag),
        None if d10 is None else float(d10),None if d30 is None else float(d30),
        None if d60 is None else float(d60),bool(organic),
        bool(organic_test_done),float(ll_od),bool(peat))
    if st.button("執行土壤分類",key="m2_run"):
        st.session_state.pop('m2_result',None)
        st.session_state.pop('m2_result_signature',None)
        try:
            result=classify_uscs_aashto(p4=p4,p10=p10,p40=p40,p200=p200,ll=ll,pl=pl,np_flag=np_flag,
                d10=d10,d30=d30,d60=d60,organic=organic,ll_oven_dried=(ll_od if organic and organic_test_done else None),peat=peat)
            st.session_state['m2_result']=result
            st.session_state['m2_result_signature']=m2_input_signature
        except Exception as exc: st.error(f"資料檢核未通過：{exc}")
    result=st.session_state.get('m2_result')
    if result and st.session_state.get('m2_result_signature') != m2_input_signature:
        st.warning("土壤分類輸入已變更；目前顯示的舊結果不再對應現有試驗值。請重新按「執行土壤分類」更新。")
        result=None
    if result:
        r1,r2,r3=st.columns(3)
        r1.success(f"USCS：{result['USCS']}")
        r2.success(f"AASHTO：{result['AASHTO']}")
        r3.metric("群指數 GI",result['GI'])
        if result['peat']:
            st.caption("泥炭／高度有機土：PI、Cu、Cc 與篩分析比例不適用。")
        else:
            st.write(f"PI = {result['PI']:.1f}% ｜ Cu = {result['Cu'] if result['Cu'] is not None else '未計算'} ｜ Cc = {result['Cc'] if result['Cc'] is not None else '未計算'}")
            st.dataframe(pd.DataFrame([{'礫粒(%)':result['gravel_pct'],'砂粒(%)':result['sand_pct'],'細料(%)':result['fines_pct'],'A-line PI':result['A_line_PI']}]),hide_index=True,use_container_width=True)
        if result['organic_note']: st.warning(result['organic_note'])
        st.caption("USCS：LL<50 時 PI<4 或位於 A 線下判 ML；PI>7 且位於 A 線上判 CL；4–7 的 A 線上區為 CL-ML。細料 >12% 且屬 CL-ML 時，粗粒土採 GC-GM／SC-SM；5–12% 細料仍依 ASTM 規則採雙重符號。未輸入 D10/D30/D60 時，不會虛構 GW/GP 或 SW/SP。AASHTO 限值依 M 145 將小數試驗值先四捨五入至整數；GI 依 AASHTO M 145 計算並四捨五入至整數，負值歸零（不強制封頂 20）；A-2-6／A-2-7 僅採 PI 部分。")
        st.warning("分類結果仍須由完整粒徑曲線、液塑限試驗及有機土試驗確認；本工具不取代 ASTM/AASHTO 正式試驗與工程師判釋。")
    with st.expander("分類依據與文獻",expanded=False):
        st.markdown("- [ASTM D2487：Unified Soil Classification System](https://www.astm.org/d2487.html)\n- [AASHTO M 145：Classification of Soils and Soil-Aggregate Mixtures](https://store.transportation.org/)")


# ==============================================================================
# 模組三：SPT 標準貫入試驗全修正
# ==============================================================================
with st.expander("🔨 模組三：SPT 標準貫入試驗全修正", expanded=exp_3):
    st.subheader("🔨 SPT 標準貫入試驗全修正")
    st.caption("N60 = N × CE × CB × CS × CR；(N1)60 = CN × N60。N 值須為標準貫入試驗最後 300 mm 的擊數，拒錘／未貫入須另註記，不可當作一般 N 值。")
    a,b,c=st.columns(3)
    with a:
        n_measured=st.number_input("現場量測 N 值",0,200,18,1,key="m3_n")
        er=st.number_input("錘擊能量比 ETR／ER [%]（依 ASTM D4633 實測或設備紀錄）",20.0,150.0,60.0,1.0,key="m3_er")
        st.caption("尚無能量校正報告時，60% 僅作標準化暫定假設；請取得設備實測 ETR 後更新，不可視為現場實測值。")
        cb_label=st.selectbox("鑽孔直徑（CB）",["65–115 mm（1.00）","150 mm（1.05）","200 mm（1.15）"],index=0,key="m3_cb_label")
        cb={"65–115 mm（1.00）":1.00,"150 mm（1.05）":1.05,"200 mm（1.15）":1.15}[cb_label]
    with b:
        cs_label=st.selectbox("取樣器內襯修正 CS",["有內襯（1.00）","無內襯／一般（1.10）","無內襯／較高修正（1.20）","無內襯／最高修正（1.30）"],index=0,key="m3_cs_label")
        cs={"有內襯（1.00）":1.00,"無內襯／一般（1.10）":1.10,"無內襯／較高修正（1.20）":1.20,"無內襯／最高修正（1.30）":1.30}[cs_label]
        rod_len=st.number_input("鑽桿長度 [m]",0.5,60.0,8.0,0.5,key="m3_rod")
        st.caption("CR 依鑽桿長度自動採建議值；仍須依設備型式與採用規範核對。")
        if rod_len>30:
            st.warning("鑽桿長度超過 30 m；USACE EM 1110-1-1905（2025）表 4-6 的 CR 參考範圍為 10–30 m。本工具目前仍以 CR=1.00 延用計算，但此範圍屬表列範圍外推，請依實際設備與採用規範確認。")
    with c:
        sigma_v=st.number_input("有效覆土應力 σ'v [kPa]",1.0,2000.0,95.0,5.0,key="m3_sv")
        soil_behavior=st.selectbox("土層性質",["砂土／非凝聚性土壤","黏土／凝聚性土壤"],key="m3_soil_behavior")
        soil_behavior_code="cohesionless" if soil_behavior.startswith("砂土") else "cohesive"
        cn_method=st.selectbox("覆土壓力修正 CN",["Liao & Whitman","Seed & Idriss","Skempton","不修正"],key="m3_cnmethod",disabled=(soil_behavior_code=="cohesive"))
        cn_cap=st.number_input("CN 上限（USACE 2025：最高 2.0；Seed–Idriss 液化法自動不超過 1.7）",1.0,2.0,2.0,0.1,key="m3_cncap")
        dilatancy_allowed=(soil_behavior_code=="cohesionless" and cn_method!="不修正")
        dilatancy=st.checkbox("飽和細砂／粉土位於地下水位以下，且 (N1)60 > 15：套用膨脹修正",value=False,key="m3_dilatancy",disabled=(not dilatancy_allowed))
        if not dilatancy_allowed: dilatancy=False
    refusal_single=st.checkbox("本筆為拒錘／部分貫入（不套用一般 N 值修正）",value=False,key="m3_refusal")
    if n_measured>=50 and not refusal_single:
        st.warning("本筆 N 值 ≥50；請回查每 150 mm 擊數與實際貫入量，確認是否已達拒錘／部分貫入條件，不可只把高 N 值視為一般貫入結果。")
    if refusal_single:
        st.warning("拒錘或未達標準貫入深度不能直接當作一般 N 值計算 N60／(N1)60；請保留每段擊數與實際貫入量，另依試驗紀錄判讀。")
        st.session_state.pop("m3_current_n60",None)
        st.session_state.pop("m3_current_n160",None)
    else:
        try:
            current=spt_correct(n_measured,er,cb,cs,rod_len,sigma_v,cn_method,cn_cap,
                soil_behavior=soil_behavior_code,apply_dilatancy=dilatancy)
            r1,r2,r3=st.columns(3)
            r1.metric("N60",f"{current['N60']:.2f}")
            r2.metric("CN",f"{current['CN']:.3f}")
            r3.metric("(N1)60 最終值",f"{current['N1_60_final']:.2f}")
            if current['CN_cap_applied'] is not None:
                st.caption(f"本次 CN 實際上限 = {current['CN_cap_applied']:.2f}（Seed & Idriss 液化法自動限制不超過 1.7）。")
            else:
                st.caption("本筆未套用覆土修正（黏土／選擇不修正），CN 固定為 1.0。")
            st.dataframe(pd.DataFrame([{'修正係數':'CE','值':current['CE']},{'修正係數':'CB','值':current['CB']},{'修正係數':'CS','值':current['CS']},{'修正係數':'CR','值':current['CR']},{'修正係數':'CN','值':current['CN']}]),hide_index=True,use_container_width=True)
            st.session_state['m3_current_n60']=current['N60']
            st.session_state['m3_current_n160']=current['N1_60_final']
        except Exception as exc: st.error(f"SPT 修正失敗：{exc}")
    st.markdown("**鑽孔逐深度資料（CSV）**")
    st.caption("必要欄位：Depth_m、N、Effective_Stress_kPa；可選填 Rod_Length_m（該深度實際鑽桿長度）、Refusal（true/false）及 Penetration_mm。若提供 Rod_Length_m，逐列依實際鑽桿長度計算 CR；未提供才使用上方共用值。拒錘列會保留但不計算一般 N60。")
    csv_file=st.file_uploader("上傳逐深度 SPT CSV（UTF-8）",type=['csv'],key='m3_csv_upload')
    default_csv="Depth_m,N,Effective_Stress_kPa,Rod_Length_m\n5,12,50,6\n10,18,95,11\n15,25,140,16"
    csv_text=st.text_area("或貼上 CSV 內容",default_csv,height=100,key="m3_profile")
    try:
        prof=pd.read_csv(csv_file) if csv_file is not None else pd.read_csv(StringIO(csv_text))
        required={'Depth_m','N','Effective_Stress_kPa'}
        if required.issubset(prof.columns) and len(prof):
            if prof[list(required)].isnull().any().any() or (prof['Effective_Stress_kPa']<=0).any() or (prof['N']<0).any():
                raise ValueError('CSV 含空值、負 N 值或非正有效覆土應力')
            rows=prof.to_dict('records')
            corrected=spt_profile(rows,energy_ratio_pct=er,borehole_factor=cb,sampler_factor=cs,rod_length_m=rod_len,
                cn_method=cn_method,cn_cap=cn_cap,soil_behavior=soil_behavior_code,apply_dilatancy=dilatancy)
            out=pd.DataFrame(corrected)
            st.dataframe(out,use_container_width=True,hide_index=True)
            plot_out=out.dropna(subset=['N1_60_final'])
            if len(plot_out):
                fig=go.Figure(go.Scatter(x=plot_out['N1_60_final'],y=plot_out['Depth_m'],mode='lines+markers',name='(N1)60 最終值'))
                fig.update_yaxes(autorange='reversed',title='深度 [m]'); fig.update_xaxes(title='(N1)60 最終值')
                fig.update_layout(height=420,title='SPT 修正值深度剖面')
                st.plotly_chart(fig,use_container_width=True)
            if 'Refusal' in out.columns and out['N1_60_final'].isna().any():
                st.warning("表格中的拒錘／部分貫入列已排除一般 N 值修正與剖面連線；請依原始貫入紀錄個別判讀。")
            high_n=out['N']>=50
            refusal_mask=(out['Refusal'].astype(str).str.lower().isin(['true','1','1.0','yes','y','refusal','拒錘','部分貫入']) if 'Refusal' in out.columns else pd.Series(False,index=out.index))
            if (high_n & ~refusal_mask).any():
                st.warning("剖面仍有 N≥50 且未標記 Refusal 的測點；請逐筆核對拒錘／部分貫入紀錄，必要時補上 Refusal 欄位。")
            st.download_button('下載修正後 SPT CSV',out.to_csv(index=False).encode('utf-8-sig'),'SPT_corrected.csv','text/csv',key='m3_download')
            st.session_state['m3_profile_result']=out
        else: st.info('請提供 Depth_m、N、Effective_Stress_kPa 三欄；未提供完整欄位前不執行剖面計算。')
    except Exception as exc: st.error(f"逐深度資料檢核失敗：{exc}")
    st.caption("依 USACE EM 1110-1-1905（2025）：CN 僅建議用於非凝聚性土壤；黏土不作覆土修正，黏土類 CB 採 1.0。一般淺基礎設計可採 CN≤2.0；液化評估常見文獻上限 1.7，應依分析目的選擇。")
    st.info("飽和細砂／粉土的膨脹修正必須在覆土修正後進行，僅適用於地下水位以下且 (N1)60 > 15；粗砂不適用。")
    with st.expander("SPT 修正依據與文獻",expanded=False):
        st.markdown("- [USACE EM 1110-1-1905（2025）：Geotechnical Design of Shallow Foundations on Soils](https://publibrary.sec.usace.army.mil/api/download?filename=EM+1110-1-1905_Geotechincal+Design+of+Shallow+Foundations+on+Soils_2025+07+22+-+Final.pdf&id=54658636-77d2-48df-f26b-5295a01899a7&preview=true)\n- [ASTM D1586：Standard Penetration Test (SPT)](https://www.astm.org/d1586_d1586m.html)\n- [Youd et al. (2001)：NCEER SPT 液化評估修正建議](https://doi.org/10.1061/(ASCE)1090-0241(2001)127:10(817))")


# ==============================================================================
# 模組四：容許承載力與沉陷控制
# ==============================================================================
with st.expander("📏 模組四：容許承載力與沉陷控制", expanded=exp_4):
    st.subheader("📏 模組四：容許承載力與沉陷控制")
    method4=st.selectbox("分析方法",["砂土／礫土：Burland–Burbidge SPT 法（USACE 2025）","砂土：Meyerhof SPT 舊版經驗式（USACE 1992）","黏土：一維主固結沉陷控制法"],key='m4_method')
    if method4.startswith('砂土／礫土'):
        st.caption("依 USACE EM 1110-1-1905（2025）第 7-13 節，採 Burland & Burbidge SPT 法；輸入值應是基礎底至影響深度內的平均 N60，不是 (N1)60。")
        a,b,c=st.columns(3)
        with a:
            n4=st.number_input("影響深度內平均 N60",1.0,100.0,20.0,1.0,key='m4_bb_n60')
            width4=st.number_input("基礎短邊 B [m]",0.3,30.0,2.0,0.1,key='m4_bb_b')
            length4=st.number_input("基礎長邊 L [m]",0.3,100.0,3.0,0.1,key='m4_bb_l')
        with b:
            q4=st.number_input("目前基礎底總接觸壓力 q [kPa]",1.0,5000.0,150.0,5.0,key='m4_bb_q')
            target_bb4=st.number_input("容許總沉陷量 [mm]",1.0,200.0,25.0,1.0,key='m4_bb_target')
            qcap4=st.number_input("模組五 qa,gross（總容許承載力）上限 [kPa]（0＝不套用）",0.0,20000.0,0.0,10.0,key='m4_bb_qcap')
            sig04=st.number_input("影響深度內平均初始有效應力 [kPa]",0.0,3000.0,100.0,5.0,key='m4_bb_sig0')
            sigp4=st.number_input("先期固結壓力 σ′p [kPa]（正常固結時採 σ′0）",1.0,5000.0,100.0,5.0,key='m4_bb_sigp')
        with c:
            hs4=st.number_input("基礎底下砂／礫層厚度 Hs [m]",0.1,100.0,10.0,0.5,key='m4_bb_hs')
            years4=st.number_input("載重作用時間 [年]",0.1,100.0,30.0,0.5,key='m4_bb_years')
            loadtype4=st.selectbox("載重型態",["static","fluctuating"],format_func=lambda x:"靜態" if x=="static" else "反覆／波動",key='m4_bb_load')
        profile_text4=st.text_area("選填：逐深度 N60 CSV（深度自基礎底向下；欄位 Depth_below_base_m、N60）",value="",height=90,key='m4_bb_profile',placeholder="Depth_below_base_m,N60\n0.5,18\n1.0,20\n1.5,22")
        d,e=st.columns(2)
        with d:
            oc4=st.checkbox("超固結顆粒土（使用 σ′p 分段式）",key='m4_bb_oc')
            gravel4=st.checkbox("礫土／砂礫土（逐點 N60 × 1.25）",key='m4_bb_gravel')
        with e:
            fine_sat4=st.checkbox("地下水位以下飽和細砂／粉土（逐點 N60 > 15 套用膨脹修正）",key='m4_bb_finesat')
            ndecrease4=st.checkbox("N60 隨深度持續下降（影響深度改採 min(2B, 鬆弱層厚度)）",key='m4_bb_decrease')
        try:
            n60_used4=n4
            if profile_text4.strip():
                prof_bb=pd.read_csv(StringIO(profile_text4))
                avg_bb=burland_burbidge_average_n60_from_profile(prof_bb.to_dict('records'),
                    width_m=width4,granular_layer_thickness_m=hs4,n_decreases_with_depth=ndecrease4,
                    gravel_adjustment=gravel4,fine_sand_saturated=fine_sat4)
                n60_used4=avg_bb['N60_average']
                st.caption(f"依 Zi={avg_bb['influence_depth_m']:.2f} m 篩選 {avg_bb['selected_count']} 筆測點；{avg_bb['adjustments']}，平均 N60={n60_used4:.2f}。")
                st.dataframe(pd.DataFrame(avg_bb['selected_profile'],columns=['基礎底下深度 z [m]','原始 N60','逐點修正後 N60']),hide_index=True,use_container_width=True)
            elif gravel4 or fine_sat4:
                st.warning("目前以單一平均 N60 輸入；粒料修正將套用於平均值作近似。正式計算應先逐筆修正影響深度內的 N60，再計算算術平均；可貼上剖面 CSV 以自動處理。")
            bb_args=dict(n60_average=n60_used4,width_m=width4,length_m=length4,
                initial_effective_stress_kpa=sig04,preconsolidation_stress_kpa=sigp4,
                granular_layer_thickness_m=hs4,years=years4,load_type=loadtype4,
                overconsolidated=oc4,gravel_adjustment=(gravel4 if not profile_text4.strip() else False),
                fine_sand_saturated=(fine_sat4 if not profile_text4.strip() else False),
                n_decreases_with_depth=ndecrease4)
            q4_used=min(q4,qcap4) if qcap4>0 else q4
            max_q4=min(5000.0,qcap4) if qcap4>0 else 5000.0
            if qcap4>0 and q4>qcap4:
                st.warning(f"目前輸入 q={q4:.1f} kPa 高於模組五 qa,gross={qcap4:.1f} kPa；沉陷估算改以後者計算。")
            r=burland_burbidge_2025_settlement(gross_pressure_kpa=q4_used,**bb_args)
            qa_bb=burland_burbidge_2025_allowable_pressure(target_settlement_mm=target_bb4,max_pressure_kpa=max_q4,**bb_args)
            st.metric("沉陷＋承載力控制容許總接觸壓力",f"{qa_bb['qa_settlement_gross_kpa']:.1f} kPa")
            st.write(f"目前 q 採用值 = {q4_used:.1f} kPa 時，估算沉陷 = {r['settlement_mm']:.1f} mm ｜ 容許沉陷 = {target_bb4:.1f} mm")
            st.write(f"影響深度 Zi = {r['influence_depth_m']:.2f} m ｜ N60 採用值 = {r['N60_average_used']:.2f} ｜ Ic = {r['Ic_tsf_inv']:.5f} tsf⁻¹")
            st.write(f"形狀係數 C1 = {r['C1_shape']:.3f} ｜ 層厚係數 C2 = {r['C2_layer']:.3f} ｜ 時間係數 C3 = {r['C3_time']:.3f} ｜ {r['regime']}")
            st.caption(r['method'])
            st.warning(r['limitations'])
            if qa_bb['pressure_search_limit_reached'] and qcap4>0 and qcap4<=5000:
                st.caption("容許壓力受模組五輸入的 qa,gross 上限控制；在該上限內，預估沉陷仍未超過目標值。")
            elif qa_bb['pressure_search_limit_reached']:
                st.warning("5,000 kPa 搜尋上限內仍未達容許沉陷量，結果受搜尋上限控制，請檢查輸入。")
            if qa_bb['no_feasible_pressure']: st.error("即使不增加基礎接觸壓力，公式中的初始應力沉陷項仍已超過容許沉陷量；目前沒有可行的正接觸壓力解，請檢查 σ′0、N60、目標沉陷與方法適用性。")
            st.info("本結果已可選擇套用模組五 qa,gross 作承載力上限；若未輸入該值，結果僅受沉陷控制。請確認模組五使用相同基礎尺寸、埋深、地下水與地層條件。")
        except Exception as exc: st.error(f"Burland–Burbidge 沉陷估算失敗：{exc}")
    elif method4.startswith('砂土：'):
        st.caption("舊版 USACE EM 1110-1-1905（1992）Meyerhof SPT 經驗式；已由 2025 版手冊取代，僅保留作歷史方法比較，不作預設設計方法。")
        a,b,c=st.columns(3)
        with a:
            n4=st.number_input("基礎影響範圍代表 N60",min_value=1.0,max_value=100.0,value=float(max(1,round(st.session_state.get('m3_current_n60',18.0),1))),step=1.0,key='m4_n60')
            width4=st.number_input("基礎寬度 B [m]",0.3,30.0,2.5,0.1,key='m4_b')
        with b:
            depth4=st.number_input("基礎埋深 Df [m]",0.0,30.0,1.5,0.1,key='m4_df')
            settle4=st.number_input("容許總沉陷量 [mm]",5.0,100.0,25.0,5.0,key='m4_settle')
        with c:
            energy4=st.selectbox("N 值能量基準",[55,70],index=1,key='m4_energy')
            mat4=st.checkbox("筏基／Mat foundation",key='m4_mat')
        try:
            r=usace_meyerhof_settlement_allowable(n60=n4,width_m=width4,embedment_m=depth4,settlement_mm=settle4,energy_percent=energy4,mat=mat4)
            st.metric("沉陷控制容許承載壓力（初估）",f"{r['qa_settlement_kPa']:.1f} kPa")
            st.write(f"1 inch 沉陷基準：{r['qa_1in_kPa']:.1f} kPa ｜ 埋深係數 Kd = {r['Kd']:.3f} ｜ 寬度 = {r['width_ft']:.2f} ft")
            st.caption(r['method'])
            st.warning(r['limitations'])
        except Exception as exc: st.error(f"砂土容許承載力估算失敗：{exc}")
        st.info("此法是砂土 SPT 經驗法，不適用於黏土固結沉陷；採用時須確認 N 值代表基礎影響深度範圍，且不可重複作地下水修正。")
    else:
        st.caption("以 e–log σ′ 一維主固結理論計算；可選用 Boussinesq 矩形均布荷載中心點應力解，或 2:1 簡化法。亦可輸入多層 CSV，逐層計算後加總主固結沉陷。")
        stress_method_clay4=st.selectbox("垂直應力增量分布",["Boussinesq","2:1"],format_func=lambda x:"Boussinesq 矩形均布荷載（較建議）" if x=="Boussinesq" else "2:1 簡化法（初步估算）",key='m4c_stress_method')
        a,b,c=st.columns(3)
        with a:
            qB=st.number_input("基礎寬度 B [m]",0.3,50.0,2.0,0.1,key='m4c_b')
            qL=st.number_input("基礎長度 L [m]",0.3,100.0,3.0,0.1,key='m4c_l')
            zc=st.number_input("單一壓縮層中點距基礎底 z [m]",0.0,100.0,3.0,0.1,key='m4c_z')
        with b:
            Hc=st.number_input("單一壓縮層厚度 H [m]",0.1,100.0,5.0,0.1,key='m4c_h')
            sig0=st.number_input("初始有效垂直應力 σ′0 [kPa]",1.0,3000.0,100.0,5.0,key='m4c_sig0')
            sigp=st.number_input("先期固結壓力 σ′p [kPa]",1.0,5000.0,150.0,5.0,key='m4c_sigp')
        with c:
            e0=st.number_input("初始孔隙比 e0",0.1,3.0,0.8,0.05,key='m4c_e0')
            Cc=st.number_input("壓縮指數 Cc",0.001,2.0,0.30,0.01,key='m4c_cc')
            Cr=st.number_input("再壓縮指數 Cr",0.0,1.0,0.05,0.01,key='m4c_cr')
            target4=st.number_input("容許主固結沉陷 [mm]",1.0,200.0,25.0,1.0,key='m4c_target')
            qcap_clay4=st.number_input("模組五 qa,net 承載力上限 [kPa]（0＝不套用）",0.0,20000.0,0.0,10.0,key='m4c_qcap')
        layers_text4=st.text_area("選填：多層固結 CSV（填入後取代上方單一壓縮層參數）",value="",height=110,key='m4c_layers',placeholder="Layer,Depth_center_m,Thickness_m,e0,Cc,Cr,Sigma0_kPa,SigmaP_kPa\n1,1.5,3.0,0.8,0.30,0.05,60,100\n2,5.0,4.0,0.9,0.40,0.06,100,150")
        try:
            max_clay_q=min(5000.0,qcap_clay4) if qcap_clay4>0 else 5000.0
            if layers_text4.strip():
                layer_rows=pd.read_csv(StringIO(layers_text4)).to_dict('records')
                r=consolidation_allowable_pressure_layers(layers=layer_rows,footing_width_m=qB,
                    footing_length_m=qL,target_settlement_mm=target4,stress_method=stress_method_clay4,
                    max_pressure_kpa=max_clay_q)
                qa_clay_settlement=r['qa_primary_consolidation_kpa']
                st.dataframe(pd.DataFrame(r['layer_results']),hide_index=True,use_container_width=True)
                st.caption("分層表逐層列出應力影響係數、應力增量及主固結沉陷；總沉陷為各層沉陷量加總。")
            else:
                stress_ratio=((qB*qL)/((qB+zc)*(qL+zc)) if stress_method_clay4=='2:1'
                    else boussinesq_rectangular_center_factor(qB,qL,zc))
                r=consolidation_allowable_pressure(target_settlement_mm=target4,footing_pressure_factor=stress_ratio,
                    layer_thickness_m=Hc,initial_void_ratio=e0,compression_index=Cc,recompression_index=Cr,
                    initial_effective_stress_kpa=sig0,preconsolidation_stress_kpa=sigp,
                    max_pressure_kpa=max_clay_q,stress_method=stress_method_clay4)
                qa_clay_settlement=r['qa_primary_consolidation_kpa']
                st.write(f"應力影響係數 = {stress_ratio:.3f} ｜ 壓縮層中點應力增量 Δσ = {r['delta_sigma_mid_kpa']:.2f} kPa ｜ 預估主固結沉陷 = {r['settlement_mm']:.2f} mm")
                st.caption(f"固結狀態：{r['regime']}；最終有效應力 = {r['final_effective_stress_kpa']:.2f} kPa。")
            qa_clay_final=min(qa_clay_settlement,qcap_clay4) if qcap_clay4>0 else qa_clay_settlement
            st.metric("沉陷＋承載力控制容許接觸壓力（淨值）",f"{qa_clay_final:.1f} kPa")
            if r['search_limit_reached'] and qcap_clay4>0 and qcap_clay4<=5000:
                st.caption("最終淨容許壓力受模組五 qa,net 承載力上限控制。")
            elif r['search_limit_reached']:
                st.warning("5,000 kPa 搜尋上限內仍未達容許沉陷量，結果受搜尋上限控制，請檢查輸入。")
            st.info("若要套用模組五承載力限制，請輸入模組五的 qa,net；兩模組需使用相同基礎尺寸、埋深、地下水與地層條件。未輸入時僅為主固結沉陷控制值。")
            if stress_method_clay4=='2:1':
                st.warning("2:1 應力擴散法僅供初估；USACE 2025 指出其在方形基礎且 z<1.5B 時可能低估垂直應力。正式設計優先採 Boussinesq 彈性解或分層分析。")
            else:
                st.caption("Boussinesq 應力解假設均布矩形荷載作用於均質彈性半空間；仍需搭配正確分層參數與有效應力剖面。")

            with st.expander("主固結時間速率與次壓縮（選填）",expanded=False):
                st.caption("依 USACE 2025 第 7-18、7-19 節。Cv 應由固結試驗或現地試驗取得；此處以代表性壓縮層作一維估算。")
                rt_a,rt_b,rt_c=st.columns(3)
                with rt_a:
                    cv4=st.number_input("固結係數 Cv [m²/day]",min_value=0.000001,max_value=10.0,value=0.005,format="%.6f",key="m4c_cv")
                    drainage4=st.selectbox("排水條件",["double","single"],format_func=lambda x:"雙向排水（Hdr=H/2）" if x=="double" else "單向排水（Hdr=H）",key="m4c_drainage")
                with rt_b:
                    u_target4=st.number_input("目標平均固結度 U [%]",min_value=1.0,max_value=99.9,value=90.0,step=1.0,key="m4c_u")
                    elapsed_years4=st.number_input("載重後經過時間 [年]",min_value=0.0,max_value=100.0,value=1.0,step=0.5,key="m4c_elapsed")
                with rt_c:
                    calc_secondary4=st.checkbox("另估次壓縮沉陷",value=False,key="m4c_secondary")
                    ca4=st.number_input("次壓縮指數 Cα",min_value=0.0,max_value=0.5,value=0.01,step=0.001,format="%.4f",key="m4c_ca",disabled=not calc_secondary4)
                    ep4=st.number_input("主固結完成時孔隙比 ep",min_value=0.0,max_value=3.0,value=float(e0),step=0.05,key="m4c_ep",disabled=not calc_secondary4)
                try:
                    representative_H4=sum(float(x["Thickness_m"]) for x in layer_rows) if layers_text4.strip() else Hc
                    primary_total4=float(r["settlement_mm"])
                    time4=consolidation_time_rate(primary_settlement_mm=primary_total4,
                        layer_thickness_m=representative_H4,cv_m2_per_day=cv4,
                        target_degree_percent=u_target4,elapsed_days=elapsed_years4*365.25,
                        drainage=drainage4)
                    st.write(f"達到 U={u_target4:.1f}% 預估需時 **{time4['time_to_target_years']:.2f} 年**；目前 {elapsed_years4:.2f} 年時 U≈{time4['degree_at_elapsed_percent']:.1f}%，主固結沉陷≈{time4['primary_settlement_at_elapsed_mm']:.2f} mm。")
                    st.caption(f"排水距離 Hdr={time4['drainage_path_m']:.3f} m；Tv={time4['time_factor_target']:.4f}。")
                    if calc_secondary4:
                        t1_years4=st.number_input("次壓縮起算時間 t1 [年]（通常取主固結完成時間）",min_value=0.001,max_value=100.0,value=min(100.0,max(0.01,time4['time_to_target_years'])),step=0.1,key="m4c_t1")
                        t2_years4=st.number_input("次壓縮計算終止時間 t2 [年]",min_value=0.01,max_value=200.0,value=max(50.0,t1_years4+0.01),step=1.0,key="m4c_t2")
                        sec4=secondary_compression_settlement(layer_thickness_m=representative_H4,
                            secondary_compression_index=ca4,void_ratio_at_primary_end=ep4,
                            time_start_days=t1_years4*365.25,time_end_days=t2_years4*365.25)
                        st.write(f"次壓縮沉陷 δs ≈ **{sec4['secondary_settlement_mm']:.2f} mm**；代表層長期總沉陷（最終主固結＋次壓縮）≈ **{primary_total4+sec4['secondary_settlement_mm']:.2f} mm**。")
                    if layers_text4.strip():
                        st.warning("多層 CSV 的 Cv、排水距離及次壓縮參數目前以總厚度及單一代表 Cv 簡化估算；正式設計應逐層輸入各層 Cv、排水條件及 Cα，不可將此簡化值視為逐層精算。")
                except Exception as time_exc:
                    st.error(f"固結時間／次壓縮估算失敗：{time_exc}")


            with st.expander("黏土即時／彈性沉陷（選填）",expanded=False):
                st.caption("USACE 2025 指出飽和黏土即時沉陷通常相對主固結較小，常可忽略；若需估算，可用工作應變範圍的 Es 作簡化彈性半空間估算。")
                im_a,im_b,im_c=st.columns(3)
                with im_a:
                    q_im4=st.number_input("實際淨接觸壓力 qnet [kPa]",min_value=0.0,max_value=20000.0,value=float(min(20000.0,max(0.0,qa_clay_final))),step=5.0,key="m4c_q_im")
                    es_im4=st.number_input("土壤彈性模數 Es [MPa]",min_value=0.01,max_value=1000.0,value=10.0,step=0.5,key="m4c_es_im")
                with im_b:
                    nu_im4=st.number_input("蒲松比 ν",min_value=0.0,max_value=0.5,value=0.5,step=0.05,key="m4c_nu_im")
                    ip_im4=st.selectbox("沉陷影響係數 Ip（近似）",[
                        ("rigid_square",0.82,"方形剛性基礎"),
                        ("rigid_rectangle_2",1.20,"長方形剛性基礎 L/B≈2"),
                        ("rigid_strip",2.00,"條形剛性基礎"),
                        ("flexible_center_square",1.122,"方形柔性基礎中心")],
                        format_func=lambda x:x[2]+"（"+str(x[1])+"）",key="m4c_ip_im")
                with im_c:
                    st.warning("Es 預設 10 MPa 僅供示範運算，不是建議設計值。請以工作應變範圍的試驗或經場址校正的相關式取代；不可直接把 SPT N 值當成 Es。若無可靠 Es，請不要採用此即時沉陷數值。")
                try:
                    immediate4=immediate_elastic_settlement(net_pressure_kpa=q_im4,
                        footing_width_m=qB,soil_modulus_mpa=es_im4,
                        poisson_ratio=nu_im4,influence_factor=ip_im4[1])
                    st.metric("即時／彈性沉陷 δi",f"{immediate4['immediate_settlement_mm']:.2f} mm")
                    st.caption(immediate4['method']+"；"+immediate4['limitations'])
                except Exception as immediate_exc:
                    st.error(f"即時沉陷估算失敗：{immediate_exc}")
            with st.expander("開挖回彈與基礎再壓縮（選填）",expanded=False):
                st.caption("依 USACE 2025 第 7-15 節／表 7-10，以 Cr、Cc 理想化 e-log-p 路徑估算；σ′exc 與 σ′f 應由開挖及載重後有效應力分析取得。")
                re_a,re_b=st.columns(2)
                with re_a:
                    sigma_exc4=st.number_input("開挖／降水後有效應力 σ′exc [kPa]",min_value=0.1,max_value=5000.0,value=float(max(0.1,sig0*0.6)),step=5.0,key="m4c_sigma_exc")
                with re_b:
                    sigma_final4=st.number_input("基礎載重後最終有效應力 σ′f [kPa]",min_value=0.1,max_value=10000.0,value=float(max(0.1,sig0*1.2)),step=5.0,key="m4c_sigma_final")
                try:
                    rebound4=excavation_rebound_recompression(layer_thickness_m=Hc,
                        initial_void_ratio=e0,compression_index=Cc,recompression_index=Cr,
                        initial_effective_stress_kpa=sig0,preconsolidation_stress_kpa=sigp,
                        excavation_effective_stress_kpa=sigma_exc4,
                        final_effective_stress_kpa=sigma_final4)
                    st.write(f"開挖回彈（隆起）≈ **{abs(rebound4['rebound_mm']):.2f} mm**；基礎再壓縮沉陷≈ **{rebound4['recompression_settlement_mm']:.2f} mm**。")
                    st.metric("回彈後淨垂直位移（正值為沉陷）",f"{rebound4['net_settlement_mm']:.2f} mm")
                    st.caption(rebound4['regime']+"；"+rebound4['limitations'])
                    if layers_text4.strip():
                        st.warning("目前此回彈／再壓縮面板使用上方單層代表參數 H、e0、Cc、Cr；若地層為多層，需逐層輸入開挖後與載重後有效應力，不可直接代表整個多層剖面。")
                except Exception as rebound_exc:
                    st.error(f"開挖回彈／再壓縮估算失敗：{rebound_exc}")
            st.warning("此方法的主要成果為一維主固結沉陷；黏土即時沉陷通常相對較小，仍應依土層排水狀態與剛度判斷。時間速率、次壓縮及開挖回彈可於上方選填區估算。σ′0、σ′p、Cc、Cr、e0、Cv、Cα 應優先採代表性試驗資料。")
        except Exception as exc: st.error(f"黏土主固結估算失敗：{exc}")

    with st.expander("差異沉陷／角變量檢核（兩位置比較）",expanded=False):
        st.caption("將兩個位置各自計算得到的總沉陷量填入；本工具計算沉陷差與角變量，不擅自判定通過／不通過，容許值須依結構型式及適用規範選定。")
        da,db,ds=st.columns(3)
        with da: settle_a4=st.number_input("位置 A 總沉陷 [mm]",0.0,1000.0,20.0,1.0,key="m4_diff_a")
        with db: settle_b4=st.number_input("位置 B 總沉陷 [mm]",0.0,1000.0,10.0,1.0,key="m4_diff_b")
        with ds: spacing_diff4=st.number_input("兩位置距離 [m]",0.1,1000.0,5.0,0.1,key="m4_diff_spacing")
        try:
            diff4=differential_settlement(settlement_a_mm=settle_a4,
                settlement_b_mm=settle_b4,spacing_m=spacing_diff4)
            st.metric("差異沉陷量",f"{diff4['differential_settlement_mm']:.2f} mm")
            st.metric("角變量（Δs／L）",f"1/{(1/diff4['angular_distortion']):.0f}" if diff4['angular_distortion']>0 else "0")
            st.caption(f"角變量數值 = {diff4['angular_distortion']:.6f}；請依建築結構型式、跨距及設計規範判讀。")
        except Exception as diff_exc:
            st.error(f"差異沉陷檢核失敗：{diff_exc}")
    with st.expander("計算依據與文獻",expanded=False):
        st.markdown("- [USACE EM 1110-1-1905（2025）：第 6 章應力影響係數／Boussinesq／2:1，第 7-13 節 Burland–Burbidge SPT 沉陷法](https://publibrary.sec.usace.army.mil/api/download?filename=EM+1110-1-1905_Geotechincal+Design+of+Shallow+Foundations+on+Soils_2025+07+22+-+Final.pdf&id=54658636-77d2-48df-f26b-5295a01899a7&preview=true)\n- [Burland & Burbidge (1985)：Settlement of Foundations on Sand and Gravel](https://doi.org/10.1680/iicep.1985.1058)\n- [ASTM D2435/D2435M：一維固結試驗](https://www.astm.org/d2435_d2435m.html)\n- [USACE EM 1110-1-1905（1992）：舊版 Meyerhof SPT 公式](https://www.publications.usace.army.mil/Portals/76/Publications/EngineerManuals/EM_1110-1-1905.pdf)")


# ==============================================================================
# 模組五：極限承載力四大理論
# ==============================================================================
with st.expander("🏗️ 模組五：極限承載力四大理論", expanded=exp_5):
    st.subheader("🏗️ 模組五：極限承載力四大理論")
    st.caption("採 Terzaghi、Meyerhof、Hansen、Vesic 各自的經典承載力因子／係數架構；請先確認土層參數代表基礎破壞影響範圍。注意：USACE 2025 現行手冊另列 USACE（以 Meyerhof 為主）與 AASHTO/FHWA（以 Vesic 為主）兩套設計修正係數；若承載力控制設計，建議依該手冊分別計算並比較，不應將本頁任一單一理論宣稱為完整符合 2025 USACE 設計程序。")
    a,b,c,d=st.columns(4)
    with a:
        theory5=st.selectbox("理論",['Terzaghi','Meyerhof','Hansen','Vesic'],key='m5_theory')
        B5=st.number_input("基礎短邊 B [m]",0.2,50.0,2.0,0.1,key='m5_b')
        L5=st.number_input("基礎長邊 L [m]",0.2,100.0,3.0,0.1,key='m5_l')
    with b:
        src5=st.selectbox("參數來源",['手動輸入','模組一 Hoek-Brown 等效參數'],key='m5_src')
        use_hb5='模組一' in src5
        cdef=float(round(c_hb_kpa,1)) if use_hb5 and hb_current is not None else (0.0 if use_hb5 else 15.0)
        phidef=float(round(phi_hb_deg,1)) if use_hb5 and hb_current is not None else (0.0 if use_hb5 else 30.0)
        if use_hb5:
            st.session_state['m5_c']=cdef
            st.session_state['m5_phi']=min(50.0,phidef)
            st.session_state['_m5_src_prev']=src5
        elif st.session_state.get('_m5_src_prev') != src5:
            st.session_state['m5_c']=cdef
            st.session_state['m5_phi']=phidef
            st.session_state['_m5_src_prev']=src5
        c5=st.number_input("凝聚力 c [kPa]",0.0,100000.0,cdef,1.0,key='m5_c',disabled=use_hb5)
        phi5=st.number_input("內摩擦角 ϕ [°]",0.0,50.0,min(50.0,phidef),1.0,key='m5_phi',disabled=use_hb5)
        if use_hb5 and hb_current is None:
            st.error("模組一參數尚未成功計算，不能作為模組五輸入。")
        if use_hb5 and hb_current is not None:
            st.caption(f"模組一目前等效參數：c′={c_hb_kpa:.1f} kPa、ϕ′={phi_hb_deg:.2f}°；圍壓範圍 σ3,max={sig3_max:.3f} MPa。")
            if phi_hb_deg>50:
                st.error("模組一等效摩擦角超過本模組承載力公式目前支援的 50° 上限；系統不會把它截斷成 50° 後計算。請調整有工程依據的圍壓範圍，或改用試驗參數手動輸入。")
    with c:
        gamma5=st.number_input("地表至基礎底土層 γ [kN/m³]",10.0,30.0,18.5,0.5,key='m5_gamma')
        gsub5=st.number_input("基礎底以下有效單位重 γ' [kN/m³]",5.0,15.0,9.5,0.5,key='m5_gsub')
        df5=st.number_input("基礎埋深 Df [m]",0.0,30.0,1.5,0.1,key='m5_df')
    with d:
        dw5=st.number_input("地下水位深度 Dw [m]（自地表）",0.0,100.0,5.0,0.1,key='m5_dw')
        fs5=st.number_input("安全係數 FS",1.1,5.0,3.0,0.1,key='m5_fs')
        beta5=st.number_input("載重傾角 β [°]（Meyerhof 使用）",0.0,60.0,0.0,1.0,key='m5_beta',disabled=(theory5!='Meyerhof'))
    failure_mode5=st.selectbox("Terzaghi 剪力破壞模式",['general','local'],format_func=lambda x:'一般剪力破壞' if x=='general' else '局部剪力破壞（c、ϕ 折減）',disabled=(theory5!='Terzaghi'),key='m5_failure_mode')
    st.markdown("**載重分量（供 Hansen／Vesic 傾斜係數使用）**")
    hcol,vcol=st.columns(2)
    with hcol: H5=st.number_input("水平載重 H [kN]",0.0,1000000.0,0.0,10.0,key='m5_h')
    with vcol: V5=st.number_input("垂直載重 V [kN]",0.1,1000000.0,1000.0,10.0,key='m5_v')
    if theory5=='Terzaghi':
        st.session_state['m5_eL']=0.0
        st.session_state['m5_eB']=0.0
    excol,eycol=st.columns(2)
    with eycol: eB5=st.number_input("短邊方向偏心距 eB [m]",0.0,max(0.0,B5/2-0.001),0.0,0.01,key='m5_eB',disabled=(theory5=='Terzaghi'))
    eL_max5=max(0.0,min(L5/2-0.001,(L5-(B5-2*eB5))/2-0.001))
    eL_disabled5=(theory5=='Terzaghi' or eL_max5<0.001)
    with excol: eL5=st.number_input("長邊方向偏心距 eL [m]",0.0,max(0.001,eL_max5),0.0,0.01,key='m5_eL',disabled=eL_disabled5)
    if theory5=='Terzaghi': st.caption("Terzaghi 本頁不支援偏心荷載；切換至 Terzaghi 時偏心距會重設為 0。")
    load_dir5=st.selectbox("水平力方向（Vesic 公式）",['parallel_B','parallel_L'],format_func=lambda x:'平行短邊 B' if x=='parallel_B' else '平行長邊 L',disabled=(theory5!='Vesic'),key='m5_load_dir')
    adhesion5=st.number_input("基底黏著係數 ca/c（Hansen／Vesic）",0.0,1.0,0.6,0.1,key='m5_adhesion')
    hb_source_signature=(float(gsi),float(sig3_max),float(d_factor),float(sig_ci),float(mi)) if use_hb5 else ()
    m5_input_signature=(theory5,src5,float(c5),float(phi5),float(gamma5),float(gsub5),float(B5),float(L5),float(df5),float(dw5),float(fs5),float(beta5),float(H5),float(V5),float(eB5),float(eL5),failure_mode5,load_dir5,float(adhesion5),hb_source_signature)
    if st.button("計算極限承載力",key='m5_run'):
        st.session_state.pop('m5_result',None)
        st.session_state.pop('m5_result_signature',None)
        if use_hb5 and (hb_current is None or phi_hb_deg>50):
            st.error("模組一參數無效或等效 ϕ′ 超出 50°；已停止模組五計算，避免以無效／截斷值產生錯誤承載力。")
        else:
            try:
                if abs(math.degrees(math.atan2(H5,V5))-beta5)>2.0 and H5>0 and theory5=='Meyerhof':
                    st.warning("載重傾角 β 與 H/V 計算角度差異超過 2°；H/V 為 Hansen/Vesic 計算依據，請核對輸入。")
                result5=bearing_capacity(theory=theory5,c_kpa=c5,phi_deg=phi5,gamma_moist=gamma5,gamma_sub=gsub5,B=B5,L=L5,Df=df5,water_depth=dw5,fs=fs5,load_angle=(beta5 if theory5=='Meyerhof' else 0.0),horizontal_load=(H5 if theory5 in ('Hansen','Vesic') else 0.0),vertical_load=(V5 if theory5 in ('Hansen','Vesic') else None),failure_mode=(failure_mode5 if theory5=='Terzaghi' else 'general'),load_direction=load_dir5,adhesion_ratio=adhesion5,eccentricity_B=eB5,eccentricity_L=eL5)
                st.session_state['m5_result']=result5
                st.session_state['m5_result_signature']=m5_input_signature
            except Exception as exc: st.error(f"承載力計算失敗：{exc}")
    result5=st.session_state.get('m5_result')
    if result5 and st.session_state.get('m5_result_signature') != m5_input_signature:
        st.warning("模組五輸入參數已變更；目前顯示的舊結果不再對應現有輸入。請重新按「計算極限承載力」更新結果。")
        result5=None
    if result5:
        r1,r2,r3=st.columns(3)
        r1.metric("總極限承載力 qu",f"{result5['qu_gross']:.1f} kPa")
        r2.metric("淨容許承載力 qa,net",f"{result5['qa_net']:.1f} kPa")
        r3.metric("總容許承載力 qa,gross",f"{result5['qa_gross']:.1f} kPa")
        factors=pd.DataFrame([
            {'項目':'凝聚力項 cNc','承載力因子':result5['Nc'],'形狀係數':result5['sc'],'深度係數':result5['dc'],'傾斜係數':result5['ic'],'貢獻(kPa)':result5['term_c']},
            {'項目':'覆土項 qNq','承載力因子':result5['Nq'],'形狀係數':result5['sq'],'深度係數':result5['dq'],'傾斜係數':result5['iq'],'貢獻(kPa)':result5['term_q']},
            {'項目':'單位重項 0.5γBNγ','承載力因子':result5['Ngamma'],'形狀係數':result5['sg'],'深度係數':result5['dg'],'傾斜係數':result5['ig'],'貢獻(kPa)':result5['term_gamma']}])
        st.dataframe(factors,hide_index=True,use_container_width=True)
        st.write(f"有效尺寸 B′ × L′ = {result5['B_effective']:.2f} × {result5['L_effective']:.2f} m ｜ 基礎底有效覆土壓力 q = {result5['q_surcharge']:.2f} kPa ｜ Nγ 項有效單位重 γ' = {result5['gamma_effective']:.2f} kN/m³")
        st.caption(f"供模組四比較：總容許承載力 qa,gross = {result5['qa_gross']:.1f} kPa；淨容許承載力 qa,net = {result5['qa_net']:.1f} kPa。砂土／礫土模組四採總壓力，應使用 qa,gross；黏土主固結模組採淨壓力，應使用 qa,net。")
        if theory5=='Terzaghi': st.caption(f"Terzaghi {result5['failure_mode']}：採用 c = {result5['c_used']:.2f} kPa、ϕ = {result5['phi_used']:.2f}°；承載力因子依 USACE 表列值線性插值。")
        if '模組一' in src5:
            st.warning(f"本次使用模組一等效 Mohr–Coulomb 參數；其 c′、ϕ′係在 σ3,max={sig3_max:.3f} MPa 範圍內擬合，須確認與淺基礎破壞應力範圍相符。若不相符，請改用試驗參數或重新設定模組一圍壓範圍。")
        st.warning(result5['limitations'])
    st.caption("Hoek–Brown 岩體等效 c′、ϕ′僅應用於適當岩體尺度與破壞模式；不可不加判斷地當作一般土壤參數。SPT 推估 ϕ 亦僅為經驗參考，不取代三軸／直剪試驗。")
    with st.expander("理論公式與文獻來源",expanded=False):
        st.markdown("- [USACE EM 1110-1-1905（2025）：淺基礎承載力設計（現行手冊）](https://publibrary.sec.usace.army.mil/api/download?filename=EM+1110-1-1905_Geotechincal+Design+of+Shallow+Foundations+on+Soils_2025+07+22+-+Final.pdf&id=54658636-77d2-48df-f26b-5295a01899a7&preview=true)\n- [USACE EM 1110-1-1905（1992）：經典承載力因子表](https://www.publications.usace.army.mil/Portals/76/Publications/EngineerManuals/EM_1110-1-1905.pdf)\n- [FHWA GEC No. 6：Shallow Foundations](https://www.fhwa.dot.gov/engineering/geotech/pubs/010943.pdf)\n- [geolysis 開源套件公式文件](https://docs.geolysis.io/en/latest/formulas/ultimate-bearing-capacity/)")
