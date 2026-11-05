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

