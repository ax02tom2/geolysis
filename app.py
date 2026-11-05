import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math

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


    with st.expander("🗺️ GSI 現場評估", expanded=False):
        st.markdown("請先對照下列圖例，再分別選取 **岩體結構** 與 **節理面狀況**。GSI 是地質判釋指標，不是由單一照片自動量測的物理量。")
        st.info("**圖例與文獻**：建議先開啟 Hoek（2023）Practical Rock Engineering 第 15 圖（GSI 判讀矩陣），再參考 Medwedeff et al. 的 Figure 3（露頭照片與 GSI 判讀案例）。文獻圖僅供對照，不能取代現場地質判釋。")
        st.markdown("- [Hoek：Practical Rock Engineering（Figure 15：GSI 判讀圖）](https://static.rocscience.cloud/assets/resources/learning/hoek/Practical-Rock-Engineering-E.Hoek-2023.pdf)\n- [Medwedeff et al.：現場露頭照片與 GSI 判讀案例（Figure 3）](https://deepblue.lib.umich.edu/bitstream/handle/2027.42/171564/jgrf21486.pdf?sequence=2)\n- [Hoek, Carter & Diederichs (2013)：GSI 圖量化研究](https://static.rocscience.cloud/assets/resources/learning/hoek/2013-Quantification-of-the-GSI-Chart.pdf)")
        st.caption("現場觀察建議：記錄節理組數、平均間距、延續性、岩塊互鎖程度、粗糙度、風化程度、開口及填充物；最好同時拍攝全景與近照，並附比例尺。")
        
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
    st.caption("依 ASTM D2487 / AASHTO M 145 的基本判別流程。請輸入完整篩分析與阿太堡限度；缺少資料時會標示資料不足，不以預設值冒充試驗結果。")
    c1, c2, c3 = st.columns(3)
    with c1:
        p200 = st.number_input("#200 篩通過率 P200 [%]", 0.0, 100.0, 38.0, 1.0, key="m2_p200")
        p4 = st.number_input("#4 篩通過率 P4 [%]", 0.0, 100.0, 58.0, 1.0, key="m2_p4")
        p10 = st.number_input("#10 篩通過率 P10 [%]（AASHTO）", 0.0, 100.0, 48.0, 1.0, key="m2_p10")
        p40 = st.number_input("#40 篩通過率 P40 [%]（AASHTO）", 0.0, 100.0, 42.0, 1.0, key="m2_p40")
    with c2:
        ll = st.number_input("液性限度 LL [%]", 0.0, 200.0, 42.0, 1.0, key="m2_ll")
        pl = st.number_input("塑性限度 PL [%]", 0.0, 200.0, 22.0, 1.0, key="m2_pl")
        np_flag = st.checkbox("NP（無塑性）", key="m2_np")
    with c3:
        organic = st.checkbox("有機土（需依顏色／氣味／烘乾前後 LL 確認）", key="m2_org")
        d10 = st.number_input("D10 [mm]（粗粒土級配判定）", min_value=0.0001, value=0.15, format="%.4f", key="m2_d10")
        d30 = st.number_input("D30 [mm]", min_value=0.0001, value=0.60, format="%.4f", key="m2_d30")
        d60 = st.number_input("D60 [mm]", min_value=0.0001, value=1.80, format="%.4f", key="m2_d60")
    valid_gradation = d10 <= d30 <= d60
    valid_fractions = p200 <= p4 and p4 <= p40 <= p10
    pi = 0.0 if np_flag else ll - pl
    if not np_flag and pl > ll:
        st.error("PL 不可大於 LL，請檢查試驗資料。")
    elif not valid_fractions:
        st.error("#200 通過率不可大於 #4 通過率，請檢查篩分析資料。")
    elif not valid_gradation:
        st.error("粒徑必須符合 D10 ≤ D30 ≤ D60。")
    else:
        cu = d60 / d10
        cc = (d30*d30)/(d10*d60)
        if p200 >= 50:
            above_a = pi >= 0.73*(ll-20) and pi > 0
            if organic:
                uscs = "OL" if ll < 50 else "OH"
            elif np_flag or pi < 4:
                uscs = "ML" if ll < 50 else "MH"
            elif above_a:
                uscs = "CL" if ll < 50 else "CH"
            elif 4 <= pi <= 7 and ll < 50:
                uscs = "CL-ML"
            else:
                uscs = "ML" if ll < 50 else "MH"
        else:
            coarse_gravel = p4 - p200
            coarse_sand = 100.0 - p4
            major = "G" if coarse_gravel >= coarse_sand else "S"
            if p200 < 5:
                well = (cu >= 4 and 1 <= cc <= 3) if major == "G" else (cu >= 6 and 1 <= cc <= 3)
                uscs = major + ("W" if well else "P")
            elif p200 >= 12:
                above_a = pi >= 0.73*(ll-20) and pi > 0
                suffix = ("C" if above_a else "M")
                uscs = major + suffix
            else:
                well = (cu >= 4 and 1 <= cc <= 3) if major == "G" else (cu >= 6 and 1 <= cc <= 3)
                above_a = pi >= 0.73*(ll-20) and pi > 0
                uscs = major + ("W" if well else "P") + "-" + ("C" if above_a else "M")
        # AASHTO M145
        if p200 <= 35:
            if p200 <= 10 and p40 > 50:
                aashto = "A-3"
            elif p200 <= 15 and p10 <= 50 and p40 <= 30 and p4 <= 50:
                aashto = "A-1-a"
            elif p200 <= 25 and p40 <= 50:
                aashto = "A-1-b"
            elif p200 <= 35 and pi <= 10:
                aashto = "A-2-4" if ll <= 40 else "A-2-5"
            else:
                aashto = "A-2-6" if ll <= 40 else "A-2-7"
        else:
            if ll <= 40 and pi <= 10: aashto = "A-4"
            elif ll > 40 and pi <= 10: aashto = "A-5"
            elif ll <= 40 and pi > 10: aashto = "A-6"
            else: aashto = "A-7-5" if pi <= (ll-30) else "A-7-6"
        gi_raw = (p200-35)*(0.2+0.005*(ll-40)) + 0.01*(p200-15)*(pi-10)
        gi = max(0, int(round(gi_raw))) if p200 > 35 else 0
        r1, r2 = st.columns(2)
        r1.success(f"**USCS 分類：{uscs}**")
        r2.success(f"**AASHTO 分類：{aashto}；GI = {gi}**")
        st.write(f"塑性指數 PI = {pi:.1f}%；Cu = {cu:.2f}；Cc = {cc:.2f}；礫粒 = {100-p4:.1f}%；砂粒 = {p4-p200:.1f}%；細料 = {p200:.1f}%")
        st.caption(f"AASHTO 篩分析檢核：P10={p10:.1f}%、P40={p40:.1f}%、P200={p200:.1f}%。")
        st.caption("注意：雙重符號、含有機質土、礫石／砂土細分類及邊界值，仍須依完整試驗資料與 ASTM/AASHTO 正式分類表複核。本工具目前提供工程初判，非試驗報告自動簽證。")


# 模組三：SPT 標準貫入試驗全修正
# ==============================================================================
with st.expander("🔨 模組三：SPT 標準貫入試驗全修正", expanded=exp_3):
    st.subheader("🔨 SPT 標準貫入試驗全修正")
    st.caption("N60 = N × CE × CB × CS × CR；(N1)60 = CN × N60。修正係數應依實際設備、操作紀錄與採用規範設定。")
    a,b,c = st.columns(3)
    with a:
        n_measured = st.number_input("現場量測 N 值（末 300 mm）", min_value=0, max_value=200, value=18, key="m3_n")
        hammer_eff = st.selectbox("錘擊能量比 ER [%]", [45, 60, 70, 80, 85, 90, 100], index=3, key="m3_er")
        cb = st.selectbox("鑽孔直徑修正 CB", [0.75, 0.80, 1.00, 1.05, 1.15], index=2, key="m3_cb")
    with b:
        cs = st.selectbox("取樣器修正 CS", [1.00, 1.05, 1.10], index=0, key="m3_cs")
        rod_len = st.number_input("鑽桿長度 [m]", min_value=0.5, max_value=60.0, value=8.0, step=0.5, key="m3_rod")
        if rod_len < 3: cr = 0.75
        elif rod_len < 4: cr = 0.80
        elif rod_len < 6: cr = 0.85
        elif rod_len < 10: cr = 0.95
        else: cr = 1.00
        st.metric("依鑽桿長度建議 CR", f"{cr:.2f}")
    with c:
        sigma_v = st.number_input("有效覆土應力 σ'v [kPa]", min_value=1.0, max_value=2000.0, value=95.0, step=5.0, key="m3_sv")
        cn_method = st.selectbox("覆土壓力修正 CN", ["Liao & Whitman (1986)", "Skempton (1986)", "不修正（CN=1）"], key="m3_cnmethod")
        cn_cap = st.number_input("CN 上限", min_value=1.0, max_value=2.5, value=2.0, step=0.1, key="m3_cncap")
    ce = hammer_eff/60.0
    n60 = n_measured*ce*cb*cs*cr
    if cn_method == "Liao & Whitman (1986)": cn_raw = math.sqrt(100.0/sigma_v)
    elif cn_method == "Skempton (1986)": cn_raw = 2.0/(1.0+sigma_v/100.0)
    else: cn_raw = 1.0
    cn = min(cn_cap, cn_raw)
    n1_60_corr = cn*n60
    phi_hat = min(45.0, max(20.0, 27.1 + 0.3*n1_60_corr - 0.00054*(n1_60_corr**2)))
    r1,r2,r3 = st.columns(3)
    r1.metric("能量修正 N60", f"{n60:.2f}")
    r2.metric("覆土修正 CN", f"{cn:.3f}")
    r3.metric("最終 (N1)60", f"{n1_60_corr:.2f}")
    st.info(f"砂土內摩擦角經驗參考值：約 {phi_hat:.1f}°（僅適用於適當砂土條件；不得視為通用直接換算式）。")
    st.markdown("**修正係數明細**")
    st.dataframe(pd.DataFrame([{"係數":"CE 能量比","值":ce},{"係數":"CB 鑽孔直徑","值":cb},{"係數":"CS 取樣器","值":cs},{"係數":"CR 鑽桿長度","值":cr},{"係數":"CN 覆土壓力","值":cn}]), hide_index=True, use_container_width=True)
    st.markdown("**鑽孔逐深度資料（選填）**")
    st.caption("可貼上 CSV，欄位：Depth_m,N,Effective_Stress_kPa。每列會依本模組目前選定的設備係數計算 N60 與 (N1)60。")
    profile_text = st.text_area("逐深度 CSV", "Depth_m,N,Effective_Stress_kPa\n5,12,50\n10,18,95\n15,25,140", height=110, key="m3_profile")
    try:
        from io import StringIO
        prof = pd.read_csv(StringIO(profile_text))
        if {"Depth_m","N","Effective_Stress_kPa"}.issubset(prof.columns) and len(prof):
            prof["N60"] = prof["N"]*ce*cb*cs*cr
            if cn_method == "Liao & Whitman (1986)": prof["CN"] = (100/prof["Effective_Stress_kPa"].clip(lower=1)).pow(0.5).clip(upper=cn_cap)
            elif cn_method == "Skempton (1986)": prof["CN"] = (2/(1+prof["Effective_Stress_kPa"]/100)).clip(upper=cn_cap)
            else: prof["CN"] = 1.0
            prof["N1_60"] = prof["N60"]*prof["CN"]
            st.dataframe(prof, hide_index=True, use_container_width=True)
            fig_spt = go.Figure(go.Scatter(x=prof["N1_60"], y=prof["Depth_m"], mode="lines+markers", name="(N1)60"))
            fig_spt.update_yaxes(autorange="reversed", title="深度 [m]")
            fig_spt.update_xaxes(title="(N1)60")
            fig_spt.update_layout(height=380, title="SPT 修正值深度剖面")
            st.plotly_chart(fig_spt, use_container_width=True)
        else:
            st.warning("CSV 欄位需包含 Depth_m、N、Effective_Stress_kPa。")
    except Exception as exc:
        st.warning(f"逐深度 CSV 尚無法解析：{exc}")


# 模組四：容許承載力與沉陷控制
# ==============================================================================
with st.expander("📏 模組四：容許承載力與沉陷控制", expanded=exp_4):
    st.subheader("📏 容許承載力與沉陷控制")
    st.caption("以砂土 SPT 經驗法進行初步估算，並與使用者設定的沉陷容許值比較。此為經驗估算，不取代分層彈性沉陷分析或載重試驗。")
    x1,x2,x3 = st.columns(3)
    with x1:
        n_design = st.number_input("基礎影響深度內平均 (N1)60", min_value=1.0, max_value=100.0, value=float(max(1,round(n1_60_corr,1))), step=1.0, key="m4_n")
        b_abc = st.number_input("基礎寬度 B [m]", min_value=0.3, max_value=30.0, value=2.5, step=0.1, key="m4_b")
    with x2:
        l_abc = st.number_input("基礎長度 L [m]", min_value=0.3, max_value=100.0, value=3.0, step=0.1, key="m4_l")
        df_abc = st.number_input("基礎埋深 Df [m]", min_value=0.0, max_value=30.0, value=1.5, step=0.1, key="m4_df")
    with x3:
        settlement_allow = st.number_input("容許沉陷量 [mm]", min_value=5.0, max_value=100.0, value=25.0, step=5.0, key="m4_sallow")
        fs_settle = st.number_input("經驗估算安全／修正係數", min_value=0.5, max_value=2.0, value=1.0, step=0.1, key="m4_factor")
    shape_factor = 1.0 if l_abc/b_abc > 5 else (1.0+0.2*b_abc/l_abc)
    # Simplified Meyerhof-type SPT correlation for preliminary settlement-limited pressure
    q_settle = (n_design/0.05) * (b_abc+0.3)/b_abc * (1+0.33*df_abc/b_abc) * (settlement_allow/25.0) / shape_factor * fs_settle
    st.metric("沉陷控制容許承載力 qₐ,settlement", f"{q_settle:.1f} kPa")
    st.caption("採用簡化 SPT–沉陷經驗關係作初估；實際適用性受砂土密度、地下水、基礎尺寸、埋深、應力歷程與沉陷定義影響。")
    st.warning("本模組目前尚未完成黏土固結沉陷、分層土層積分、偏心／傾斜載重與筏基差異沉陷分析；不應將本估算直接作為最終設計值。")


# 模組五：極限承載力四大理論
# ==============================================================================
with st.expander("🏗️ 模組五：極限承載力四大理論", expanded=exp_5):
    st.subheader("🏗️ 極限承載力四大理論")
    st.caption("採一般淺基礎承載力架構 qᵤ = cNc sc dc ic + qNq sq dq iq + 0.5γ'BNγ sγ dγ iγ。不同理論的承載力因子定義不同；此版本提供常用近似式與透明係數，不宣稱涵蓋所有規範細節。")
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        theory = st.selectbox("承載力理論", ["Vesic (1973)","Hansen (1970)","Meyerhof (1963)","Terzaghi (1943)"], key="m5_theory")
        shape = st.selectbox("基礎形狀", ["條形","方形","圓形","矩形"], key="m5_shape")
        B = st.number_input("基礎寬度 B [m]", min_value=0.2, max_value=50.0, value=2.0, step=0.1, key="m5_b")
        L = st.number_input("基礎長度 L [m]", min_value=0.2, max_value=100.0, value=3.0, step=0.1, key="m5_l")
    with c2:
        source = st.selectbox("力學參數來源", ["手動輸入 c、ϕ","帶入模組一：Hoek-Brown 等效參數","帶入模組三：SPT 推估 ϕ"], key="m5_src")
        c_default = float(round(c_hb_kpa,1)) if "模組一" in source else 15.0
        phi_default = float(round(phi_hb_deg,1)) if "模組一" in source else (float(round(phi_hat,1)) if "模組三" in source else 30.0)
        cval = st.number_input("凝聚力 c [kPa]", min_value=0.0, max_value=1000.0, value=c_default, step=1.0, key="m5_c")
        phival = st.number_input("內摩擦角 ϕ [°]", min_value=0.0, max_value=55.0, value=min(55.0,phi_default), step=1.0, key="m5_phi")
        gamma = st.number_input("土壤單位重 γ [kN/m³]", min_value=10.0, max_value=30.0, value=18.5, step=0.5, key="m5_gamma")
    with c3:
        Df = st.number_input("基礎埋深 Df [m]", min_value=0.0, max_value=30.0, value=1.5, step=0.1, key="m5_df")
        Dw = st.number_input("地下水位深度（地表下）Dw [m]", min_value=0.0, max_value=100.0, value=5.0, step=0.1, key="m5_dw")
        fs = st.number_input("安全係數 FS", min_value=1.0, max_value=5.0, value=3.0, step=0.5, key="m5_fs")
    with c4:
        load_tilt = st.number_input("載重傾角 β [°]（水平偏斜）", min_value=0.0, max_value=30.0, value=0.0, step=1.0, key="m5_beta")
        groundwater_gamma = st.number_input("水下有效單位重 γ' [kN/m³]", min_value=5.0, max_value=15.0, value=9.5, step=0.5, key="m5_gammasub")
        base_incl = st.number_input("基底傾角 α [°]", min_value=0.0, max_value=15.0, value=0.0, step=1.0, key="m5_alpha")
    phi = math.radians(phival)
    if phival == 0:
        Nq = 1.0; Nc = 5.14; Ngamma = 0.0
    else:
        Nq = math.exp(math.pi*math.tan(phi))*math.tan(math.radians(45)+phi/2)**2
        Nc = (Nq-1)/math.tan(phi)
        if theory.startswith("Vesic"):
            Ngamma = 2*(Nq+1)*math.tan(phi)
        elif theory.startswith("Hansen"):
            Ngamma = 1.5*(Nq-1)*math.tan(phi)
        elif theory.startswith("Meyerhof"):
            Ngamma = (Nq-1)*math.tan(1.4*phi)
        else:
            Ngamma = 1.5*(Nq-1)*math.tan(phi)
    ratio = 1.0 if shape == "條形" else (1.0+B/L if shape == "矩形" else 1.2)
    sc = 1.0 if theory.startswith("Terzaghi") else 1.0+(Nq/Nc)*(B/L)
    sq = 1.0 if theory.startswith("Terzaghi") else 1.0+(B/L)*math.tan(phi)
    sg = 1.0 if theory.startswith("Terzaghi") else max(0.6,1.0-0.4*(B/L))
    if theory.startswith("Terzaghi"):
        sc = 1.0 if shape == "條形" else (1.3 if shape == "方形" else 1.3)
        sq = 1.0 if shape == "條形" else 1.0
        sg = 1.0 if shape == "條形" else (0.8 if shape == "方形" else 0.6)
    dc = 1.0 if theory.startswith("Terzaghi") else 1.0+0.4*Df/B
    dq = 1.0 if theory.startswith("Terzaghi") else 1.0+2*math.tan(phi)*(1-math.sin(phi))**2*(Df/B)
    dg = 1.0
    # Water table correction for surcharge and unit-weight terms
    q_over = gamma*min(Df,Dw) + groundwater_gamma*max(0.0,Df-Dw)
    if Dw <= Df:
        gamma_eff = groundwater_gamma
    elif Dw < Df+B:
        gamma_eff = groundwater_gamma+(gamma-groundwater_gamma)*(Dw-Df)/B
    else:
        gamma_eff = gamma
    beta = math.radians(load_tilt)
    ic = iq = ig = max(0.0,(1-load_tilt/90.0)**2)
    if base_incl > 0:
        fac = max(0.0,(1-base_incl/90.0)**2)
        ic *= fac; iq *= fac; ig *= fac
    term_c = cval*Nc*sc*dc*ic
    term_q = q_over*Nq*sq*dq*iq
    term_g = 0.5*gamma_eff*B*Ngamma*sg*dg*ig
    q_ult = term_c+term_q+term_g
    q_net_ult = q_ult-q_over
    q_allow_gross = q_net_ult/fs+q_over
    q_allow_net = q_net_ult/fs
    r1,r2,r3 = st.columns(3)
    r1.metric("總極限承載力 qᵤ", f"{q_ult:.1f} kPa")
    r2.metric("淨容許承載力 qₐ,net", f"{q_allow_net:.1f} kPa")
    r3.metric("總容許承載力 qₐ,gross", f"{q_allow_gross:.1f} kPa")
    st.markdown("**計算分項與承載力因子**")
    st.dataframe(pd.DataFrame([{"項目":"凝聚力項 cNc","承載力因子":Nc,"形狀係數":sc,"深度係數":dc,"傾斜係數":ic,"貢獻(kPa)":term_c},{"項目":"覆土項 qNq","承載力因子":Nq,"形狀係數":sq,"深度係數":dq,"傾斜係數":iq,"貢獻(kPa)":term_q},{"項目":"單位重項 0.5γBNγ","承載力因子":Ngamma,"形狀係數":sg,"深度係數":dg,"傾斜係數":ig,"貢獻(kPa)":term_g}]), hide_index=True, use_container_width=True)
    st.caption(f"採用 {theory}；有效覆土壓力 q = {q_over:.2f} kPa；基底有效單位重 γ' = {gamma_eff:.2f} kN/m³。")
    st.warning("設計限制：本版尚未實作完整 Hansen/Vesic/Meyerhof 所有係數組合、偏心載重有效面積、層狀地盤、斜坡地表、地震、群樁／筏基及規範特定修正。正式設計前須依採用規範逐項核對。")

