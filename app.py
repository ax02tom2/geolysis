import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math
from io import StringIO
from geolysis_engine import classify_uscs_aashto, spt_correct, spt_profile, usace_meyerhof_settlement_allowable, consolidation_allowable_pressure, bearing_capacity

st.set_page_config(page_title="geolysis 大地工程分析系統", page_icon="🧱", layout="wide")

st.title("🧱 geolysis 大地工程分析系統")
st.markdown(r"""
本系統結合 **Hoek-Brown (2002) 岩體裂隙參數推估** 與開源套件 **[geolysis](https://github.com/patrickboateng/geolysis)** 核心工程模組：
- **模組一：Hoek-Brown 岩體裂隙推估 ($c', \phi'$)** — 依據地質強度指標 (GSI，內建現場結構×節理交叉查表)、岩性常數 ($m_i$)、單壓強度與邊坡深度，自動轉換等效莫耳－庫倫參數
- **模組二：土壤分類系統** — USCS 統一土壤分類法 & AASHTO 公路土壤分類法（含群指數 $GI$ 與雙重符號判定）
- **模組三：SPT 標準貫入試驗修正** — 能量、鑽孔直徑、取樣器、鑽桿與覆土壓力修正，含逐深度剖面
- **模組四：容許承載力與沉陷控制** — 砂土 SPT 經驗法及黏土一維主固結沉陷反算
- **模組五：極限承載力四大理論** — Terzaghi / Meyerhof / Hansen / Vesic 理論係數、形狀／深度／載重傾斜及地下水影響
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


    with st.expander("🗺️ GSI 現場評估", expanded=False):
        st.markdown("請先對照下列圖例，再分別選取 **岩體結構** 與 **節理面狀況**。GSI 是地質判釋指標，不是由單一照片自動量測的物理量。")
        st.markdown("GSI 主要依 **岩體結構（破碎程度、節理組數與互鎖性）** 及 **不連續面表面品質（粗糙度、風化與填充物）** 綜合判讀。以下直接展示研究中的現場案例，請先看照片，再對照圖中的 GSI 區間。")
        st.markdown("**現場露頭照片與 GSI 判讀案例**")
        st.info("外部論文 PDF 內嵌容易受第三方網站限制；本頁改以系統內建 GSI 判讀矩陣圖呈現，文獻案例仍保留出處供查證。")
        st.caption("圖例出處：Medwedeff, W. G. et al. (2022), Figure 3, *Journal of Geophysical Research: Earth Surface*, 127, e2021JF006240. 圖中案例描述為三組主要節理、間距約 10–30 cm、中度風化，作者判讀 GSI 約 50–65。")
        with st.expander("文獻來源（完整論文與補充判讀資料）", expanded=False):
            st.markdown("- [Medwedeff et al. (2022)：Figure 3 現場照片與 GSI 判讀案例](https://doi.org/10.1029/2021JF006240)\n- [Hoek：Practical Rock Engineering（GSI 判讀矩陣）](https://static.rocscience.cloud/assets/resources/learning/hoek/Practical-Rock-Engineering-E.Hoek-2023.pdf)\n- [Hoek, Carter & Diederichs (2013)：GSI 圖量化研究](https://static.rocscience.cloud/assets/resources/learning/hoek/2013-Quantification-of-the-GSI-Chart.pdf)")
        st.caption("現場觀察建議：記錄節理組數、平均間距、延續性、岩塊互鎖程度、粗糙度、風化程度、開口及填充物；最好同時拍攝全景與近照，並附比例尺。文獻案例僅供比對，不代表其他岩性或露頭可直接套用相同 GSI。")
        
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
        fig_gsi = go.Figure(data=go.Heatmap(
            z=gsi_matrix,
            x=["I 極佳", "II 良好", "III 普通", "IV 不良", "V 極差"],
            y=["A 巨塊狀", "B 塊狀", "C 次塊狀", "D 碎裂", "E 剪碎／泥化"],
            text=gsi_matrix, texttemplate="%{text}",
            colorscale="RdYlGn", reversescale=False, showscale=True,
            colorbar=dict(title="GSI")))
        fig_gsi.update_layout(title="GSI 現場判讀矩陣（系統參考值）",height=390,
            xaxis_title="節理面狀況",yaxis_title="岩體結構",margin=dict(l=20,r=20,t=55,b=30))
        st.plotly_chart(fig_gsi,use_container_width=True)
        st.warning(f"初步矩陣參考值：GSI 約 {matrix_gsi}。這是定性查表的中心參考，不代表精確測值；請依現場紀錄另行確認合理範圍。")
        gr1, gr2 = st.columns(2)
        with gr1:
            gsi_lower = st.number_input("GSI 初判下限", min_value=0, max_value=100, value=max(0, matrix_gsi-5), key="gsi_lower")
        with gr2:
            gsi_upper = st.number_input("GSI 初判上限", min_value=0, max_value=100, value=min(100, matrix_gsi+5), key="gsi_upper")
        if gsi_lower > gsi_upper:
            st.error("GSI 下限不可大於上限。")
        else:
            st.caption(f"人工確認區間：GSI {gsi_lower}–{gsi_upper}；計算仍使用下方選定的單一代表值。")
        
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
    st.caption("依 ASTM D2487 與 AASHTO M 145 判別邏輯進行工程初判。篩分析通過率必須符合 P4 ≥ P10 ≥ P40 ≥ P200。")
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
                d10=d10,d30=d30,d60=d60,organic=organic,ll_oven_dried=(ll_od if organic and organic_test_done else None))
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
        st.caption("5–12% 細料之粗粒土採雙重符號；未輸入 D10/D30/D60 時，不會虛構 GW/GP 或 SW/SP 級配判定。")
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
        cn_method=st.selectbox("覆土壓力修正 CN",["Liao & Whitman","Seed & Idriss","Skempton","不修正"],key="m3_cnmethod")
        cn_cap=st.number_input("CN 上限",1.0,2.5,1.7,0.1,key="m3_cncap")
    try:
        current=spt_correct(n_measured,er,cb,cs,rod_len,sigma_v,cn_method,cn_cap)
        r1,r2,r3=st.columns(3)
        r1.metric("N60",f"{current['N60']:.2f}")
        r2.metric("CN",f"{current['CN']:.3f}")
        r3.metric("(N1)60",f"{current['N1_60']:.2f}")
        st.dataframe(pd.DataFrame([{'修正係數':'CE','值':current['CE']},{'修正係數':'CB','值':current['CB']},{'修正係數':'CS','值':current['CS']},{'修正係數':'CR','值':current['CR']},{'修正係數':'CN','值':current['CN']}]),hide_index=True,use_container_width=True)
        st.session_state['m3_current_n60']=current['N60']
        st.session_state['m3_current_n160']=current['N1_60']
    except Exception as exc: st.error(f"SPT 修正失敗：{exc}")
    st.markdown("**鑽孔逐深度資料（CSV）**")
    st.caption("必要欄位：Depth_m、N、Effective_Stress_kPa。每列共用上方設備修正係數，但依各深度有效覆土應力計算 CN。")
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
            corrected=spt_profile(rows,energy_ratio_pct=er,borehole_factor=cb,sampler_factor=cs,rod_length_m=rod_len,cn_method=cn_method,cn_cap=cn_cap)
            out=pd.DataFrame(corrected)
            st.dataframe(out,use_container_width=True,hide_index=True)
            fig=go.Figure(go.Scatter(x=out['N1_60'],y=out['Depth_m'],mode='lines+markers',name='(N1)60'))
            fig.update_yaxes(autorange='reversed',title='深度 [m]'); fig.update_xaxes(title='(N1)60')
            fig.update_layout(height=420,title='SPT 修正值深度剖面')
            st.plotly_chart(fig,use_container_width=True)
            st.download_button('下載修正後 SPT CSV',out.to_csv(index=False).encode('utf-8-sig'),'SPT_corrected.csv','text/csv',key='m3_download')
            st.session_state['m3_profile_result']=out
        else: st.info('請提供 Depth_m、N、Effective_Stress_kPa 三欄；未提供完整欄位前不執行剖面計算。')
    except Exception as exc: st.error(f"逐深度資料檢核失敗：{exc}")
    st.caption("Liao–Whitman 與 Seed–Idriss 常用平方根型 CN；本系統將方法名稱、上限及輸入應力明確列出。不同地層／砂土液化評估另有適用條件，不能只憑 (N1)60 直接判定液化或設計參數。")
    with st.expander("SPT 修正依據與文獻",expanded=False):
        st.markdown("- [FHWA：Soils and Foundations Reference Manual](https://www.fhwa.dot.gov/engineering/geotech/pubs/nhi06089/)\n- [ASTM D1586：Standard Penetration Test (SPT)](https://www.astm.org/d1586_d1586m.html)")


# ==============================================================================
# 模組四：容許承載力與沉陷控制
# ==============================================================================
with st.expander("📏 模組四：容許承載力與沉陷控制", expanded=exp_4):
    st.subheader("📏 模組四：容許承載力與沉陷控制")
    method4=st.selectbox("分析方法",["砂土：Meyerhof SPT 沉陷控制法","黏土：一維主固結沉陷控制法"],key='m4_method')
    if method4.startswith('砂土'):
        st.caption("依 USACE EM 1110-1-1905 所列 Meyerhof SPT 經驗式，適用於砂土淺基礎初步估算。")
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
        st.caption("以 2:1 應力擴散估算壓縮層中點 Δσ，再依 e–log σ′ 一維主固結理論反算容許接觸壓力。")
        a,b,c=st.columns(3)
        with a:
            qB=st.number_input("基礎寬度 B [m]",0.3,50.0,2.0,0.1,key='m4c_b')
            qL=st.number_input("基礎長度 L [m]",0.3,100.0,3.0,0.1,key='m4c_l')
            zc=st.number_input("壓縮層中點距基礎底 z [m]",0.0,100.0,3.0,0.1,key='m4c_z')
        with b:
            Hc=st.number_input("壓縮層厚度 H [m]",0.1,100.0,5.0,0.1,key='m4c_h')
            sig0=st.number_input("初始有效垂直應力 σ′0 [kPa]",1.0,3000.0,100.0,5.0,key='m4c_sig0')
            sigp=st.number_input("先期固結壓力 σ′p [kPa]",1.0,5000.0,150.0,5.0,key='m4c_sigp')
        with c:
            e0=st.number_input("初始孔隙比 e0",0.1,3.0,0.8,0.05,key='m4c_e0')
            Cc=st.number_input("壓縮指數 Cc",0.001,2.0,0.30,0.01,key='m4c_cc')
            Cr=st.number_input("再壓縮指數 Cr",0.0,1.0,0.05,0.01,key='m4c_cr')
            target4=st.number_input("容許主固結沉陷 [mm]",1.0,200.0,25.0,1.0,key='m4c_target')
        try:
            stress_ratio=(qB*qL)/((qB+zc)*(qL+zc))
            r=consolidation_allowable_pressure(target_settlement_mm=target4,footing_pressure_factor=stress_ratio,
                layer_thickness_m=Hc,initial_void_ratio=e0,compression_index=Cc,recompression_index=Cr,
                initial_effective_stress_kpa=sig0,preconsolidation_stress_kpa=sigp)
            st.metric("主固結沉陷控制容許接觸壓力（淨值）",f"{r['qa_primary_consolidation_kpa']:.1f} kPa")
            st.write(f"2:1 應力比 = {stress_ratio:.3f} ｜ 壓縮層中點應力增量 Δσ = {r['delta_sigma_mid_kpa']:.2f} kPa ｜ 預估主固結沉陷 = {r['settlement_mm']:.2f} mm")
            st.caption(f"固結狀態：{r['regime']}；最終有效應力 = {r['final_effective_stress_kpa']:.2f} kPa。")
            if r['search_limit_reached']: st.warning('目前搜尋上限 5,000 kPa 仍未達容許沉陷量；結果受搜尋上限控制，應檢查輸入與模型適用性。')
            st.warning("本法只估算單一等效壓縮層的一維主固結沉陷；尚未計算即時沉陷、次壓縮、分層多層積分、時間速率（Cv／排水距離）及差異沉陷。σ′0、σ′p、Cc、Cr、e0 必須由代表性室內固結試驗與地層應力分析取得。")
        except Exception as exc: st.error(f"黏土主固結估算失敗：{exc}")
    with st.expander("計算依據與文獻",expanded=False):
        st.markdown("- [USACE EM 1110-1-1905：Meyerhof SPT 沉陷控制經驗式](https://www.publications.usace.army.mil/Portals/76/Publications/EngineerManuals/EM_1110-1-1905.pdf)\\n- [USACE EM 1110-1-1904：Settlement Analysis](https://www.publications.usace.army.mil/Portals/76/Publications/EngineerManuals/EM_1110-1-1904.pdf)")


# ==============================================================================
# 模組五：極限承載力四大理論
# ==============================================================================
with st.expander("🏗️ 模組五：極限承載力四大理論", expanded=exp_5):
    st.subheader("🏗️ 模組五：極限承載力四大理論")
    st.caption("採 Terzaghi、Meyerhof、Hansen、Vesic 各自的承載力因子／係數架構；請先確認土層參數代表基礎破壞影響範圍。")
    a,b,c,d=st.columns(4)
    with a:
        theory5=st.selectbox("理論",['Terzaghi','Meyerhof','Hansen','Vesic'],key='m5_theory')
        B5=st.number_input("基礎短邊 B [m]",0.2,50.0,2.0,0.1,key='m5_b')
        L5=st.number_input("基礎長邊 L [m]",0.2,100.0,3.0,0.1,key='m5_l')
    with b:
        src5=st.selectbox("參數來源",['手動輸入','模組一 Hoek-Brown 等效參數'],key='m5_src')
        cdef=float(round(c_hb_kpa,1)) if '模組一' in src5 else 15.0
        phidef=float(round(phi_hb_deg,1)) if '模組一' in src5 else 30.0
        if st.session_state.get('_m5_src_prev') != src5:
            st.session_state['m5_c']=cdef
            st.session_state['m5_phi']=min(50.0,phidef)
            st.session_state['_m5_src_prev']=src5
        c5=st.number_input("凝聚力 c [kPa]",0.0,1000.0,cdef,1.0,key='m5_c')
        phi5=st.number_input("內摩擦角 ϕ [°]",0.0,50.0,min(50.0,phidef),1.0,key='m5_phi')
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
    excol,eycol=st.columns(2)
    with excol: eL5=st.number_input("長邊方向偏心距 eL [m]",0.0,20.0,0.0,0.05,key='m5_eL')
    with eycol: eB5=st.number_input("短邊方向偏心距 eB [m]",0.0,20.0,0.0,0.05,key='m5_eB')
    load_dir5=st.selectbox("水平力方向（Vesic 公式）",['parallel_B','parallel_L'],format_func=lambda x:'平行短邊 B' if x=='parallel_B' else '平行長邊 L',disabled=(theory5!='Vesic'),key='m5_load_dir')
    adhesion5=st.number_input("基底黏著係數 ca/c（Hansen／Vesic）",0.1,1.0,0.6,0.1,key='m5_adhesion')
    if st.button("計算極限承載力",key='m5_run'):
        st.session_state.pop('m5_result',None)
        try:
            if abs(math.degrees(math.atan2(H5,V5))-beta5)>2.0 and H5>0 and theory5=='Meyerhof':
                st.warning("載重傾角 β 與 H/V 計算角度差異超過 2°；H/V 為 Hansen/Vesic 計算依據，請核對輸入。")
            result5=bearing_capacity(theory=theory5,c_kpa=c5,phi_deg=phi5,gamma_moist=gamma5,gamma_sub=gsub5,B=B5,L=L5,Df=df5,water_depth=dw5,fs=fs5,load_angle=beta5,horizontal_load=H5,vertical_load=V5,failure_mode=(failure_mode5 if theory5=='Terzaghi' else 'general'),load_direction=load_dir5,adhesion_ratio=adhesion5,eccentricity_B=eB5,eccentricity_L=eL5)
            st.session_state['m5_result']=result5
        except Exception as exc: st.error(f"承載力計算失敗：{exc}")
    result5=st.session_state.get('m5_result')
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
        if theory5=='Terzaghi': st.caption(f"Terzaghi {result5['failure_mode']}：採用 c = {result5['c_used']:.2f} kPa、ϕ = {result5['phi_used']:.2f}°；承載力因子依 USACE 表列值線性插值。")
        st.warning(result5['limitations'])
    st.caption("Hoek–Brown 岩體等效 c′、ϕ′僅應用於適當岩體尺度與破壞模式；不可不加判斷地當作一般土壤參數。SPT 推估 ϕ 亦僅為經驗參考，不取代三軸／直剪試驗。")
    with st.expander("理論公式與文獻來源",expanded=False):
        st.markdown("- [USACE EM 1110-1-1905：Terzaghi 因子表、Meyerhof／Hansen／Vesic 公式與地下水修正](https://www.publications.usace.army.mil/Portals/76/Publications/EngineerManuals/EM_1110-1-1905.pdf)\n- [FHWA GEC No. 6：Shallow Foundations](https://www.fhwa.dot.gov/engineering/geotech/pubs/010943.pdf)\n- [geolysis 開源套件公式文件](https://docs.geolysis.io/en/latest/formulas/ultimate-bearing-capacity/)")
