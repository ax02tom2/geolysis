"""Streamlit UI for engineering module 4."""
import streamlit as st
import logging
import pandas as pd
from io import StringIO
from geolysis_engine import consolidation_time_rate, secondary_compression_settlement, immediate_elastic_settlement, excavation_rebound_recompression, differential_settlement, usace_meyerhof_settlement_allowable, burland_burbidge_2025_settlement, burland_burbidge_2025_allowable_pressure, burland_burbidge_average_n60_from_profile, consolidation_allowable_pressure, consolidation_allowable_pressure_layers, boussinesq_rectangular_center_factor, usace_settlement_design_pressure


def render_module_4(expanded=False):
    # ==============================================================================
    # 模組四：容許承載力與沉陷控制
    # ==============================================================================
    with st.expander("📏 模組四：容許承載力與沉陷控制", expanded):
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
                q4=st.number_input("目前基礎底 gross 壓力 q；偏心時輸入 qeq [kPa]",1.0,5000.0,150.0,5.0,key='m4_bb_q')
                target_bb4=st.number_input("容許總沉陷量 [mm]",1.0,200.0,25.0,1.0,key='m4_bb_target')
                qult4=st.number_input("模組五 gross 極限承載力 qult [kPa]（0＝不套用上限）",0.0,20000.0,0.0,10.0,key='m4_bb_qult')
                fs_bb4=st.number_input("承載力安全係數 FS",1.1,10.0,3.0,0.1,key='m4_bb_fs')
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
                pressure_check4=None
                if qult4>0:
                    pressure_check4=usace_settlement_design_pressure(
                        gross_equivalent_pressure_kpa=q4,
                        ultimate_bearing_kpa=qult4,
                        factor_of_safety=fs_bb4)
                    q4_used=pressure_check4['design_pressure_kpa']
                    capacity_limit4=pressure_check4['capacity_pressure_limit_kpa']
                    max_q4=min(5000.0,capacity_limit4)
                    if pressure_check4['capacity_limit_governs']:
                        st.warning(f"輸入 q／qeq={q4:.1f} kPa 高於 qult/FS={capacity_limit4:.1f} kPa；依 USACE 2025 沉陷壓力限制，計算改採 qult/FS。")
                    st.caption(f"承載力壓力上限：qult/FS = {qult4:.1f}/{fs_bb4:.2f} = {capacity_limit4:.1f} kPa。")
                else:
                    q4_used=q4
                    max_q4=5000.0
                    capacity_limit4=None
                    st.warning("尚未輸入模組五 gross qult；目前只做沉陷估算，尚未套用 USACE 2025 的 qult/FS 承載力壓力上限。")
                r=burland_burbidge_2025_settlement(gross_pressure_kpa=q4_used,**bb_args)
                qa_bb=burland_burbidge_2025_allowable_pressure(target_settlement_mm=target_bb4,max_pressure_kpa=max_q4,**bb_args)
                st.metric("沉陷＋承載力控制容許總接觸壓力",f"{qa_bb['qa_settlement_gross_kpa']:.1f} kPa")
                st.write(f"目前 q 採用值 = {q4_used:.1f} kPa 時，估算沉陷 = {r['settlement_mm']:.1f} mm ｜ 容許沉陷 = {target_bb4:.1f} mm")
                st.write(f"影響深度 Zi = {r['influence_depth_m']:.2f} m ｜ N60 採用值 = {r['N60_average_used']:.2f} ｜ Ic = {r['Ic_tsf_inv']:.5f} tsf⁻¹")
                st.write(f"形狀係數 C1 = {r['C1_shape']:.3f} ｜ 層厚係數 C2 = {r['C2_layer']:.3f} ｜ 時間係數 C3 = {r['C3_time']:.3f} ｜ {r['regime']}")
                st.caption(r['method'])
                st.warning(r['limitations'])
                if qa_bb['pressure_search_limit_reached'] and qult4>0 and capacity_limit4 is not None and capacity_limit4<=5000:
                    st.caption("容許壓力受模組五 qult/FS 上限控制；在該上限內，預估沉陷仍未超過目標值。")
                elif qa_bb['pressure_search_limit_reached']:
                    st.warning("5,000 kPa 搜尋上限內仍未達容許沉陷量，結果受搜尋上限控制，請檢查輸入。")
                if qa_bb['no_feasible_pressure']: st.error("即使不增加基礎接觸壓力，公式中的初始應力沉陷項仍已超過容許沉陷量；目前沒有可行的正接觸壓力解，請檢查 σ′0、N60、目標沉陷與方法適用性。")
                st.info("本方法使用 gross q／偏心時的 qeq，並以 gross qult/FS 作承載力上限；偏心基礎不可輸入 V/A 的平均壓力取代 qeq。若未輸入 qult，結果僅受沉陷控制。請確認模組五與本頁採用相同基礎尺寸、埋深、地下水及地層條件。")
            except Exception as exc:
                logging.exception("Unhandled application calculation error")
                st.error(f"Burland–Burbidge 沉陷估算失敗：{exc}")
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
            except Exception as exc:
                logging.exception("Unhandled application calculation error")
                st.error(f"砂土容許承載力估算失敗：{exc}")
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
                    if layers_text4.strip():
                        st.warning("目前輸入的是多層壓縮土。USACE EM 1110-1-1905（2025）表 7-11 要求逐一判定各壓縮層的 Cv，並依各層排水邊界計算 Hdr；不能把所有層厚加總後套用單一 Cv 與排水條件。因此本版不提供多層情況的時間速率及次壓縮數值，避免產生具誤導性的結果。")
                        st.caption("請先以單一、均質且排水條件一致的壓縮層使用下方時間估算；多層分析需補齊每層 Cv、排水路徑、次壓縮指數 Cα 與主固結完成時孔隙比後，才能逐層計算並在共同經過時間下整合。")
                    else:
                        st.caption("依 USACE EM 1110-1-1905（2025）第 7-18、7-19 節；U–Tv 採圖 7-16 表列點線性內插。Cv 應由固結試驗或現地試驗取得；此處以單一均質壓縮層作一維估算。")
                        rt_a,rt_b,rt_c=st.columns(3)
                        with rt_a:
                            cv4=st.number_input("固結係數 Cv [m²/day]",min_value=0.000001,max_value=10.0,value=0.005,format="%.6f",key="m4c_cv")
                            drainage4=st.selectbox("排水條件",["double","single"],format_func=lambda x:"雙向排水（Hdr=H/2）" if x=="double" else "單向排水（Hdr=H）",key="m4c_drainage")
                        with rt_b:
                            u_target4=st.number_input("目標平均固結度 U [%]",min_value=1.0,max_value=99.4,value=90.0,step=1.0,key="m4c_u")
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
                                t100_est4=consolidation_time_rate(primary_settlement_mm=primary_total4,
                                    layer_thickness_m=representative_H4,cv_m2_per_day=cv4,
                                    target_degree_percent=99.4,drainage=drainage4)
                                st.caption(f"未提供固結試驗 t100 時，先以 USACE 圖 7-16 的 U=99.4%（Tv≈2.0）估算 t1；此值只是近似，正式分析應以試驗判讀 t100 取代。估算 t1≈{t100_est4['time_to_target_years']:.2f} 年。")
                                t1_years4=st.number_input("次壓縮起算時間 t1 [年]",min_value=0.001,max_value=100.0,value=min(100.0,max(0.01,t100_est4['time_to_target_years'])),step=0.1,key="m4c_t1")
                                t2_years4=st.number_input("次壓縮計算終止時間 t2 [年]",min_value=0.01,max_value=200.0,value=max(50.0,t1_years4+0.01),step=1.0,key="m4c_t2")
                                sec4=secondary_compression_settlement(layer_thickness_m=representative_H4,
                                    secondary_compression_index=ca4,void_ratio_at_primary_end=ep4,
                                    time_start_days=t1_years4*365.25,time_end_days=t2_years4*365.25)
                                st.write(f"次壓縮沉陷 δs ≈ **{sec4['secondary_settlement_mm']:.2f} mm**；代表層長期總沉陷（最終主固結＋次壓縮）≈ **{primary_total4+sec4['secondary_settlement_mm']:.2f} mm**。")
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
            except Exception as exc:
                logging.exception("Unhandled application calculation error")
                st.error(f"黏土主固結估算失敗：{exc}")
    
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
