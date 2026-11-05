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
