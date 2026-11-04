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
