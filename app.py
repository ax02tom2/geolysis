import streamlit as st
import pandas as pd
import plotly.express as px
import math
import inspect
import pkgutil
import importlib

st.set_page_config(page_title="geolysis 大地工程分析系統", page_icon="🧱", layout="wide")

st.title("🧱 geolysis 大地工程分析系統")
st.markdown("""
本系統完整呈現開源套件 **[geolysis](https://github.com/patrickboateng/geolysis)** 之四大核心工程模組：
* **模組一：土壤分類系統 (`soil_classifier`)** — USCS 統一土壤分類法 & AASHTO 公路土壤分類法（含群指數 $GI$ 與雙重符號判定）
* **模組二：SPT 標準貫入試驗全修正 (`spt`)** — 器材四項修正 ($E_m, C_B, C_S, C_R$)、7 大學者覆土壓力修正 ($C_N$) 與全鑽孔剖面批次繪圖
* **模組三：容許承載力與沉陷控制 (`bearing_capacity.abc`)** — Bowles & Meyerhof 控制沉陷量之淺基礎與筏基設計
* **模組四：極限承載力四大理論 (`bearing_capacity.ubc`)** — Terzaghi / Meyerhof / Hansen / Vesic 全套修正係數與三階段地下水折減
""")

# ==============================================================================
# 側邊欄：快速檢視模式與 geolysis 原生套件探測器
# ==============================================================================
st.sidebar.title("🛠️ 顯示與套件探測")
display_mode = st.sidebar.radio(
    "選擇畫面展開模式：",
    ["全部展開 (一覽全貌)", "僅展開：模組一 (土壤分類)", "僅展開：模組二 (SPT 全修正)", "僅展開：模組三 (ABC 容許承載力)", "僅展開：模組四 (UBC 極限承載力)"]
)

st.sidebar.divider()
st.sidebar.subheader("🔍 原生套件底層探測")
try:
    import geolysis
    st.sidebar.success(f"✅ 已載入 `geolysis` ({getattr(geolysis, '__version__', '最新版')})")
    submodules = ["geolysis"]
    if hasattr(geolysis, "__path__"):
        for _, modname, _ in pkgutil.walk_packages(path=geolysis.__path__, prefix=geolysis.__name__+'.'):
            submodules.append(modname)
    
    selected_mod = st.sidebar.selectbox("檢視原創子模組：", submodules)
    if selected_mod:
        mod = importlib.import_module(selected_mod)
        members = [name for name, obj in inspect.getmembers(mod) if not name.startswith("_")]
        selected_member = st.sidebar.selectbox("檢視類別/函數原始碼：", ["(請選擇)"] + members)
        if selected_member != "(請選擇)":
            obj = getattr(mod, selected_member)
            with st.expander(f"📜 原創原始碼檢視：`{selected_mod}.{selected_member}`", expanded=True):
                try:
                    st.code(inspect.getsource(obj), language="python")
                except Exception:
                    st.write(obj)
except Exception as e:
    st.sidebar.error(f"載入 `geolysis` 異常：{e}")

# 控制各區塊是否預設展開
exp_1 = display_mode in ["全部展開 (一覽全貌)", "僅展開：模組一 (土壤分類)"]
exp_2 = display_mode in ["全部展開 (一覽全貌)", "僅展開：模組二 (SPT 全修正)"]
exp_3 = display_mode in ["全部展開 (一覽全貌)", "僅展開：模組三 (ABC 容許承載力)"]
exp_4 = display_mode in ["全部展開 (一覽全貌)", "僅展開：模組四 (UBC 極限承載力)"]


# ==============================================================================
# 模組一：土壤分類系統 (geolysis.soil_classifier)
# ==============================================================================
with st.expander("🌱 模組一：土壤分類系統 (USCS & AASHTO 完整分類引擎)", expanded=exp_1):
    st.subheader("🌱 土壤分類系統 (`geolysis.soil_classifier`)")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("##### 1. 阿太堡限度 (Atterberg Limits)")
        ll = st.number_input("液性限度 Liquid Limit (LL) [%]", min_value=0.0, max_value=200.0, value=42.0, step=1.0)
        pl = st.number_input("塑性限度 Plastic Limit (PL) [%]", min_value=0.0, max_value=200.0, value=22.0, step=1.0)
        is_np = st.checkbox("無塑性 (Non-Plastic, NP)", value=False)
        organic = st.checkbox("含高有機質 (Organic Soil)", value=False)
        pi = 0.0 if is_np else max(0.0, ll - pl)
        st.metric("計算塑性指數 (PI = LL - PL)", "NP" if is_np else f"{pi:.1f} %")

    with col_b:
        st.markdown("##### 2. 粒徑分佈與級配參數 (PSD)")
        fines = st.number_input("過 200 號篩百分比 (Fines < 0.075mm) [%]", min_value=0.0, max_value=100.0, value=38.0, step=1.0)
        sand = st.number_input("砂粒含量 (Sand, 0.075mm ~ 4.75mm) [%]", min_value=0.0, max_value=100.0, value=42.0, step=1.0)
        gravel = max(0.0, 100.0 - fines - sand)
        st.caption(f"自動推算礫石含量 (Gravel > 4.75mm)：**{gravel:.1f} %**")
        
        c1, c2, c3 = st.columns(3)
        d10 = c1.number_input("有效粒徑 D10 [mm]", min_value=0.001, value=0.15, format="%.3f")
        d30 = c2.number_input("粒徑 D30 [mm]", min_value=0.001, value=0.60, format="%.3f")
        d60 = c3.number_input("粒徑 D60 [mm]", min_value=0.001, value=1.80, format="%.3f")
        
        cu = d60 / d10 if d10 > 0 else 0.0
        cc = (d30 ** 2) / (d10 * d60) if (d10 * d60) > 0 else 0.0
        st.caption(f"均勻係數 $C_u = {cu:.2f}$ ｜ 曲率係數 $C_c = {cc:.2f}$")

    # 即時計算 USCS 與 AASHTO
    native_uscs_res, native_aashto_res = None, None
    try:
        from geolysis import soil_classifier as sc
        if hasattr(sc, "create_uscs_classifier"):
            clf = sc.create_uscs_classifier(liquid_limit=ll, plastic_limit=pl, fines=fines, sand=sand, d_10=d10, d_30=d30, d_60=d60, organic=organic)
            native_uscs_res = clf.classify()
        if hasattr(sc, "create_aashto_classifier"):
            aclf = sc.create_aashto_classifier(liquid_limit=ll, plastic_limit=pl, fines=fines)
            native_aashto_res = aclf.classify()
    except Exception:
        pass

    a_line = 0.73 * (ll - 20.0)
    if fines >= 50.0:
        if organic:
            uscs_sym, uscs_desc = ("OH", "高塑性有機質黏土或粉土") if ll >= 50 else ("OL", "低塑性有機質粉土或黏土")
        else:
            if ll < 50.0:
                if is_np or pi < 4.0 or pi < a_line:
                    uscs_sym, uscs_desc = "ML", "無機低塑性粉土 (Inorganic Low Plasticity Silt)"
                elif 4.0 <= pi <= 7.0 and pi >= a_line:
                    uscs_sym, uscs_desc = "CL-ML", "低塑性粉質黏土 (Silty Clay)"
                else:
                    uscs_sym, uscs_desc = "CL", "無機低塑性黏土 (Lean Clay)"
            else:
                if pi >= a_line:
                    uscs_sym, uscs_desc = "CH", "無機高塑性黏土 (Fat Clay)"
                else:
                    uscs_sym, uscs_desc = "MH", "無機高塑性粉土或彈性粉土 (Elastic Silt)"
    else:
        prefix = "S" if sand >= gravel else "G"
        p_name = "砂土 (Sand)" if prefix == "S" else "礫石 (Gravel)"
        well_graded = (cu >= 6.0 and 1.0 <= cc <= 3.0) if prefix == "S" else (cu >= 4.0 and 1.0 <= cc <= 3.0)
        g_sym = "W" if well_graded else "P"
        f_sym = "C" if (not is_np and pi >= a_line and pi > 7.0) else "M"
        
        if fines < 5.0:
            uscs_sym = f"{prefix}{g_sym}"
            uscs_desc = f"級配良好{p_name}" if g_sym == "W" else f"級配不良{p_name}"
        elif fines > 12.0:
            uscs_sym = f"{prefix}{f_sym}"
            uscs_desc = f"黏土質{p_name}" if f_sym == "C" else f"粉土質{p_name}"
        else:
            uscs_sym = f"{prefix}{g_sym}-{prefix}{f_sym}"
            uscs_desc = f"雙重符號：{p_name}含粉土/黏土"

    gi = (fines - 35.0) * (0.2 + 0.005 * (ll - 40.0)) + 0.01 * (fines - 15.0) * (pi - 10.0)
    if fines <= 35.0:
        if fines <= 15 and pi <= 6:
            aashto_sym, gi_val = "A-1-a", 0
        elif fines <= 25 and pi <= 6:
            aashto_sym, gi_val = "A-1-b", 0
        elif fines <= 10 and is_np:
            aashto_sym, gi_val = "A-3", 0
        else:
            if ll <= 40 and pi <= 10: aashto_sym = "A-2-4"
            elif ll > 40 and pi <= 10: aashto_sym = "A-2-5"
            elif ll <= 40 and pi > 10: aashto_sym = "A-2-6"
            else: aashto_sym = "A-2-7"
            gi_partial = 0.01 * (fines - 15.0) * (pi - 10.0)
            gi_val = max(0, round(gi_partial)) if aashto_sym in ["A-2-6", "A-2-7"] else 0
    else:
        gi_val = max(0, round(gi))
        if ll <= 40 and pi <= 10: aashto_sym = "A-4"
        elif ll > 40 and pi <= 10: aashto_sym = "A-5"
        elif ll <= 40 and pi > 10: aashto_sym = "A-6"
        else:
            aashto_sym = "A-7-5" if pi <= (ll - 30.0) else "A-7-6"

    res_col1, res_col2 = st.columns(2)
    with res_col1:
        st.success(f"#### USCS 分類結果：`{native_uscs_res or uscs_sym}`")
        st.write(f"**工程描述**：{uscs_desc} ｜ **A-Line 檢核值**：$PI_{{A}} = {max(0.0, a_line):.2f}$")
    with res_col2:
        st.info(f"#### AASHTO 分類結果：`{native_aashto_res or f'{aashto_sym} ({gi_val})'}`")
        st.write(f"**群指數 (Group Index, GI)**：`{gi_val}` (原始計算值: `{max(0.0, gi):.2f}`)")


# ==============================================================================
# 模組二：SPT 標準貫入試驗全修正 (geolysis.spt)
# ==============================================================================
with st.expander("🔨 模組二：SPT 標準貫入試驗全修正系統 (Energy & Overburden Corrections)", expanded=exp_2):
    st.subheader("🔨 SPT 標準貫入試驗全修正 (`geolysis.spt`)")
    col_spt1, col_spt2, col_spt3 = st.columns(3)
    
    with col_spt1:
        st.markdown("##### 1. 現場量測與器材四項參數")
        n_measured = st.number_input("現場量測 SPT-N 值", min_value=1, max_value=100, value=18)
        hammer_type = st.selectbox("錘擊型式與釋放機制 (Em)", [
            "自動錘 Automatic (Em = 0.80)",
            "安全錘 Safety (Em = 0.60)",
            "甜甜圈錘 Donut - 滑輪繩索 (Em = 0.45)",
            "自訂打擊效率 (Custom Em)"
        ])
        if "0.80" in hammer_type: em = 0.80
        elif "0.60" in hammer_type: em = 0.60
        elif "0.45" in hammer_type: em = 0.45
        else: em = st.number_input("自訂錘擊效率 Em (0~1)", 0.1, 1.0, 0.60, 0.05)
        
        borehole_dia = st.selectbox("鑽孔直徑 [mm] (CB)", ["65 ~ 115 mm (CB = 1.00)", "150 mm (CB = 1.05)", "200 mm (CB = 1.15)"])
        cb = 1.00 if "115" in borehole_dia else (1.05 if "150" in borehole_dia else 1.15)
        
        sampler_type = st.selectbox("取樣器型式 (CS)", ["標準取樣器含內襯管 Standard w/ liner (CS = 1.00)", "標準取樣器無內襯管 w/o liner (CS = 1.20)"])
        cs = 1.00 if "1.00" in sampler_type else 1.20
        
        rod_len = st.number_input("鑽桿總長度 [m] (自動計算 CR)", min_value=1.0, value=8.5, step=0.5)
        cr = 0.75 if rod_len < 3.0 else (0.80 if rod_len < 4.0 else (0.85 if rod_len < 6.0 else (0.95 if rod_len < 10.0 else 1.00)))
        st.caption(f"自動判定鑽桿長度修正係數 $C_R = {cr:.2f}$")

    with col_spt2:
        st.markdown("##### 2. 覆土應力與 7 大學者公式選擇")
        sigma_v = st.number_input("有效覆土應力 $\sigma'_v$ [kPa]", min_value=5.0, value=95.0, step=5.0)
        pa = 100.0
        cn_method = st.selectbox("選擇覆土壓力修正公式 ($C_N$ Method)", [
            "Liao & Whitman (1986)",
            "Skempton (1986) - 細砂",
            "Skempton (1986) - 粗砂",
            "Peck, Hanson & Thornburn (1974)",
            "Seed (1979)",
            "Kayen et al. (1992)",
            "Bazaraa (1967)"
        ])
        dilatancy_corr = st.checkbox("啟用飽和細砂/粉土剪脹修正 (Terzaghi & Peck, N' > 15 折減)", value=True)

    n60 = (n_measured * em * cb * cs * cr) / 0.60
    if "Liao" in cn_method: cn = math.sqrt(pa / sigma_v)
    elif "細砂" in cn_method: cn = 2.0 / (1.0 + (sigma_v / pa))
    elif "粗砂" in cn_method: cn = 1.7 / (0.7 + (sigma_v / pa))
    elif "Peck" in cn_method: cn = 0.77 * math.log10(2000.0 / sigma_v)
    elif "Seed" in cn_method: cn = 1.0 - 1.25 * math.log10(sigma_v / pa)
    elif "Kayen" in cn_method: cn = 2.2 / (1.2 + (sigma_v / pa))
    else: cn = 4.0 / (1.0 + 0.04 * sigma_v) if sigma_v <= 75.0 else 4.0 / (3.25 + 0.01 * sigma_v)
        
    cn = min(cn, 2.0)
    n1_60 = n60 * cn
    n1_60_corr = 15.0 + 0.5 * (n1_60 - 15.0) if (dilatancy_corr and n1_60 > 15.0) else n1_60

    with col_spt3:
        st.markdown("##### 3. SPT 全修正與衍生力學參數")
        st.metric("能量與器材修正值 $N_{60}$", f"{n60:.2f}")
        st.metric(f"覆土修正係數 $C_N$ ({cn_method.split(' ')[0]})", f"{cn:.3f}")
        st.metric("最終設計貫入值 $(N_1)'_{60}$", f"{n1_60_corr:.2f}", delta=f"未折減 (N1)60 = {n1_60:.2f}")
        phi_hat = min(45.0, math.sqrt(20.0 * n1_60_corr) + 15.0)
        st.info(f"💡 經驗公式推估內摩擦角 $\\phi$：**{phi_hat:.1f}°** (Hatanaka & Uchida)")

    st.markdown("---")
    st.markdown("##### 📊 全鑽孔剖面批次修正與繪圖")
    df_spt_default = pd.DataFrame({
        "深度_m": [1.5, 3.0, 4.5, 6.0, 7.5, 9.0, 10.5, 12.0],
        "現場_N": [6, 10, 14, 12, 20, 26, 32, 38],
        "有效應力_kPa": [27.0, 54.0, 81.0, 96.0, 111.0, 126.0, 141.0, 156.0],
        "鑽桿長_m": [3.0, 4.5, 6.0, 7.5, 9.0, 10.5, 12.0, 13.5]
    })
    df_spt_edit = st.data_editor(df_spt_default, num_rows="dynamic", use_container_width=True)
    
    def calc_spt_row(r):
        rl = r["鑽桿長_m"]
        cr_r = 0.75 if rl < 3 else (0.80 if rl < 4 else (0.85 if rl < 6 else (0.95 if rl < 10 else 1.0)))
        n60_r = (r["現場_N"] * em * cb * cs * cr_r) / 0.60
        cn_r = min(2.0, math.sqrt(100.0 / max(5.0, r["有效應力_kPa"])))
        return pd.Series([round(n60_r, 1), round(n60_r * cn_r, 1)])
    
    df_spt_edit[["N60", "(N1)60"]] = df_spt_edit.apply(calc_spt_row, axis=1)
    c_tbl, c_fig = st.columns([1, 1])
    c_tbl.dataframe(df_spt_edit, use_container_width=True)
    
    fig_spt = px.line(
        df_spt_edit, x=["現場_N", "N60", "(N1)60"], y="深度_m", markers=True,
        title="鑽孔深度 vs. 各階段修正 SPT-N 值剖面"
    )
    fig_spt.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="SPT N 值", yaxis_title="深度 (m)")
    c_fig.plotly_chart(fig_spt, use_container_width=True)


# ==============================================================================
# 模組三：容許承載力與沉陷控制 (geolysis.bearing_capacity.abc)
# ==============================================================================
with st.expander("📏 模組三：容許承載力與沉陷控制設計 (Allowable Bearing Capacity - ABC)", expanded=exp_3):
    st.subheader("📏 容許承載力與沉陷控制 (`geolysis.bearing_capacity.abc`)")
    c_abc1, c_abc2, c_abc3 = st.columns(3)
    
    with c_abc1:
        abc_method = st.radio("選擇計算方法", ["Bowles (1997)", "Meyerhof (1956)"])
        found_type = st.selectbox("基礎型式 (Foundation Type)", ["獨立/條形/方形基礎 (Isolated / Strip / Pad)", "筏式基礎 (Mat / Raft Foundation)"])
        sync_spt_abc = st.checkbox("自動帶入模組二之設計貫入值 $(N_1)'_{60}$", value=True)
        n_design = st.number_input("影響深度內設計平均 N 值", min_value=1.0, value=float(round(n1_60_corr, 1)) if sync_spt_abc else 18.0, step=1.0)
        
    with c_abc2:
        b_abc = st.number_input("基礎寬度 B [m]", min_value=0.3, value=2.5, step=0.1, key="b_abc")
        df_abc = st.number_input("基礎埋深 Df [m]", min_value=0.0, value=1.5, step=0.1, key="df_abc")
        tol_settlement = st.number_input("容許沉陷量 $S_e$ [mm]", min_value=5.0, max_value=100.0, value=25.0, step=5.0)
        
    with c_abc3:
        dw_abc = st.number_input("地下水位深度 $D_w$ [m] (自地表起算)", min_value=0.0, value=2.0, step=0.5)
        fd = min(1.0 + 0.33 * (df_abc / b_abc), 1.33)
        cw = 1.0 if dw_abc >= (df_abc + b_abc) else (0.5 if dw_abc <= df_abc else 0.5 + 0.5 * ((dw_abc - df_abc) / b_abc))
        s_ratio = tol_settlement / 25.0
        
        if "筏式" in found_type:
            qa = (n_design / 0.08) * fd * s_ratio * cw if "Bowles" in abc_method else (n_design / 0.12) * fd * s_ratio * cw
        else:
            if b_abc <= 1.22:
                qa = (n_design / 0.05) * fd * s_ratio * cw if "Bowles" in abc_method else (n_design / 0.08) * fd * s_ratio * cw
            else:
                factor = ((b_abc + 0.3) / b_abc) ** 2
                qa = (n_design / 0.08) * factor * fd * s_ratio * cw if "Bowles" in abc_method else (n_design / 0.12) * factor * fd * s_ratio * cw

        st.metric("深度修正因子 $f_d$ ｜ 地下水因子 $C_w$", f"fd={fd:.2f} | Cw={cw:.2f}")
        st.success(f"#### 容許承載力 $q_a$：`{qa:.2f} kPa`")
        st.caption(f"對應容許總載重 (以 $B \\times B$ 計)：**`{qa * b_abc * b_abc:.1f} kN`**")


# ==============================================================================
# 模組四：極限承載力四大理論 (geolysis.bearing_capacity.ubc)
# ==============================================================================
with st.expander("🏗️ 模組四：極限承載力四大理論完整版 (Ultimate Bearing Capacity - UBC)", expanded=exp_4):
    st.subheader("🏗️ 極限承載力四大理論 (`geolysis.bearing_capacity.ubc`)")
    u_col1, u_col2, u_col3, u_col4 = st.columns(4)
    
    with u_col1:
        st.markdown("##### 1. 理論與基礎幾何")
        ubc_theory = st.selectbox("選擇理論公式", ["Vesic (1973)", "Hansen (1970)", "Meyerhof (1963)", "Terzaghi (1943)"])
        f_shape = st.selectbox("基礎形狀 (Shape)", ["連續/條形 (Strip)", "方形 (Square)", "圓形 (Circle)", "矩形 (Rectangle)"])
        b_ubc = st.number_input("基礎寬度 B [m]", min_value=0.2, value=2.0, step=0.1)
        l_ubc = st.number_input("基礎長度 L [m]", min_value=0.2, value=3.0, step=0.1, disabled=(f_shape != "矩形 (Rectangle)"))
        if "方形" in f_shape or "圓形" in f_shape: l_ubc = b_ubc
        elif "連續" in f_shape: l_ubc = 10000.0
        df_ubc = st.number_input("基礎埋深 Df [m]", min_value=0.0, value=1.5, step=0.1)

    with u_col2:
        st.markdown("##### 2. 土壤與地下水參數")
        sync_phi_ubc = st.checkbox("帶入模組二估算之內摩擦角 ϕ", value=False)
        c_ubc = st.number_input("凝聚力 c [kPa]", min_value=0.0, value=15.0, step=1.0)
        phi_ubc = st.number_input("內摩擦角 ϕ [度]", min_value=0.0, max_value=48.0, value=float(round(phi_hat, 1)) if sync_phi_ubc else 30.0, step=1.0)
        gamma_ubc = st.number_input("濕單位重 γ [kN/m³]", min_value=10.0, value=18.5, step=0.5)
        gamma_sat = st.number_input("飽和單位重 γ_sat [kN/m³]", min_value=12.0, value=20.0, step=0.5)
        dw_ubc = st.number_input("地下水位深度 Dw [m]", min_value=0.0, value=1.2, step=0.2)
        fs_ubc = st.number_input("安全係數 (FS)", min_value=1.0, value=3.0, step=0.5)

    with u_col3:
        st.markdown("##### 3. 偏心與傾斜載重")
        eb = st.number_input("寬度方向偏心距 $e_B$ [m]", min_value=0.0, max_value=b_ubc/2.1, value=0.0, step=0.05)
        el = st.number_input("長度方向偏心距 $e_L$ [m]", min_value=0.0, max_value=l_ubc/2.1, value=0.0, step=0.05)
        alpha_deg = st.number_input("載重傾斜角 α (與垂直線夾角) [度]", min_value=0.0, max_value=45.0, value=0.0, step=1.0)
        beta_deg = st.number_input("基底傾斜角 β [度]", min_value=0.0, max_value=45.0, value=0.0, step=1.0)
        omega_deg = st.number_input("地面坡角 ω [度]", min_value=0.0, max_value=45.0, value=0.0, step=1.0)

    b_eff = b_ubc - 2.0 * eb
    l_eff = l_ubc - 2.0 * el
    area_eff = (math.pi * (b_eff / 2.0) ** 2) if "圓形" in f_shape else (b_eff * l_eff if "連續" not in f_shape else b_eff * 1.0)

    gamma_w = 9.81
    gamma_sub = max(1.0, gamma_sat - gamma_w)
    if dw_ubc <= df_ubc:
        q_overburden = gamma_ubc * dw_ubc + gamma_sub * (df_ubc - dw_ubc)
        gamma_below = gamma_sub
        water_case = "Case 1: 水位位於基礎底面之上 (覆土與基底下部土壤皆折減)"
    elif dw_ubc < (df_ubc + b_ubc):
        q_overburden = gamma_ubc * df_ubc
        d_water_below = dw_ubc - df_ubc
        gamma_below = gamma_sub + ((d_water_below / b_ubc) * (gamma_ubc - gamma_sub))
        water_case = "Case 2: 水位位於基底下方影響深度 B 內 (基底下部單位重線性內插折減)"
    else:
        q_overburden = gamma_ubc * df_ubc
        gamma_below = gamma_ubc
        water_case = "Case 3: 水位深於影響範圍 Dw >= Df + B (無地下水折減)"

    phi_r = math.radians(phi_ubc)
    if phi_ubc == 0:
        nq = 1.0
        nc = 5.7 if "Terzaghi" in ubc_theory else 5.14
        ng = 0.0
    else:
        if "Terzaghi" in ubc_theory:
            a_theta = math.exp((0.75 * math.pi - phi_r / 2.0) * math.tan(phi_r))
            nq = (a_theta ** 2) / (2.0 * (math.cos(math.radians(45.0 + phi_ubc / 2.0)) ** 2))
            nc = (nq - 1.0) / math.tan(phi_r)
            ng = 2.0 * (nq + 1.0) * math.tan(phi_r) / (1.0 + 0.4 * math.sin(4.0 * phi_r))
        else:
            nq = math.exp(math.pi * math.tan(phi_r)) * (math.tan(math.radians(45.0) + phi_r / 2.0) ** 2)
            nc = (nq - 1.0) / math.tan(phi_r)
            if "Meyerhof" in ubc_theory: ng = (nq - 1.0) * math.tan(1.4 * phi_r)
            elif "Hansen" in ubc_theory: ng = 1.5 * (nq - 1.0) * math.tan(phi_r)
            else: ng = 2.0 * (nq + 1.0) * math.tan(phi_r)

    bl_ratio = 0.0 if "連續" in f_shape else (b_eff / l_eff)
    if "Terzaghi" in ubc_theory:
        sc = 1.0 if "連續" in f_shape else (1.3 if ("方形" in f_shape or "圓形" in f_shape) else 1.0 + 0.3 * bl_ratio)
        sq = 1.0
        sg = 1.0 if "連續" in f_shape else (0.8 if "方形" in f_shape else (0.6 if "圓形" in f_shape else max(0.6, 1.0 - 0.2 * bl_ratio)))
        dc = dq = dg = ic = iq = ig = bc = bq = bg = gc = gq = gg = 1.0
    else:
        sc = 1.0 + bl_ratio * (nq / nc) if phi_ubc > 0 else 1.0 + 0.2 * bl_ratio
        sq = 1.0 + bl_ratio * math.tan(phi_r)
        sg = max(0.6, 1.0 - 0.4 * bl_ratio)
        
        k_df = (df_ubc / b_eff) if (df_ubc / b_eff) <= 1.0 else math.atan(df_ubc / b_eff)
        dc = 1.0 + 0.4 * k_df
        dq = 1.0 + 2.0 * math.tan(phi_r) * ((1.0 - math.sin(phi_r)) ** 2) * k_df
        dg = 1.0
        
        ic = iq = (1.0 - alpha_deg / 90.0) ** 2
        ig = (1.0 - alpha_deg / phi_ubc) ** 2 if (phi_ubc > 0 and alpha_deg < phi_ubc) else 0.0
        
        bc = bq = (1.0 - beta_deg / 147.0) ** 2
        bg = bc
        gc = gq = (1.0 - math.tan(math.radians(omega_deg))) ** 2
        gg = gq

    term_c = c_ubc * nc * sc * dc * ic * bc * gc
    term_q = q_overburden * nq * sq * dq * iq * bq * gq
    term_g = 0.5 * gamma_below * b_eff * ng * sg * dg * ig * bg * gg
    
    q_ult = term_c + term_q + term_g
    q_net_ult = max(0.0, q_ult - q_overburden)
    q_allow_gross = q_ult / fs_ubc

    with u_col4:
        st.markdown("##### 4. 承載力計算成果")
        st.metric("總極限承載力 $q_{ult}$", f"{q_ult:.2f} kPa")
        st.metric("淨極限承載力 $q_{net(u)}$", f"{q_net_ult:.2f} kPa")
        st.metric(f"總容許承載力 $q_{{all}}$ (FS={fs_ubc})", f"{q_allow_gross:.2f} kPa")
        st.metric("極限總支承力 $Q_{ult} = q_{ult} \\times A'$", f"{q_ult * area_eff:.1f} kN")

    st.info(f"💧 **地下水狀態判定**：{water_case} ｜ 有效覆土壓力 $q' = {q_overburden:.2f}\\text{{ kPa}}$ ｜ 基底下部有效單位重 $\\gamma' = {gamma_below:.2f}\\text{{ kN/m}}^3$")

    st.markdown("##### 📋 完整承載力修正係數明細表")
    df_factors = pd.DataFrame({
        "分項名稱": ["凝聚力項 (Cohesion Term, c)", "覆土壓力項 (Overburden Term, q)", "基底單位重項 (Width/Weight Term, γ)"],
        "承載力係數 (N)": [f"Nc = {nc:.2f}", f"Nq = {nq:.2f}", f"Nγ = {ng:.2f}"],
        "形狀係數 (s)": [f"sc = {sc:.3f}", f"sq = {sq:.3f}", f"sγ = {sg:.3f}"],
        "深度係數 (d)": [f"dc = {dc:.3f}", f"dq = {dq:.3f}", f"dγ = {dg:.3f}"],
        "載重傾斜係數 (i)": [f"ic = {ic:.3f}", f"iq = {iq:.3f}", f"iγ = {ig:.3f}"],
        "基底/地面傾斜 (b, g)": [f"bc={bc:.2f}, gc={gc:.2f}", f"bq={bq:.2f}, gq={gq:.2f}", f"bγ={bg:.2f}, gγ={gg:.2f}"],
        "各分項貢獻值 [kPa]": [f"{term_c:.2f} ({term_c/max(1,q_ult)*100:.1f}%)", f"{term_q:.2f} ({term_q/max(1,q_ult)*100:.1f}%)", f"{term_g:.2f} ({term_g/max(1,q_ult)*100:.1f}%)"]
    })
    st.table(df_factors)
