"""Streamlit UI for engineering module 4."""
import streamlit as st
import logging
import pandas as pd
from io import StringIO
from geolysis_engine import consolidation_time_rate, consolidation_time_rate_layers, consolidation_settlement_layers, consolidation_settlement_1d, secondary_compression_settlement, immediate_elastic_settlement, excavation_rebound_recompression, excavation_rebound_recompression_layers, differential_settlement, usace_meyerhof_settlement_allowable, burland_burbidge_2025_settlement, burland_burbidge_2025_allowable_pressure, burland_burbidge_average_n60_from_profile, burland_burbidge_average_n60_from_ground_profile, consolidation_allowable_pressure, consolidation_allowable_pressure_layers, consolidation_settlement_layers_from_stress_profile, boussinesq_rectangular_center_factor, usace_settlement_design_pressure, dmt_settlement_2025, dmt_modulus_settlement_2025, schmertmann_cpt_settlement_2025, menard_rousseau_pmt_settlement_2025




def _module5_transfer_value(*, key_prefix, label, field, width_m, length_m,
        footing_type=None, depth_m=None):
    """Return a current Module 5 capacity value only after geometry/context confirmation."""
    transfer=st.session_state.get("m5_bearing_transfer")
    if not transfer:
        return None
    width_match=abs(float(width_m)-float(transfer["B_m"]))<=0.01
    length_match=abs(float(length_m)-float(transfer["L_m"]))<=0.01
    depth_match=(depth_m is None or abs(float(depth_m)-float(transfer["Df_m"]))<=0.01)
    type_match=(footing_type is None or str(footing_type)==str(transfer["footing_type"]))
    if not (width_match and length_match and depth_match and type_match):
        st.warning(
            f"Module 4 幾何與 Module 5 結果不一致，不能自動帶入 {label}。"
            f"Module 5：B={transfer['B_m']:.2f} m、L={transfer['L_m']:.2f} m、"
            f"Df={transfer['Df_m']:.2f} m、型式={transfer['footing_type']}；"
            f"請統一基礎尺寸／埋深／型式，或改用手動輸入。"
        )
        return None
    transfer_id=str(transfer["transfer_id"])
    use_value=st.checkbox(
        f"使用 Module 5 目前有效的 {label}（{float(transfer[field]):.1f} kPa）",
        value=False,key=f"{key_prefix}_use_m5_{transfer_id}")
    if not use_value:
        return None
    st.caption(
        f"來源：Module 5 {transfer['theory']}（主承載力水平基底／地表分析）；qult={transfer['qult_gross_kpa']:.1f} kPa；"
        f"qa,net={transfer['qa_net_kpa']:.1f} kPa；qeq={transfer['qeq_gross_kpa']:.1f} kPa；"
        f"FS_bearing={transfer['FS_bearing']:.2f}。"
    )
    if not transfer.get("passes_bearing",False):
        st.warning("Module 5 實際承載力 FS 未達 3.0；此數值僅供沉陷壓力上限比較，不代表承載力設計合格。")
    context_key=f"{key_prefix}_conditions_{transfer_id}_{float(width_m):.2f}_{float(length_m):.2f}_{float(depth_m or 0.0):.2f}_{footing_type or 'any'}"
    same_conditions=st.checkbox(
        "已確認基礎埋深、地下水位、地層剖面及載重條件與 Module 5 相同，且本沉陷方法適用於水平基底／地表與中央垂直荷載",
        value=False,key=context_key)
    if not same_conditions:
        st.warning("尚未確認沉陷分析與 Module 5 的埋深、地下水位、地層及載重條件一致；目前不套用跨模組承載力。")
        return None
    return float(transfer[field])


def render_module_4(expanded=False):
    # ==============================================================================
    # 模組四：容許承載力與沉陷控制
    # ==============================================================================
    with st.expander("📏 模組四：容許承載力與沉陷控制", expanded):
        st.subheader("📏 模組四：容許承載力與沉陷控制")
        m5_transfer4=st.session_state.get("m5_bearing_transfer")
        if m5_transfer4:
            st.caption(f"已取得 Module 5 有效承載力結果：qult={m5_transfer4['qult_gross_kpa']:.1f} kPa、qa,net(FS=3.0)={m5_transfer4['qa_net_kpa']:.1f} kPa；基礎 B×L={m5_transfer4['B_m']:.2f}×{m5_transfer4['L_m']:.2f} m、Df={m5_transfer4['Df_m']:.2f} m。各沉陷方法仍須確認幾何、水位與地層條件相同後，才可選擇帶入。")
        else:
            st.caption("完成 Module 5 極限承載力計算、確認設計總垂直力並通過偏心接觸檢核後，可將有效 qult／qa,net 帶入本模組作沉陷壓力上限。")
        method4=st.selectbox("分析方法",["砂土／礫土：Burland–Burbidge SPT 法（USACE 2025）","DMT：增量拘束模數法（USACE 2025）","CPT：Schmertmann 沉陷法（USACE 2025）","PMT：Ménard–Rousseau 法（USACE 2025）","砂土：Meyerhof SPT 舊版經驗式（USACE 1992）","黏土：一維主固結沉陷控制法"],key='m4_method')
        if method4.startswith('砂土／礫土'):
            st.caption("依 USACE EM 1110-1-1905（2025）第 7-13 節，採 Burland & Burbidge SPT 法；使用基礎底至影響深度內的平均 N60，不是 (N1)60。可直接連結模組三剖面，並依基礎埋深將地表深度換算為基礎底下深度。")
            a,b,c=st.columns(3)
            with a:
                n4=st.number_input("影響深度內平均 N60",1.0,100.0,20.0,1.0,key='m4_bb_n60')
                width4=st.number_input("基礎短邊 B [m]",0.3,30.0,2.0,0.1,key='m4_bb_b')
                length4=st.number_input("基礎長邊 L [m]",0.3,100.0,3.0,0.1,key='m4_bb_l')
            with b:
                q4=st.number_input("目前基礎底 gross 壓力 q；偏心時輸入 qeq [kPa]",1.0,5000.0,150.0,5.0,key='m4_bb_q')
                target_bb4=st.number_input("容許總沉陷量 [mm]",1.0,200.0,25.0,1.0,key='m4_bb_target')
                fs_bb4=st.number_input("承載力安全係數 FS",1.1,10.0,3.0,0.1,key='m4_bb_fs')
                sig04=st.number_input("影響深度內平均初始有效應力 [kPa]",0.0,3000.0,100.0,5.0,key='m4_bb_sig0')
                sigp4=st.number_input("先期固結壓力 σ′p [kPa]（正常固結時採 σ′0）",1.0,5000.0,100.0,5.0,key='m4_bb_sigp')
            with c:
                hs4=st.number_input("基礎底下砂／礫層厚度 Hs [m]",0.1,100.0,10.0,0.5,key='m4_bb_hs')
                df_bb4=st.number_input("基礎埋深 Df [m]（連結模組三深度用）",0.0,30.0,1.5,0.1,key='m4_bb_df')
                transfer_qult4=_module5_transfer_value(key_prefix="m4_bb",label="gross 極限承載力 qult",field="qult_gross_kpa",width_m=width4,length_m=length4,depth_m=df_bb4)
                qult4=(transfer_qult4 if transfer_qult4 is not None else st.number_input("模組五 gross 極限承載力 qult [kPa]（0＝不套用上限）",0.0,20000.0,0.0,10.0,key='m4_bb_qult'))
                if qult4>0 and fs_bb4<3.0: st.warning("FS 低於 USACE EM 1110-1-1905（2025）表 2-1 靜力承載力最低值 3.0；可供比較計算，但不可標示為符合該手冊靜力承載力安全要求。")
                years4=st.number_input("載重作用時間 [年]",0.1,100.0,30.0,0.5,key='m4_bb_years')
                loadtype4=st.selectbox("載重型態",["static","fluctuating"],format_func=lambda x:"靜態" if x=="static" else "反覆／波動",key='m4_bb_load')
            profile_text4=st.text_area("選填：逐深度 N60 CSV（深度自基礎底向下；必要欄位 Depth_below_base_m、N60；可加 Burland_Material）",value="",height=90,key='m4_bb_profile',placeholder="Depth_below_base_m,N60,Burland_Material\n0.5,18,fine_sand_silt_saturated\n1.0,20,standard\n1.5,22,gravel_sandy_gravel")
            m3_profile_data4=st.session_state.get('m3_profile_result')
            use_m3_spt4=st.checkbox("直接使用模組三已校正 SPT 剖面（N60）",
                value=False,disabled=(m3_profile_data4 is None),key='m4_bb_use_m3_spt')
            if m3_profile_data4 is None:
                st.caption("尚無模組三有效 SPT 剖面；先在模組三輸入／上傳逐深度資料並完成修正後，此處即可直接帶入。")
            d,e=st.columns(2)
            with d:
                oc4=st.checkbox("超固結顆粒土（使用 σ′p 分段式）",key='m4_bb_oc')
                gravel4=st.checkbox("礫土／砂礫土（逐點 N60 × 1.25）",key='m4_bb_gravel')
            with e:
                fine_sat4=st.checkbox("地下水位以下飽和細砂／粉土（逐點 N60 > 15 套用膨脹修正）",key='m4_bb_finesat')
                ndecrease4=st.checkbox("N60 隨深度下降（Zi 改採 min(2B, 鬆弱層底深度)）",key='m4_bb_decrease')
            st.caption("若整個影響深度 Zi 均為同一材料，可使用全剖面修正勾選。混合地層可在模組三／手動 CSV 逐點填 Burland_Material：standard、fine_sand_silt_saturated 或 gravel_sandy_gravel；系統會依 USACE 第 7-13 節逐點修正 N60，再取算術平均。逐點分類與全剖面勾選不可同時使用。此處修正直接作用於 N60，不使用液化評估用的 (N1)60。")
            loose_layer4=None
            if ndecrease4:
                loose_layer4=st.number_input("鬆弱層底深度（自基礎底向下）[m]",min_value=0.1,max_value=100.0,value=float(hs4),step=0.1,key="m4_bb_loose_layer_depth")
                st.caption("此深度與砂／礫層總厚度 Hs 是不同參數；只有鬆弱層底恰好等於砂／礫層底時兩者才相同。預設值僅供起始輸入，請依 N60 剖面確認。影響深度 Zi=min(2B,鬆弱層底深度)，而 C2 仍使用總砂／礫層厚度 Hs。")
                st.caption("若使用單一平均 N60 輸入，請自行確認該平均值只取自基礎底至上述 Zi 的有效測點；若使用剖面 CSV 或模組三連結，系統會依 Zi 自動篩選。")
            try:
                n60_used4=n4
                if use_m3_spt4:
                    m3_has_burland_material4=('Burland_Material' in m3_profile_data4.columns and
                        m3_profile_data4['Burland_Material'].notna().any() and
                        m3_profile_data4['Burland_Material'].fillna('').astype(str).str.strip().ne('').any())
                    avg_bb=burland_burbidge_average_n60_from_ground_profile(
                        m3_profile_data4.to_dict('records'),foundation_depth_m=df_bb4,
                        width_m=width4,granular_layer_thickness_m=hs4,n_decreases_with_depth=ndecrease4,
                        loose_layer_thickness_m=loose_layer4,
                        gravel_adjustment=(gravel4 if not m3_has_burland_material4 else False),
                        fine_sand_saturated=(fine_sat4 if not m3_has_burland_material4 else False))
                    n60_used4=avg_bb['N60_average']
                    st.caption(f"已由模組三地表深度扣除 Df={df_bb4:.2f} m，依 Zi={avg_bb['influence_depth_m']:.2f} m 篩選 {avg_bb['selected_count']} 筆有效 N60；{avg_bb['adjustments']}，平均 N60={n60_used4:.2f}。")
                    if m3_has_burland_material4 and (gravel4 or fine_sat4):
                        st.warning("本次使用模組三逐點 Burland_Material；全剖面礫土／細砂勾選不套用，避免重複修正。")
                    for _quality_warning in avg_bb.get('data_quality_warnings', []): st.warning(_quality_warning)
                    st.dataframe(pd.DataFrame([
                        {'基礎底下深度 z [m]':row[0],'原始 N60':row[1],
                         '逐點修正後 N60':row[2],'Burland 修正':adj}
                        for row,adj in zip(avg_bb['selected_profile'],avg_bb.get('selected_adjustments',[]))
                    ]),hide_index=True,use_container_width=True)
                elif profile_text4.strip():
                    prof_bb=pd.read_csv(StringIO(profile_text4))
                    manual_has_burland_material4=('Burland_Material' in prof_bb.columns and
                        prof_bb['Burland_Material'].notna().any() and
                        prof_bb['Burland_Material'].fillna('').astype(str).str.strip().ne('').any())
                    avg_bb=burland_burbidge_average_n60_from_profile(prof_bb.to_dict('records'),
                        width_m=width4,granular_layer_thickness_m=hs4,n_decreases_with_depth=ndecrease4,
                        loose_layer_thickness_m=loose_layer4,
                        gravel_adjustment=(gravel4 if not manual_has_burland_material4 else False),
                        fine_sand_saturated=(fine_sat4 if not manual_has_burland_material4 else False))
                    n60_used4=avg_bb['N60_average']
                    st.caption(f"依 Zi={avg_bb['influence_depth_m']:.2f} m 篩選 {avg_bb['selected_count']} 筆測點；{avg_bb['adjustments']}，平均 N60={n60_used4:.2f}。")
                    if manual_has_burland_material4 and (gravel4 or fine_sat4):
                        st.warning("本次使用 CSV 逐點 Burland_Material；全剖面礫土／細砂勾選不套用，避免重複修正。")
                    for _quality_warning in avg_bb.get('data_quality_warnings', []): st.warning(_quality_warning)
                    st.dataframe(pd.DataFrame([
                        {'基礎底下深度 z [m]':row[0],'原始 N60':row[1],
                         '逐點修正後 N60':row[2],'Burland 修正':adj}
                        for row,adj in zip(avg_bb['selected_profile'],avg_bb.get('selected_adjustments',[]))
                    ]),hide_index=True,use_container_width=True)
                elif gravel4 or fine_sat4:
                    st.warning("目前以單一平均 N60 輸入；粒料修正將套用於平均值作近似。正式計算應先逐筆修正影響深度內的 N60，再計算算術平均；可使用模組三剖面或貼上 CSV。")
                zi_bb4=1.43*(width4/0.3048)**0.7*0.3048
                if ndecrease4: zi_bb4=min(2.0*width4,loose_layer4)
                if hs4 < zi_bb4-1e-9 and not ndecrease4:
                    st.warning("Hs 小於 Zi，依 USACE 式 7-33 套用有限厚度修正 C2。請確認下伏層的變形特性與有限厚度修正假設相符；若下伏層仍有顯著壓縮或較軟，C2 折減可能低估沉陷，應改用分層 CPT／DMT／固結沉陷分析。")
                bb_args=dict(n60_average=n60_used4,width_m=width4,length_m=length4,
                    initial_effective_stress_kpa=sig04,preconsolidation_stress_kpa=sigp4,
                    granular_layer_thickness_m=hs4,years=years4,load_type=loadtype4,
                    overconsolidated=oc4,gravel_adjustment=(gravel4 if not profile_text4.strip() and not use_m3_spt4 else False),
                    fine_sand_saturated=(fine_sat4 if not profile_text4.strip() and not use_m3_spt4 else False),
                    n_decreases_with_depth=ndecrease4,loose_layer_thickness_m=loose_layer4)
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
        elif method4.startswith('DMT：'):
            st.caption("依 USACE EM 1110-1-1905（2025）式 3-41、4-13～4-15、7-10 及表 7-4。輸入經儀器校正後的 DMT corrected p0、p1、u0 與原位初始有效應力；系統逐層計算 ID、KD、ED、修正係數 RM、MDMT，再以 Boussinesq 中心線應力增量計算沉陷。")
            a,b,c=st.columns(3)
            with a:
                dmtB=st.number_input("基礎短邊 B [m]",0.3,30.0,2.0,0.1,key="m4_dmt_b")
                dmtL=st.number_input("基礎長邊 L [m]",0.3,100.0,2.0,0.1,key="m4_dmt_l")
                dmt_type=st.selectbox("基礎型式",["isolated","continuous"],format_func=lambda x:"獨立／矩形基礎" if x=="isolated" else "連續基礎（條形）",key="m4_dmt_type")
            with b:
                dmtq=st.number_input("基礎底 gross q；偏心時輸入 qeq [kPa]",1.0,5000.0,150.0,5.0,key="m4_dmt_q")
                dmtsig=st.number_input("基礎底初始有效應力 σ′zD [kPa]",0.0,3000.0,100.0,5.0,key="m4_dmt_sig")
                dmt_transfer_qult=_module5_transfer_value(key_prefix="m4_dmt",label="gross 極限承載力 qult",field="qult_gross_kpa",width_m=dmtB,length_m=dmtL,footing_type=dmt_type)
                dmtqult=(dmt_transfer_qult if dmt_transfer_qult is not None else st.number_input("模組五 gross qult [kPa]（0＝不套用上限）",0.0,20000.0,0.0,10.0,key="m4_dmt_qult"))
            with c:
                dmtfs=st.number_input("承載力安全係數 FS",1.1,10.0,3.0,0.1,key="m4_dmt_fs")
                if dmtqult>0 and dmtfs<3.0: st.warning("FS 低於 USACE EM 1110-1-1905（2025）表 2-1 靜力承載力最低值 3.0；可供比較計算，但不可標示為符合該手冊靜力承載力安全要求。")
                dmtTarget=st.number_input("參考容許總沉陷 [mm]",1.0,200.0,25.0,1.0,key="m4_dmt_target")
            dmt_mode=st.selectbox("DMT 輸入資料型式",["corrected","MDMT"],format_func=lambda x:"corrected p0／p1／u0 讀值（由系統推算 MDMT）" if x=="corrected" else "直接輸入試驗解讀後 MDMT",key="m4_dmt_mode")
            dmt_text=st.text_area("DMT 分層 CSV（由基礎底開始，逐層向下）",
                value="",height=130,key="m4_dmt_layers",
                placeholder="corrected：Layer,thickness_m,p0_bar,p1_bar,u0_bar,sigma_v0_eff_bar；MDMT：Layer,depth_center_m,thickness_m,MDMT_kpa,I_sigma")
            st.caption("corrected 模式須輸入儀器校正後 p0/p1、u0、σ′v0（bar）；MDMT 模式直接輸入試驗解讀後拘束模數（kPa），可選填 I_sigma 以採用已核對的文獻／圖表值。")
            st.caption("MDMT 模式的 depth_center_m 是各層中心點距基礎底的深度，不是層底深度；若原始表列的是層底深度 z_bottom，請換算 depth_center=z_bottom−thickness/2。層厚區間須連續且不得重疊，並應涵蓋計算影響深度。")
            try:
                if not dmt_text.strip():
                    st.info("請貼上 DMT 分層資料後計算；系統不會用示範模數代替現場試驗。")
                else:
                    dmt_layers=pd.read_csv(StringIO(dmt_text)).to_dict("records")
                    if dmt_mode=="MDMT":
                        result_dmt=dmt_modulus_settlement_2025(
                            layers=dmt_layers,footing_width_m=dmtB,footing_length_m=dmtL,
                            gross_pressure_kpa=dmtq,base_effective_stress_kpa=dmtsig,
                            ultimate_bearing_kpa=(dmtqult if dmtqult>0 else None),
                            factor_of_safety=dmtfs,footing_type=dmt_type)
                    else:
                        result_dmt=dmt_settlement_2025(
                            layers=dmt_layers,footing_width_m=dmtB,footing_length_m=dmtL,
                            gross_pressure_kpa=dmtq,base_effective_stress_kpa=dmtsig,
                            ultimate_bearing_kpa=(dmtqult if dmtqult>0 else None),
                            factor_of_safety=dmtfs,footing_type=dmt_type)
                    st.metric("DMT 估算總沉陷",f"{result_dmt['settlement_mm']:.2f} mm")
                    st.write(f"採用 gross 壓力 = {result_dmt['gross_pressure_used_kpa']:.1f} kPa ｜ 新增壓力 = {result_dmt['net_pressure_increment_kpa']:.1f} kPa ｜ 參考容許沉陷 = {dmtTarget:.1f} mm")
                    if result_dmt["capacity_limit_governs"]:
                        st.warning(f"輸入 gross q／qeq={dmtq:.1f} kPa 高於 qult/FS={result_dmt['capacity_pressure_limit_kpa']:.1f} kPa；依 USACE 2025 壓力限制，沉陷計算已改採 qult/FS。")
                    if result_dmt.get("profile_ends_at_minimum_depth"):
                        st.warning(
                            f"本次 DMT 剖面僅達最低影響深度 {result_dmt['influence_depth_required_m']:.2f} m。"
                            "USACE Table 7-4 規定若底部應力增量仍不可忽略，須繼續納入更深土層；"
                            "請確認底部 Δσz 已可忽略，否則補入更深 DMT 分層後重算。系統不自行判定此工程門檻。"
                        )
                    st.dataframe(pd.DataFrame(result_dmt["layer_results"]),hide_index=True,use_container_width=True)
                    if result_dmt["settlement_mm"]>dmtTarget:
                        st.warning("估算沉陷超過目前設定的參考容許值；實際容許值仍須依結構型式、使用需求及差異沉陷共同決定。")
                    else:
                        st.caption("估算沉陷未超過目前設定的參考值；不代表整體服務性或承載力檢核已通過。")
                    if dmtqult<=0:
                        st.warning("未輸入模組五 qult；此結果未套用 USACE 2025 的 qult/FS 壓力上限。")
                    st.caption(result_dmt["method"])
                    st.warning(result_dmt["limitations"])
            except Exception as exc:
                logging.exception("DMT settlement calculation failed")
                st.error(f"DMT 沉陷估算失敗：{exc}")
        elif method4.startswith('CPT：'):
            st.caption("依 USACE EM 1110-1-1905（2025）式 7-16～7-26。以 CPT 實測 qc 計算等效 Es，依基礎長寬比建立 Iz 深度分布，逐層加總沉陷。原始經驗模數主要適用於年輕（<100 年）、正常固結、潔淨矽砂；不應直接套用於黏土、有機土或膠結土。")
            a,b,c=st.columns(3)
            with a:
                cptB=st.number_input("基礎短邊 B [m]",0.3,30.0,2.0,0.1,key="m4_cpt_b")
                cptL=st.number_input("基礎長邊 L [m]",0.3,100.0,2.0,0.1,key="m4_cpt_l")
                cptType=st.selectbox("基礎型式",["isolated","continuous"],format_func=lambda x:"獨立／矩形基礎" if x=="isolated" else "連續條形基礎",key="m4_cpt_type")
            with b:
                cptq=st.number_input("基礎底 gross q；偏心時輸入 qeq [kPa]",1.0,5000.0,150.0,5.0,key="m4_cpt_q")
                cptSigD=st.number_input("基礎底初始有效應力 σ′zD [kPa]",0.0,3000.0,100.0,5.0,key="m4_cpt_sigD")
                cptSigP=st.number_input("Iz 峰值深度初始有效應力 σ′zp [kPa]",1.0,5000.0,150.0,5.0,key="m4_cpt_sigP")
            with c:
                cpt_transfer_qult=_module5_transfer_value(key_prefix="m4_cpt",label="gross 極限承載力 qult",field="qult_gross_kpa",width_m=cptB,length_m=cptL,footing_type=cptType)
                cptQult=(cpt_transfer_qult if cpt_transfer_qult is not None else st.number_input("模組五 gross qult [kPa]（0＝不套用上限）",0.0,20000.0,0.0,10.0,key="m4_cpt_qult"))
                cptFs=st.number_input("承載力安全係數 FS",1.1,10.0,3.0,0.1,key="m4_cpt_fs")
                if cptQult>0 and cptFs<3.0: st.warning("FS 低於 USACE EM 1110-1-1905（2025）表 2-1 靜力承載力最低值 3.0；可供比較計算，但不可標示為符合該手冊靜力承載力安全要求。")
                cptYears=st.number_input("載重作用時間 [年]",0.01,100.0,50.0,0.5,key="m4_cpt_years")
            cptText=st.text_area("CPT 分層 CSV（由基礎底開始，逐層向下；qc 為實測錐尖阻抗）",
                value="",height=120,key="m4_cpt_layers",
                placeholder="Layer,thickness_m,qc_kpa\n1,0.25,8000\n2,0.25,9500\n…（需涵蓋完整影響深度）")
            st.caption("σ′zp 應取自有效應力剖面在峰值 Iz 深度的位置；矩形基礎峰值深度依 L/B 由 B/2 至 B 內插，連續基礎取 B。CPT qc 不可將 qc−σv0 的淨值誤填為 qc。")
            cptSoilConfirmed=st.checkbox("已確認影響範圍為年輕（<100 年）、正常固結、潔淨矽砂；非黏土、有機土或膠結土",value=False,key="m4_cpt_soil_confirm")
            if not cptSoilConfirmed:
                st.warning("Schmertmann CPT 經驗式的 qc–Es 關係有明確土類與地質年齡適用限制；未確認前不執行計算。若為其他土類，請改用適用的 DMT／PMT／固結分析或另有依據的方法。")
            try:
                if not cptText.strip():
                    st.info("請貼上 CPT qc 分層資料後計算；不以通用 Es 預設值代替現地試驗。")
                else:
                    cptLayers=pd.read_csv(StringIO(cptText)).to_dict("records")
                    cptResult=schmertmann_cpt_settlement_2025(
                        layers=cptLayers,footing_width_m=cptB,footing_length_m=cptL,
                        gross_pressure_kpa=cptq,base_effective_stress_kpa=cptSigD,
                        peak_effective_stress_kpa=cptSigP,years=cptYears,
                        ultimate_bearing_kpa=(cptQult if cptQult>0 else None),
                        factor_of_safety=cptFs,footing_type=cptType,
                        soil_applicability_confirmed=cptSoilConfirmed)
                    st.metric("CPT 估算總沉陷",f"{cptResult['settlement_mm']:.2f} mm")
                    st.write(f"採用 gross 壓力 = {cptResult['gross_pressure_used_kpa']:.1f} kPa ｜ 新增壓力 = {cptResult['net_pressure_increment_kpa']:.1f} kPa ｜ Izp = {cptResult['Iz_peak']:.3f} ｜ C1 = {cptResult['C1_embedment']:.3f} ｜ C2 = {cptResult['C2_creep']:.3f}")
                    if cptResult["capacity_limit_governs"]:
                        st.warning(f"輸入 gross q／qeq={cptq:.1f} kPa 高於 qult/FS={cptResult['capacity_pressure_limit_kpa']:.1f} kPa；依 USACE 2025 壓力限制，沉陷計算已改採 qult/FS。")
                    st.dataframe(pd.DataFrame(cptResult["layer_results"]),hide_index=True,use_container_width=True)
                    if cptQult<=0:
                        st.warning("未輸入模組五 qult；此結果未套用 USACE 2025 的 qult/FS 壓力上限。")
                    st.caption(cptResult["method"])
                    st.warning(cptResult["limitations"])
            except Exception as exc:
                logging.exception("Schmertmann CPT settlement calculation failed")
                st.error(f"CPT 沉陷估算失敗：{exc}")
        elif method4.startswith('PMT：'):
            st.caption("依 USACE EM 1110-1-1905（2025）式 7-11／7-12、表 7-5／7-6 及圖 7-11／7-12。可計算深層均質沉陷，並可另外輸入 2B（條形基礎 6B）範圍內的軟弱／鬆散層修正。")
            a,b,c=st.columns(3)
            with a:
                pmtB=st.number_input("基礎寬度／圓形基礎等效直徑 B [m]",0.3,30.0,2.0,0.1,key="m4_pmt_b")
                pmtRound=st.checkbox("圓形基礎（λd = λc = 1；L 取等效直徑）",value=False,key="m4_pmt_round")
                pmtL=pmtB if pmtRound else st.number_input("基礎長度 L [m]",min_value=float(pmtB),max_value=100.0,value=float(max(pmtB,2.0)),step=0.1,key="m4_pmt_l")
            with b:
                pmtq=st.number_input("基礎底 gross q；偏心時輸入 qeq [kPa]",1.0,5000.0,150.0,5.0,key="m4_pmt_q")
                pmtSigD=st.number_input("基礎底初始有效應力 σ′zD [kPa]",0.0,3000.0,100.0,5.0,key="m4_pmt_sigD")
                pmtPne=st.number_input("PMT 等效淨極限壓力 pne [kPa]",0.0,20000.0,0.0,10.0,key="m4_pmt_pne")
            with c:
                pmt_transfer_qult=_module5_transfer_value(key_prefix="m4_pmt",label="gross 極限承載力 qult",field="qult_gross_kpa",width_m=pmtB,length_m=pmtL,footing_type=("round" if pmtRound else "isolated"))
                pmtQu=(pmt_transfer_qult if pmt_transfer_qult is not None else st.number_input("模組五 gross qult [kPa]（0＝不套用上限）",0.0,20000.0,0.0,10.0,key="m4_pmt_qult"))
                pmtFs=st.number_input("承載力安全係數 FS",1.1,10.0,3.0,0.1,key="m4_pmt_fs")
                if pmtQu>0 and pmtFs<3.0: st.warning("FS 低於 USACE EM 1110-1-1905（2025）表 2-1 靜力承載力最低值 3.0；可供比較計算，但不可標示為符合該手冊靜力承載力安全要求。")
                pmtPy=st.number_input("PMT 屈服壓力 Py [kPa]",0.0,20000.0,0.0,10.0,key="m4_pmt_py")
                pmtSoil=st.selectbox("土類（表 7-6）",["sand","sand_gravel","silt","clay","peat","rock"],format_func=lambda x:{"sand":"砂土","sand_gravel":"砂礫土","silt":"粉土","clay":"黏土","peat":"泥炭","rock":"岩石"}[x],key="m4_pmt_soil")
            pmtRockCondition=None
            if pmtSoil=="rock":
                pmtState="auto"
                pmtRockCondition=st.selectbox("岩體分類（表 7-6）",[
                    "extremely_fractured","other","slightly_fractured_or_extremely_weathered"
                ],format_func=lambda x:{"extremely_fractured":"極度破碎（α=1/3）","other":"其他岩體（α=1/2）","slightly_fractured_or_extremely_weathered":"輕度破碎或極度風化（α=2/3）"}[x],key="m4_pmt_rock_condition")
                st.caption("岩石 α 依 USACE Table 7-6 岩體狀態直接選取，不使用土壤 E/pne 固結狀態判讀。")
            else:
                pmtState=st.selectbox("土層狀態（表 7-6）",["auto","normally_consolidated","overconsolidated","weathered_remolded"],format_func=lambda x:{"auto":"依 Ed／Ec 各自 E/pne 比值自動選 α","normally_consolidated":"正常固結","overconsolidated":"過固結","weathered_remolded":"風化／重塑"}[x],key="m4_pmt_state")
            if pmtSoil=="peat" and pmtState=="auto":
                st.warning("USACE Table 7-6 僅列正常固結泥炭 α=1；須先確認泥炭為正常固結，並明確選擇「正常固結」，不可由 E/pne 自動推定。")
            if pmtRound:
                pmtLd=pmtLc=1.0
                st.caption("圓形基礎依 USACE Figure 7-11，λd = λc = 1。")
            else:
                x,y=st.columns(2)
                with x:
                    pmtLd=st.number_input("λd（依 Figure 7-11 讀值）",1.0,2.5,2.35,0.01,key="m4_pmt_ld")
                with y:
                    pmtLc=st.number_input("λc（依 Figure 7-11 讀值）",1.0,1.5,1.44,0.01,key="m4_pmt_lc")
                st.caption("Figure 7-11 圖示約 λd=1.1–2.35、λc=1.08–1.44（L/B 約 1–10）；輸入範圍限制在圖表座標內，且 λd 不可小於 λc。預設採圖表高端值作保守起始值，請依實際 L/B 讀圖後調整；若 L/B>10，不可外插，請採圖表 L/B=10 端點並註明。")
                pmtLambdaConfirmed=st.checkbox("已依實際 L/B 從 USACE Figure 7-11 核對 λd、λc",value=False,key="m4_pmt_lambda_confirm")
            pmtDeepConfirmed=st.checkbox("若沒有軟弱層資料：已確認為深層且相對均質土層",value=False,key="m4_pmt_deep_confirm")
            pmtSoftText=st.text_area("選填：PMT 軟弱／鬆散夾層 CSV（E_L 為該層 E0 調和平均，單位 kPa）",
                value="",height=90,key="m4_pmt_soft_layers",
                placeholder="depth_center_m,thickness_m,E_L_kpa,pne_kpa,I_sigma\n1.0,0.5,5000,600,0.129")
            st.caption("PMT 軟弱層的 depth_center_m 是層中心點距基礎底的深度；若資料表給層底深度，請用 z_bottom−thickness/2 換算。各層厚度區間不可重疊，系統會檢查重疊。")
            pmtSoftConfirmed=st.checkbox("已辨識並列出基礎下方 2B（條形基礎 6B）範圍內所有軟弱／鬆散層",value=False,key="m4_pmt_soft_confirm")
            pmtText=st.text_area("PMT 分組模數 CSV（E0 單位 kPa；依 Figure 7-12 分組）",
                value="",height=130,key="m4_pmt_layers",
                placeholder="group,E0_kpa\nE1,12000\nE2,15000\nE345,18000\nE678,22000\nE916,25000\n…（每組可有多筆試驗值）")
            st.caption("五組代表深度：E1=0–0.5B；E2=0.5–1B；E345=1–2.5B；E678=2.5–4B；E916=4–8B。每組以調和平均計算。pne 請採模組五／PMT 剪力區的等效淨極限壓力；設計壓力不可超過 PMT 屈服壓力 Py。")
            try:
                if not pmtText.strip():
                    st.info("請貼上五組 PMT E0 試驗值後計算。")
                else:
                    pmtRows=pd.read_csv(StringIO(pmtText)).to_dict("records")
                    if not pmtRound and not pmtLambdaConfirmed:
                        st.error("非圓形基礎須先依文獻圖 7-11 確認 λd、λc。")
                    else:
                        pmtResult=menard_rousseau_pmt_settlement_2025(
                            pmt_moduli=pmtRows,footing_width_m=pmtB,footing_length_m=pmtL,
                            gross_pressure_kpa=pmtq,base_effective_stress_kpa=pmtSigD,
                            equivalent_net_limit_pressure_kpa=pmtPne,
                            yield_pressure_kpa=pmtPy,
                            soil_type=pmtSoil,consolidation_state=pmtState,
                            lambda_d=pmtLd,lambda_c=pmtLc,round_footing=pmtRound,
                            ultimate_bearing_kpa=(pmtQu if pmtQu>0 else None),
                            factor_of_safety=pmtFs,
                            deep_uniform_deposit_confirmed=pmtDeepConfirmed,
                            soft_layers=(pd.read_csv(StringIO(pmtSoftText)).to_dict("records") if pmtSoftText.strip() else None),
                            soft_layer_profile_reviewed=pmtSoftConfirmed)
                        st.metric("PMT 估算總沉陷",f"{pmtResult['settlement_mm']:.2f} mm")
                        st.write(f"剪切變形沉陷 = {pmtResult['deviatoric_settlement_mm']:.2f} mm ｜ 體積變形沉陷 = {pmtResult['spherical_settlement_mm']:.2f} mm ｜ 軟弱層修正 = {pmtResult['soft_layer_settlement_mm']:.2f} mm")
                        if pmtResult["soft_layer_results"]:
                            st.dataframe(pd.DataFrame(pmtResult["soft_layer_results"]),hide_index=True,use_container_width=True)
                        st.write(f"採用 gross 壓力 = {pmtResult['gross_pressure_used_kpa']:.1f} kPa ｜ Ed = {pmtResult['Ed_kpa']:.0f} kPa ｜ Ec = {pmtResult['Ec_kpa']:.0f} kPa ｜ αd = {pmtResult['alpha_d']:.3f} ｜ αc = {pmtResult['alpha_c']:.3f}")
                        if pmtResult["capacity_limit_governs"]:
                            st.warning(f"輸入 gross q／qeq={pmtq:.1f} kPa 高於 qult/FS={pmtResult['capacity_pressure_limit_kpa']:.1f} kPa；依 USACE 2025 壓力限制，沉陷計算已改採 qult/FS。")
                        st.dataframe(pd.DataFrame([{"分組":k,"調和平均 E0 [kPa]":v} for k,v in pmtResult["group_harmonic_means_kpa"].items()]),hide_index=True,use_container_width=True)
                        if pmtQu<=0:
                            st.warning("未輸入模組五 qult；此結果未套用 USACE 2025 的 qult/FS 壓力上限。")
                        st.caption(pmtResult["method"])
                        st.warning(pmtResult["limitations"])
            except Exception as exc:
                logging.exception("Menard-Rousseau PMT settlement calculation failed")
                st.error(f"PMT 沉陷估算失敗：{exc}")
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
                clay_transfer_qa=_module5_transfer_value(key_prefix="m4_clay",label="淨容許承載力 qa,net（FS=3.0）",field="qa_net_kpa",width_m=qB,length_m=qL)
                qcap_clay4=(clay_transfer_qa if clay_transfer_qa is not None else st.number_input("模組五 qa,net 承載力上限 [kPa]（0＝不套用）",0.0,20000.0,0.0,10.0,key='m4c_qcap'))
            layers_text4=st.text_area("選填：多層固結 CSV（填入後取代上方單一壓縮層參數；可選填 Stress_factor）",value="",height=110,key='m4c_layers',placeholder="Layer,Depth_center_m,Thickness_m,e0,Cc,Cr,Sigma0_kPa,SigmaP_kPa,Stress_factor\n1,1.5,3.0,0.8,0.30,0.05,60,100,0.85\n2,5.0,4.0,0.9,0.40,0.06,100,150,0.42")
            try:
                max_clay_q=min(5000.0,qcap_clay4) if qcap_clay4>0 else 5000.0
                stress_ratio_clay4=None
                if layers_text4.strip():
                    layer_rows=pd.read_csv(StringIO(layers_text4)).to_dict('records')
                    r=consolidation_allowable_pressure_layers(layers=layer_rows,footing_width_m=qB,
                        footing_length_m=qL,target_settlement_mm=target4,stress_method=stress_method_clay4,
                        max_pressure_kpa=max_clay_q)
                    qa_clay_settlement=r['qa_primary_consolidation_kpa']
                    st.dataframe(pd.DataFrame(r['layer_results']),hide_index=True,use_container_width=True)
                    st.caption("分層表逐層列出應力影響係數、應力增量及主固結沉陷；總沉陷為各層沉陷量加總。若提供 Stress_factor（0–1），該層會優先採用輸入值；請僅填入經核對的 USACE 範例／圖表或獨立應力分析值，空白則依上方 Boussinesq／2:1 方法計算。")
                else:
                    stress_ratio_clay4=((qB*qL)/((qB+zc)*(qL+zc)) if stress_method_clay4=='2:1'
                        else boussinesq_rectangular_center_factor(qB,qL,zc))
                    r=consolidation_allowable_pressure(target_settlement_mm=target4,footing_pressure_factor=stress_ratio_clay4,
                        layer_thickness_m=Hc,initial_void_ratio=e0,compression_index=Cc,recompression_index=Cr,
                        initial_effective_stress_kpa=sig0,preconsolidation_stress_kpa=sigp,
                        max_pressure_kpa=max_clay_q,stress_method=stress_method_clay4)
                    qa_clay_settlement=r['qa_primary_consolidation_kpa']
                    st.write(f"應力影響係數 = {stress_ratio_clay4:.3f} ｜ 壓縮層中點應力增量 Δσ = {r['delta_sigma_mid_kpa']:.2f} kPa ｜ 預估主固結沉陷 = {r['settlement_mm']:.2f} mm")
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
                        st.caption("多層模式會先以最終控制淨壓力 qa,net 重新計算各層主固結沉陷，再逐層套用各自 Cv 與排水路徑，並在同一經過時間下加總。這是各層獨立一維固結的工程估算，不是完整層間耦合分析。")
                        try:
                            layer_rows_time4=pd.read_csv(StringIO(layers_text4)).to_dict("records")
                            primary_layers_time4=consolidation_settlement_layers(
                                layers=layer_rows_time4,footing_width_m=qB,
                                footing_length_m=qL,net_pressure_kpa=qa_clay_final,
                                stress_method=stress_method_clay4)
                            time_template_rows4=[]
                            for i,row in enumerate(primary_layers_time4["layer_results"],1):
                                time_template_rows4.append({
                                    "Layer":row.get("Layer",i),
                                    "Cv_m2_per_day":"",
                                    "Drainage":"",
                                    "Hdr_m":"",
                                    "C_alpha":"",
                                    "e_p":"",
                                    "t1_days":"",
                                })
                            time_template4=pd.DataFrame(time_template_rows4).to_csv(index=False)
                            time_layer_key4="_".join(str(row.get("Layer",i)) for i,row in enumerate(primary_layers_time4["layer_results"],1))
                            time_params_text4=st.text_area(
                                "逐層固結時間參數 CSV（Cv 必填；Drainage 填 single/double，或直接填 Hdr_m）",
                                value=time_template4,height=170,
                                key="m4c_multi_time_params_"+time_layer_key4,
                                help="C_alpha、e_p 為選填次壓縮參數；C_alpha>0 時必須填 e_p。t1_days 可留白，系統會以 U=99.4%（Tv≈2.0）估算，但正式設計宜用固結試驗判讀值。")
                            rt_ma,rt_mb=st.columns(2)
                            with rt_ma:
                                multi_u_target4=st.number_input("全層加權平均目標固結度 U [%]",min_value=1.0,max_value=99.9,value=90.0,step=1.0,key="m4c_multi_u")
                            with rt_mb:
                                multi_elapsed_years4=st.number_input("共同載重後經過時間 [年]",min_value=0.0,max_value=200.0,value=1.0,step=0.5,key="m4c_multi_elapsed")
                            if time_params_text4.strip():
                                time_params4=pd.read_csv(StringIO(time_params_text4)).to_dict("records")
                                params_ready4=True
                                for row in time_params4:
                                    cv_value=row.get("Cv_m2_per_day")
                                    drainage_raw=row.get("Drainage")
                                    drainage_missing=(drainage_raw is None or pd.isna(drainage_raw) or str(drainage_raw).strip()=="")
                                    hdr_value=row.get("Hdr_m")
                                    if cv_value is None or pd.isna(cv_value) or str(cv_value).strip()=="":
                                        params_ready4=False
                                    if drainage_missing and (hdr_value is None or pd.isna(hdr_value) or str(hdr_value).strip()==""):
                                        params_ready4=False
                                if params_ready4:
                                    multi_time4=consolidation_time_rate_layers(
                                        layer_results=primary_layers_time4["layer_results"],
                                        layer_time_parameters=time_params4,
                                        target_degree_percent=multi_u_target4,
                                        elapsed_days=multi_elapsed_years4*365.25)
                                    st.dataframe(pd.DataFrame(multi_time4["layer_results"]),hide_index=True,use_container_width=True)
                                    mtc1,mtc2,mtc3=st.columns(3)
                                    with mtc1:
                                        st.metric("全層加權平均達標時間",f"{multi_time4['time_to_target_years']:.2f} 年")
                                    with mtc2:
                                        st.metric("目前全層平均固結度",f"{multi_time4['average_degree_at_elapsed_percent']:.1f}%")
                                    with mtc3:
                                        st.metric("目前主固結＋次壓縮沉陷",f"{multi_time4['total_settlement_at_elapsed_mm']:.2f} mm")
                                    st.caption(f"最終主固結沉陷 {multi_time4['ultimate_primary_settlement_mm']:.2f} mm；目前主固結 {multi_time4['primary_settlement_at_elapsed_mm']:.2f} mm；目前次壓縮 {multi_time4['secondary_settlement_at_elapsed_mm']:.2f} mm。")
                                    st.caption(multi_time4["limitations"])
                                else:
                                    st.info("請為每一層填入 Cv_m2_per_day，並指定 Drainage=single/double 或提供 Hdr_m；C_alpha、e_p、t1_days 僅在需要次壓縮時填寫。")
                        except Exception as multi_time_exc:
                            st.error(f"多層固結時間／次壓縮估算失敗：{multi_time_exc}")
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
                            representative_H4=Hc
                            primary_at_final_pressure4=consolidation_settlement_1d(
                                layer_thickness_m=Hc,initial_void_ratio=e0,
                                compression_index=Cc,recompression_index=Cr,
                                initial_effective_stress_kpa=sig0,
                                preconsolidation_stress_kpa=sigp,
                                stress_increase_kpa=qa_clay_final*stress_ratio_clay4)
                            primary_total4=float(primary_at_final_pressure4["settlement_mm"])
                            st.caption(f"時間速率與次壓縮採用最終控制淨壓力 qa,net={qa_clay_final:.2f} kPa 對應的主固結沉陷 {primary_total4:.2f} mm；若模組五承載力上限控制，已重新計算，不沿用容許沉陷目標值。")
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
                with st.expander("多重荷載疊加／大面積填土（逐層 Δσz）",expanded=False):
                    st.caption("適用於相鄰基礎、獨立基礎＋連續基礎、填土＋基礎等多重荷載。Depth_center_m 以你選定的剖面基準面向下量測（例如基礎底或填土底）。請先依 USACE 第 6 章完成各荷載的應力分布與疊加，再輸入每層合計 Δσz；本區只計算固結沉陷，不會自行推算荷載幾何或反算 qa。")
                    super_layers_text4=st.text_area(
                        "逐層總應力增量 CSV（kPa；必須是所有荷載疊加後的總 Δσz）",
                        value="",height=130,key="m4c_superposition_layers",
                        placeholder=(
                            "Layer,Depth_center_m,Thickness_m,e0,Cc,Cr,Sigma0_kPa,SigmaP_kPa,Delta_sigma_kPa\n"
                            "1,1.0,2.0,0.8,0.30,0.05,60,100,25\n"
                            "2,3.0,2.0,0.9,0.40,0.06,100,150,18"
                        ))
                    super_target4=st.number_input(
                        "主固結沉陷比較目標 [mm]",min_value=1.0,max_value=200.0,
                        value=float(target4),step=1.0,key="m4c_superposition_target")
                    if super_layers_text4.strip():
                        try:
                            super_rows4=pd.read_csv(StringIO(super_layers_text4)).to_dict("records")
                            super_result4=consolidation_settlement_layers_from_stress_profile(layers=super_rows4)
                            st.dataframe(pd.DataFrame(super_result4["layer_results"]),hide_index=True,use_container_width=True)
                            st.metric("多重荷載下總主固結沉陷",f"{super_result4['settlement_mm']:.2f} mm")
                            if super_result4["settlement_mm"]>super_target4:
                                st.warning("計算沉陷高於目前設定的比較目標；這不是自動的承載力或整體安全判定。")
                            else:
                                st.info("目前計算沉陷低於設定的比較目標；仍須另行完成承載力、差異沉陷及施工階段檢核。")
                            if qcap_clay4>0:
                                st.warning("此模式使用逐層總 Δσz，不能直接反推單一基礎 qa,net；模組五承載力上限未套用，請另行檢核。")
                            st.caption(super_result4["limitations"])
                        except Exception as super_exc:
                            st.error(f"多重荷載逐層固結估算失敗：{super_exc}")
                    else:
                        st.info("請貼上逐層資料；每一列的 Delta_sigma_kPa 必須是所有荷載完成疊加後的總應力增量。")
                with st.expander("開挖回彈與基礎再壓縮（選填）",expanded=False):
                    st.caption("依 USACE 2025 第 7-15 節／表 7-10。若有各層 oedometer e-log-p 曲線，優先輸入逐層 e0、e_exc、e_final；單一 Cr/Cc 模式僅為理想化初估。")
                    rebound_mode4=st.radio("計算資料型式",["逐層 e-log-p 試驗孔隙比","單層 Cr/Cc 理想化"],horizontal=True,key="m4c_rebound_mode")
                    if rebound_mode4=="逐層 e-log-p 試驗孔隙比":
                        rebound_layers_text4=st.text_area(
                            "逐層 e-log-p CSV（有效應力單位 kPa；厚度單位 m）",
                            value="",height=120,key="m4c_rebound_layers",
                            placeholder=(
                                "Layer,rebound_thickness_m,recompression_thickness_m,initial_effective_stress_kpa,excavation_effective_stress_kpa,final_effective_stress_kpa,e0,e_exc,e_final\n"
                                "2,2.4384,1.8288,51.7,9.6,135.0,0.947,0.964,0.805\n"
                                "3,4.2672,2.4384,78.5,55.6,79.4,0.991,0.999,0.983"
                            ))
                        if rebound_layers_text4.strip():
                            try:
                                rebound_rows4=pd.read_csv(StringIO(rebound_layers_text4)).to_dict("records")
                                rebound4=excavation_rebound_recompression_layers(layers=rebound_rows4)
                                st.dataframe(pd.DataFrame(rebound4["layer_results"]),hide_index=True,use_container_width=True)
                                st.metric("開挖回彈（隆起）",f"{abs(rebound4['rebound_mm']):.2f} mm")
                                st.metric("基礎再壓縮沉陷",f"{rebound4['recompression_settlement_mm']:.2f} mm")
                                st.metric("回彈後淨垂直位移（正值為沉陷）",f"{rebound4['net_settlement_mm']:.2f} mm")
                                st.caption(rebound4["limitations"])
                            except Exception as rebound_exc:
                                st.error(f"逐層 e-log-p 回彈／再壓縮估算失敗：{rebound_exc}")
                        else:
                            st.info("請貼上各壓縮層的試驗曲線讀值；沒有 e-log-p 資料時，請改用單層 Cr/Cc 理想化模式。")
                    else:
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
                                st.warning("目前此模式仍以單層代表參數估算；多層地層應使用逐層 e-log-p 模式。")
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
