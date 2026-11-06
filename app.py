import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math
from io import StringIO
from geolysis_engine import classify_uscs_aashto, spt_correct, spt_profile, usace_meyerhof_settlement_allowable, burland_burbidge_2025_settlement, burland_burbidge_2025_allowable_pressure, burland_burbidge_average_n60_from_profile, consolidation_allowable_pressure, consolidation_allowable_pressure_layers, boussinesq_rectangular_center_factor, bearing_capacity, hoek_brown_parameters

st.set_page_config(page_title="geolysis 大地工程分析系統", page_icon="🧱", layout="wide")

st.title("🧱 geolysis 大地工程分析系統")
st.markdown(r"""
本系統結合 **Hoek-Brown (2002) 岩體裂隙參數推估** 與開源套件 **[geolysis](https://github.com/patrickboateng/geolysis)** 核心工程模組：
- **模組一：Hoek-Brown 岩體裂隙推估 ($c', \phi'$)** — 依據地質強度指標 (GSI，附文獻判讀圖、露頭照片及人工區間判讀)、岩性常數 ($m_i$)、單壓強度與邊坡深度，自動轉換等效莫耳－庫倫參數
- **模組二：土壤分類系統** — USCS 統一土壤分類法 & AASHTO 公路土壤分類法（含群指數 $GI$ 與雙重符號判定）
- **模組三：SPT 標準貫入試驗修正** — 能量、鑽孔直徑、取樣器、鑽桿與覆土壓力修正，含逐深度剖面
- **模組四：容許承載力與沉陷控制** — 砂土 SPT 經驗法及黏土一維主固結沉陷反算
- **模組五：極限承載力四大理論** — Terzaghi / Meyerhof / Hansen / Vesic 理論係數、形狀／深度／載重傾斜及地下水影響
""")

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

    with st.expander("🗺️ GSI 現場評估與文獻圖例", expanded=False):
        st.markdown("GSI 應由 **岩體結構／塊體互鎖程度** 與 **不連續面表面品質** 綜合判讀。先參考下列圖件與示意圖，再依現場觀察人工選定合理區間。")

        # 文獻圖縮小並排顯示，避免單張圖片佔滿整個頁面
        fig_col1, fig_col2 = st.columns(2, gap="medium")
        with fig_col1:
            st.markdown("**文獻圖 1｜節理岩體 GSI 判讀圖**")
            try:
                st.image("https://www.mdpi.com/applsci/applsci-11-03351/article_deploy/html/images/applsci-11-03351-g001.png",
                    caption="Somodi et al. (2021), Figure 1：一般節理岩體 GSI 判讀圖。",
                    use_container_width=True)
            except Exception:
                st.warning("GSI 判讀圖暫時無法載入；請參考下方文獻來源。")
        with fig_col2:
            st.markdown("**文獻圖 2｜現場露頭照片**")
            try:
                st.image("https://www.mdpi.com/applsci/applsci-11-03351/article_deploy/html/images/applsci-11-03351-g004.png",
                    caption="Somodi et al. (2021), Figure 4：不同岩性露頭及層理尺度各向異性案例。",
                    use_container_width=True)
            except Exception:
                st.warning("露頭照片暫時無法載入；請參考下方文獻來源。")

        st.markdown("**GSI 判讀概念示意圖｜結構完整度 × 節理面品質**")
        st.caption("此圖為系統自製的方向性示意，用來理解兩項判讀因子的相對影響；不是 Hoek 原始 GSI 圖，也不直接提供 GSI 數值。")
        gsi_demo = go.Figure(data=go.Heatmap(
            z=[[5,4,3,2,1],[4,4,3,2,1],[4,3,2,1,1],[3,2,2,1,0],[2,2,1,0,0],[2,1,1,0,0]],
            x=["極佳","良好","普通","不良","極差"],
            y=["A 巨塊狀／完整","B 塊狀","C 極塊狀","D 擾動／層狀","E 解體狀","F 層狀／剪切狀"],
            text=[["較高","較高","中高","中低","較低"],
                  ["較高","中高","中高","中低","較低"],
                  ["中高","中高","中等","較低","較低"],
                  ["中高","中等","中等","較低","低"],
                  ["中等","中等","較低","低","低"],
                  ["中等","較低","較低","低","低"]],
            texttemplate="%{text}", colorscale="RdYlGn", showscale=False,
            xgap=3, ygap=3, hovertemplate="節理面品質：%{x}<br>岩體結構：%{y}<br>相對判讀：%{text}<extra></extra>"))
        gsi_demo.update_layout(height=300, margin=dict(l=8,r=8,t=8,b=8),
            xaxis_title="不連續面表面品質（粗糙度、風化、填充物）",
            yaxis_title="岩體結構（破碎程度、塊體互鎖程度）",
            font=dict(size=11))
        st.plotly_chart(gsi_demo, use_container_width=True, config={"displayModeBar":False})

        st.info("一般節理岩體圖不適用於所有岩性；若為片岩、片理／層理極發達、千枚岩、褶皺或剪切帶岩體，應查用相應的 foliated／flysch GSI 圖或採各向異性／結構面分析。露頭照片僅供構造案例比對，不可直接由照片換算 GSI。")
        st.caption("補充案例：Medwedeff et al. (2022) Figure 3a 描述三組主要節理、間距約 10–30 cm、岩體中度風化，依 Figure 3b 判讀 GSI 約 50–65；此範圍僅適用該研究露頭，不可直接套用至其他岩性。")
        with st.expander("文獻來源與圖說", expanded=False):
            st.markdown("""- [Somodi et al. (2021), Figure 1 與 Figure 4，Applied Sciences 11(8), 3351](https://doi.org/10.3390/app11083351)（CC BY 4.0）
- [Medwedeff et al. (2022), Figure 3，Journal of Geophysical Research: Earth Surface, 127, e2021JF006240](https://doi.org/10.1029/2021JF006240)
- [Hoek：Practical Rock Engineering（GSI 判讀與限制）](https://static.rocscience.cloud/assets/resources/learning/hoek/Practical-Rock-Engineering-E.Hoek-2023.pdf)""")

        st.markdown("**1. 岩體結構**")
        gsi_struct = st.selectbox("選擇最接近的結構描述", gsi_struct_options,
            index=1, key="gsi_structure_class")
        st.markdown("**2. 不連續面表面品質**")
        gsi_cond = st.selectbox("選擇最接近的節理面狀況", gsi_cond_options,
            index=2, key="gsi_surface_class")
        st.caption("選擇完成後，系統會依兩項條件的交叉位置提供 GSI 建議範圍；請再依露頭、岩心、岩性及現地尺度確認。")
        st.caption("若存在不利方向且連續的弱面，可能屬結構控制破壞，不應只用等向性 Hoek–Brown 岩體參數取代結構面分析。")

        _struct_code = gsi_struct[0]
        _cond_code = {"I":0,"II":1,"III":2,"IV":3,"V":4}.get(gsi_cond.split(".")[0],2)
        _gsi_recommended = gsi_range_matrix[_struct_code][_cond_code]
        if _gsi_recommended is None:
            st.error("這組結構與表面品質在 Hoek–Marinos (2000) 基本 GSI 圖中屬不適用／不建議組合，系統不自動給值。請重新檢查現場分類，或改用適合片理、層狀、flysch 等岩體的專用 GSI 圖。")
            st.info("特別注意：巨塊狀岩體不應搭配極差節理面；層狀／剪切狀岩體也不應直接套用極佳或良好節理面條件。")
        else:
            _rec_lo, _rec_hi = _gsi_recommended
            st.success(f"**系統建議 GSI 範圍：{_rec_lo}–{_rec_hi}；建議代表值：{int(round((_rec_lo + _rec_hi)/2))}**")
            _gsi_edit1, _gsi_edit2 = st.columns(2)
            with _gsi_edit1:
                st.number_input("GSI 初判下限", min_value=0, max_value=100, value=_rec_lo, step=1,
                    key=f"gsi_lower_{_struct_code}_{_cond_code}")
            with _gsi_edit2:
                st.number_input("GSI 初判上限", min_value=0, max_value=100, value=_rec_hi, step=1,
                    key=f"gsi_upper_{_struct_code}_{_cond_code}")
            st.caption("建議值是依原始 GSI 圖趨勢估讀的初判區間，不是精確量測值；可依現地證據修改。Hoek 建議以合理範圍表達，不宜假裝 GSI 可精確到單一數字。")

        st.info("GSI 基本圖不適用於所有岩性；若為片岩、片理／層理極發達、千枚岩、褶皺或剪切帶岩體，應查用相應的 foliated／flysch GSI 圖或採各向異性／結構面分析。露頭照片僅供構造案例比對，不可直接由照片換算 GSI。")
        st.caption("補充案例：Medwedeff et al. (2022) Figure 3a 描述三組主要節理、間距約 10–30 cm、岩體中度風化，依 Figure 3b 判讀 GSI 約 50–65；此範圍僅適用該研究露頭，不可直接套用至其他岩性。")
        with st.expander("文獻來源與圖說", expanded=False):
            st.markdown("""- [Hoek：Practical Rock Engineering，Figure 6（Hoek & Marinos, 2000 GSI 基本圖）](https://static.rocscience.cloud/assets/resources/learning/hoek/Practical-Rock-Engineering-E.Hoek-2023.pdf)
- [Somodi et al. (2021), Figure 1 與 Figure 4，Applied Sciences 11(8), 3351](https://doi.org/10.3390/app11083351)（CC BY 4.0）
- [Medwedeff et al. (2022), Figure 3，Journal of Geophysical Research: Earth Surface, 127, e2021JF006240](https://doi.org/10.1029/2021JF006240)""")

    gsi_struct = st.session_state.get("gsi_structure_class", gsi_struct_options[1])
    gsi_cond = st.session_state.get("gsi_surface_class", gsi_cond_options[2])
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
        gsi = st.number_input("地質強度指標代表值 (GSI)", min_value=0, max_value=100, value=default_gsi_val, step=1, key=f"gsi_representative_value_{_struct_code}_{_cond_code}")
        if 'gsi_lower' in locals() and 'gsi_upper' in locals() and gsi_lower <= gsi_upper and not (gsi_lower <= gsi <= gsi_upper):
            st.warning("目前 GSI 代表值超出人工判讀區間，請確認是否有意調整。")
        
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
            "一般淺層/自訂有效圍壓 (General σ3_max)"
        ])
        gamma_rock = st.number_input("岩體單位重 γ [kN/m³]", min_value=15.0, max_value=30.0, value=23.0, step=0.5, key="geolysis_number_input_line_376")
        h_slope = st.number_input("分析邊坡高度或覆蓋深度 H [m]", min_value=1.0, max_value=500.0, value=20.0, step=1.0, key="geolysis_number_input_line_377")
        sigma3_general = None
        if "一般淺層" in app_type:
            sigma3_general = st.number_input("自訂有效圍壓上限 σ3_max [MPa]", min_value=0.001, max_value=250.0, value=1.0, step=0.1, key="hb_sigma3_general")
            st.warning("一般淺層分析不再自動假設 σ3_max = UCS/4。請依分析深度、原位應力、破壞範圍或適用規範輸入代表圍壓。")


    # --- Hoek-Brown (2002) 核心運算 ---
    hb_application = "slope" if "邊坡" in app_type else ("tunnel" if "隧道" in app_type else "general")
    hb_current=None
    hb_error=None
    try:
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
                    hb_lo=hoek_brown_parameters(gsi=gsi_lower,mi=mi,sigma_ci_mpa=sig_ci,disturbance=d_factor,
                        application=hb_application,gamma_rock_kn_m3=gamma_rock,height_m=h_slope,sigma3_custom_mpa=sigma3_general)
                    hb_hi=hoek_brown_parameters(gsi=gsi_upper,mi=mi,sigma_ci_mpa=sig_ci,disturbance=d_factor,
                        application=hb_application,gamma_rock_kn_m3=gamma_rock,height_m=h_slope,sigma3_custom_mpa=sigma3_general)
                    st.caption(f"GSI 區間敏感度（其餘參數固定）：c′ = {min(hb_lo['c_equiv_kpa'],hb_hi['c_equiv_kpa']):.1f}–{max(hb_lo['c_equiv_kpa'],hb_hi['c_equiv_kpa']):.1f} kPa；ϕ′ = {min(hb_lo['phi_equiv_deg'],hb_hi['phi_equiv_deg']):.1f}–{max(hb_lo['phi_equiv_deg'],hb_hi['phi_equiv_deg']):.1f}°；Em = {min(hb_lo['Em_gpa'],hb_hi['Em_gpa']):.2f}–{max(hb_lo['Em_gpa'],hb_hi['Em_gpa']):.2f} GPa。")
                except Exception as exc:
                    st.warning(f"GSI 區間敏感度計算未完成：{exc}")

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
    st.caption("依 ASTM D2487 與 AASHTO M 145 判別邏輯進行工程初判。篩分析通過率必須符合 P4 ≥ P10 ≥ P40 ≥ P200；分類百分比應以通過 3 in（75 mm）篩的土樣為基準，若含卵石／漂石須另加描述。")
    a,b,c=st.columns(3)
    with a:
        p4=st.number_input("#4 篩通過率 P4 [%]",0.0,100.0,85.0,1.0,key="m2_p4")
        p10=st.number_input("#10 篩通過率 P10 [%]",0.0,100.0,75.0,1.0,key="m2_p10")
        p40=st.number_input("#40 篩通過率 P40 [%]",0.0,100.0,55.0,1.0,key="m2_p40")
        p200=st.number_input("#200 篩通過率 P200 [%]",0.0,100.0,12.0,1.0,key="m2_p200")
    with b:
        ll=st.number_input("液性限度 LL [%]",0.0,200.0,42.0,1.0,key="m2_ll")
        np_flag=st.checkbox("NP（無塑性）",key="m2_np")
        pl= None if np_flag else st.number_input("塑性限度 PL [%]",0.0,200.0,22.0,1.0,key="m2_pl")
        organic=st.checkbox("疑似有機土（需另行確認）",key="m2_org")
        organic_test_done=st.checkbox("已完成烘乾前後 LL 比值試驗",value=False,disabled=not organic,key='m2_org_test_done')
        ll_od=st.number_input("烘乾後 LL [%]（有機土確認用）",0.0,200.0,25.0,1.0,key="m2_llod",disabled=(not organic or not organic_test_done))
    with c:
        use_grad=st.checkbox("輸入粒徑曲線 D10/D30/D60（粗粒土級配判定）",value=True,key="m2_use_grad")
        if use_grad:
            d10=st.number_input("D10 [mm]",min_value=0.0001,value=0.15,format="%.4f",key="m2_d10")
            d30=st.number_input("D30 [mm]",min_value=0.0001,value=0.60,format="%.4f",key="m2_d30")
            d60=st.number_input("D60 [mm]",min_value=0.0001,value=1.80,format="%.4f",key="m2_d60")
        else: d10=d30=d60=None
    if st.button("執行土壤分類",key="m2_run"):
        st.session_state.pop('m2_result',None)
        try:
            result=classify_uscs_aashto(p4=p4,p10=p10,p40=p40,p200=p200,ll=ll,pl=pl,np_flag=np_flag,
                d10=d10,d30=d30,d60=d60,organic=organic,ll_oven_dried=(ll_od if organic and organic_test_done else None),peat=peat)
            st.session_state['m2_result']=result
        except Exception as exc: st.error(f"資料檢核未通過：{exc}")
    result=st.session_state.get('m2_result')
    if result:
        r1,r2,r3=st.columns(3)
        r1.success(f"USCS：{result['USCS']}")
        r2.success(f"AASHTO：{result['AASHTO']}")
        r3.metric("群指數 GI",result['GI'])
        st.write(f"PI = {result['PI']:.1f}% ｜ Cu = {result['Cu'] if result['Cu'] is not None else '未計算'} ｜ Cc = {result['Cc'] if result['Cc'] is not None else '未計算'}")
        st.dataframe(pd.DataFrame([{'礫粒(%)':result['gravel_pct'],'砂粒(%)':result['sand_pct'],'細料(%)':result['fines_pct'],'A-line PI':result['A_line_PI']}]),hide_index=True,use_container_width=True)
        if result['organic_note']: st.warning(result['organic_note'])
        st.caption("USCS：LL<50 時 PI<4 或位於 A 線下判 ML；PI>7 且位於 A 線上判 CL；4–7 的 A 線上區為 CL-ML。細料 >12% 且屬 CL-ML 時，粗粒土採 GC-GM／SC-SM；5–12% 細料仍依 ASTM 規則採雙重符號。未輸入 D10/D30/D60 時，不會虛構 GW/GP 或 SW/SP。AASHTO 限值依 M 145 將小數試驗值先四捨五入至整數；GI 上限 20，A-2-6／A-2-7 僅採 PI 部分。")
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
        er=st.selectbox("錘擊能量比 ER [%]",[45,60,70,80,85,90,100],index=3,key="m3_er")
        cb_label=st.selectbox("鑽孔直徑（CB）",["65–115 mm（1.00）","150 mm（1.05）","200 mm（1.15）"],index=0,key="m3_cb_label")
        cb={"65–115 mm（1.00）":1.00,"150 mm（1.05）":1.05,"200 mm（1.15）":1.15}[cb_label]
    with b:
        cs_label=st.selectbox("取樣器內襯修正 CS",["有內襯（1.00）","無內襯／一般（1.10）","無內襯／較高修正（1.20）","無內襯／最高修正（1.30）"],index=0,key="m3_cs_label")
        cs={"有內襯（1.00）":1.00,"無內襯／一般（1.10）":1.10,"無內襯／較高修正（1.20）":1.20,"無內襯／最高修正（1.30）":1.30}[cs_label]
        rod_len=st.number_input("鑽桿長度 [m]",0.5,60.0,8.0,0.5,key="m3_rod")
        st.caption("CR 依鑽桿長度自動採建議值；仍須依設備型式與採用規範核對。")
    with c:
        sigma_v=st.number_input("有效覆土應力 σ'v [kPa]",1.0,2000.0,95.0,5.0,key="m3_sv")
        soil_behavior=st.selectbox("土層性質",["砂土／非凝聚性土壤","黏土／凝聚性土壤"],key="m3_soil_behavior")
        soil_behavior_code="cohesionless" if soil_behavior.startswith("砂土") else "cohesive"
        cn_method=st.selectbox("覆土壓力修正 CN",["Liao & Whitman","Seed & Idriss","Skempton","不修正"],key="m3_cnmethod",disabled=(soil_behavior_code=="cohesive"))
        cn_cap=st.number_input("CN 上限（USACE 2025 Liao–Whitman 可至 2.0；Seed–Idriss 液化法自動不超過 1.7）",1.0,2.5,2.0,0.1,key="m3_cncap")
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
    st.caption("必要欄位：Depth_m、N、Effective_Stress_kPa；可選填 Refusal（true/false）標記拒錘／部分貫入，另可加 Penetration_mm 記錄實際貫入量。每列共用上方設備修正係數，但依各深度有效覆土應力計算 CN；拒錘列會保留但不計算一般 N60。")
    csv_file=st.file_uploader("上傳逐深度 SPT CSV（UTF-8）",type=['csv'],key='m3_csv_upload')
    default_csv="Depth_m,N,Effective_Stress_kPa\n5,12,50\n10,18,95\n15,25,140"
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
            qcap4=st.number_input("模組五 qu,gross／FS 上限 [kPa]（0＝不套用）",0.0,20000.0,0.0,10.0,key='m4_bb_qcap')
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
                st.warning(f"目前輸入 q={q4:.1f} kPa 高於模組五 qu,gross/FS={qcap4:.1f} kPa；沉陷估算改以後者計算。")
            r=burland_burbidge_2025_settlement(gross_pressure_kpa=q4_used,**bb_args)
            qa_bb=burland_burbidge_2025_allowable_pressure(target_settlement_mm=target_bb4,max_pressure_kpa=max_q4,**bb_args)
            st.metric("沉陷＋承載力控制容許總接觸壓力",f"{qa_bb['qa_settlement_gross_kpa']:.1f} kPa")
            st.write(f"目前 q 採用值 = {q4_used:.1f} kPa 時，估算沉陷 = {r['settlement_mm']:.1f} mm ｜ 容許沉陷 = {target_bb4:.1f} mm")
            st.write(f"影響深度 Zi = {r['influence_depth_m']:.2f} m ｜ N60 採用值 = {r['N60_average_used']:.2f} ｜ Ic = {r['Ic_tsf_inv']:.5f} tsf⁻¹")
            st.write(f"形狀係數 C1 = {r['C1_shape']:.3f} ｜ 層厚係數 C2 = {r['C2_layer']:.3f} ｜ 時間係數 C3 = {r['C3_time']:.3f} ｜ {r['regime']}")
            st.caption(r['method'])
            st.warning(r['limitations'])
            if qa_bb['pressure_search_limit_reached'] and qcap4>0 and qcap4<=5000:
                st.caption("容許壓力受模組五輸入的 qu,gross／FS 上限控制；在該上限內，預估沉陷仍未超過目標值。")
            elif qa_bb['pressure_search_limit_reached']:
                st.warning("5,000 kPa 搜尋上限內仍未達容許沉陷量，結果受搜尋上限控制，請檢查輸入。")
            if qa_bb['no_feasible_pressure']: st.error("即使不增加基礎接觸壓力，公式中的初始應力沉陷項仍已超過容許沉陷量；目前沒有可行的正接觸壓力解，請檢查 σ′0、N60、目標沉陷與方法適用性。")
            st.info("本結果已可選擇套用模組五 qu,gross／FS 作承載力上限；若未輸入該值，結果僅受沉陷控制。請確認模組五使用相同基礎尺寸、埋深、地下水與地層條件。")
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
            st.warning("本模組只估算一維主固結沉陷；尚未計算即時沉陷、次壓縮、固結時間速率（Cv／排水距離）、開挖回彈及差異沉陷。σ′0、σ′p、Cc、Cr、e0 必須由代表性室內固結試驗與地層應力分析取得。")
        except Exception as exc: st.error(f"黏土主固結估算失敗：{exc}")
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
        st.caption(f"供模組四比較之總極限承載力／安全係數：qu,gross／FS = {result5['qu_gross_over_FS']:.1f} kPa；淨容許承載力 qa,net = {result5['qa_net']:.1f} kPa（請依模組四方法選用對應的 gross 或 net 壓力上限）。")
        if theory5=='Terzaghi': st.caption(f"Terzaghi {result5['failure_mode']}：採用 c = {result5['c_used']:.2f} kPa、ϕ = {result5['phi_used']:.2f}°；承載力因子依 USACE 表列值線性插值。")
        if '模組一' in src5:
            st.warning(f"本次使用模組一等效 Mohr–Coulomb 參數；其 c′、ϕ′係在 σ3,max={sig3_max:.3f} MPa 範圍內擬合，須確認與淺基礎破壞應力範圍相符。若不相符，請改用試驗參數或重新設定模組一圍壓範圍。")
        st.warning(result5['limitations'])
    st.caption("Hoek–Brown 岩體等效 c′、ϕ′僅應用於適當岩體尺度與破壞模式；不可不加判斷地當作一般土壤參數。SPT 推估 ϕ 亦僅為經驗參考，不取代三軸／直剪試驗。")
    with st.expander("理論公式與文獻來源",expanded=False):
        st.markdown("- [USACE EM 1110-1-1905（2025）：淺基礎承載力設計（現行手冊）](https://publibrary.sec.usace.army.mil/api/download?filename=EM+1110-1-1905_Geotechincal+Design+of+Shallow+Foundations+on+Soils_2025+07+22+-+Final.pdf&id=54658636-77d2-48df-f26b-5295a01899a7&preview=true)\n- [USACE EM 1110-1-1905（1992）：經典承載力因子表](https://www.publications.usace.army.mil/Portals/76/Publications/EngineerManuals/EM_1110-1-1905.pdf)\n- [FHWA GEC No. 6：Shallow Foundations](https://www.fhwa.dot.gov/engineering/geotech/pubs/010943.pdf)\n- [geolysis 開源套件公式文件](https://docs.geolysis.io/en/latest/formulas/ultimate-bearing-capacity/)")
