"""Streamlit UI for engineering module 5."""
import streamlit as st
import logging
import hashlib
from .state import clear_result_state, read_result_state, store_result_state
import math
import pandas as pd
from io import StringIO
from geolysis_engine import bearing_capacity, bearing_pressure_safety_check, bearing_capacity_in_situ, bearing_capacity_slope_base_corrections, layered_bearing_capacity_punching, layered_bearing_capacity_profile, seismic_bearing_capacity_pseudostatic, seismic_foundation_eccentricity_cases, foundation_sliding_factor_of_safety, foundation_sliding_pseudostatic_cases, seismic_uplift_stability_cases, developed_rankine_sliding_earth_pressures, bishop_simplified_factor_of_safety, bishop_circular_search, seismic_bearing_capacity_residual_pore_pressure, seismic_bearing_capacity_residual_pore_pressure_cases




def _seismic_case_dataframe(rows, footing_type):
    frame=pd.DataFrame(rows)
    if footing_type=="strip":
        frame=frame.rename(columns={
            "horizontal_load_kN":"horizontal_load_kN_per_m",
            "vertical_load_kN":"vertical_load_kN_per_m",
            "seismic_weight_kN":"seismic_weight_kN_per_m",
            "moment_B_kNm":"moment_B_kNm_per_m",
            "moment_L_kNm":"moment_L_kNm_per_m",
        })
    return frame

def _render_bearing_safety_check(*, qult_kpa, vertical_load_kN, width_m,
        length_m, depth_m, water_depth_m, eccentricity_B_m=0.0,
        eccentricity_L_m=0.0, footing_type="isolated",
        complete_capacity_model=True, incomplete_reason=None, load_confirmed=True):
    """Display USACE 2025 qeq / bearing FS beside a capacity result."""
    check=bearing_pressure_safety_check(
        ultimate_bearing_kpa=qult_kpa,vertical_load_kN=vertical_load_kN,
        footing_width_m=width_m,footing_length_m=length_m,
        footing_depth_m=depth_m,water_depth_m=water_depth_m,
        eccentricity_B_m=eccentricity_B_m,eccentricity_L_m=eccentricity_L_m,
        footing_type=footing_type,required_fs=3.0)
    st.markdown("**實際承載力安全檢核（USACE 2025 式 5-2／5-3／5-23）**")
    if not load_confirmed:
        st.warning("V 目前仍是示範預設值。請先輸入並確認本次設計總垂直力 V=Q+Wf（包含基礎自重及基礎底以上覆土），確認後才會顯示 qeq 與實際 FS。")
        return check
    if footing_type=="isolated":
        st.write(f"有效尺寸 B′ × L′ = {check['B_effective_m']:.3f} × {check['L_effective_m']:.3f} m；有效面積 A′ = {check['effective_area_m2']:.3f} m²")
    else:
        st.write(f"有效寬度 B′ = {check['B_effective_m']:.3f} m")
    load_unit="kN/m（連續基礎線荷載）" if footing_type=="continuous" else "kN"
    st.write(f"V = {vertical_load_kN:.2f} {load_unit}；基底揚壓 uD = {check['water_uplift_pressure_kpa']:.2f} kPa")
    qcol,fscol,reqcol=st.columns(3)
    qcol.metric("實際等效壓力 qeq",f"{check['qeq_gross_kpa']:.2f} kPa")
    reqcol.metric("USACE 最低要求 FS","3.00")
    if check["FS_bearing"] is None:
        fscol.metric("實際承載力 FS","無有效值")
        st.error("qeq≤0，表示基底合力已進入淨上拔／浮力主導狀態；不可用承載力 FS 判斷，請另做完整抗浮檢核。")
    elif not complete_capacity_model:
        fscol.metric("實際承載力 FS","未計算")
        st.warning(incomplete_reason or "目前承載力計算未涵蓋所有輸入的載重／幾何修正，因此不顯示完整設計安全係數。")
    else:
        fscol.metric("實際承載力 FS",f"{check['FS_bearing']:.2f}",
            delta=("符合 ≥3.0" if check["passes_bearing"] else "未達 ≥3.0"),
            delta_color=("normal" if check["passes_bearing"] else "inverse"))
    if not check["passes_middle_third"]:
        st.error("偏心距超出基礎中三分點限制（eB<B/6、eL<L/6）；依 USACE 2025 表 2-1，傾覆／偏心檢核不合格。")
    elif complete_capacity_model and check["passes_all_checks"]:
        st.success("承載力 FS 與中三分點偏心限制均符合目前 USACE 2025 最低要求。")
    elif complete_capacity_model and not check["passes_bearing"]:
        st.error("承載力安全係數低於 USACE 2025 最低要求 3.0。")
    st.caption("V 必須是傳至基礎底面的總向下垂直力 Q+Wf，已含基礎自重及基礎底以上覆土；不要只填柱載重 Q。地下水位高於基礎底時，依 uD=γw(Df−Dw) 扣除基底水壓。此項只檢核承載力與中三分點偏心，不取代滑動、抗浮、整體穩定及沉陷檢核。qult 抗力端仍依上方所選理論計算；選用 1992 經典理論時，這是與 USACE 2025 需求端公式組合的檢核，不代表整套抗力係數已改為 2025 Meyerhof-based 方法。")
    return check


def render_module_5(expanded=False):
    # Module 1 results are explicitly transferred through session state; do not
    # rely on another renderer's local variables.
    hb_current = st.session_state.get("geolysis_hb_current")
    hb_metadata = st.session_state.get("geolysis_hb_metadata", {})
    c_hb_kpa = float(hb_current["c_equiv_kpa"]) if hb_current is not None else 0.0
    phi_hb_deg = float(hb_current["phi_equiv_deg"]) if hb_current is not None else 0.0
    sig3_max = float(hb_current["sigma3_max_mpa"]) if hb_current is not None else 0.0
    gsi = float(hb_metadata.get("gsi", 0.0))
    d_factor = float(hb_metadata.get("disturbance", 0.0))
    sig_ci = float(hb_metadata.get("sigma_ci_mpa", 0.0))
    mi = float(hb_metadata.get("mi", 0.0))
    hb_application = str(hb_metadata.get("application", ""))

    # ==============================================================================
    # 模組五：極限承載力四大理論
    # ==============================================================================
    with st.expander("🏗️ 模組五：極限承載力四大理論", expanded):
        st.subheader("🏗️ 模組五：極限承載力四大理論")
        st.caption("採 Terzaghi、Meyerhof、Hansen、Vesic 各自的經典承載力因子／係數架構；請先確認土層參數代表基礎破壞影響範圍。注意：USACE 2025 現行手冊另列 USACE（以 Meyerhof 為主）與 AASHTO/FHWA（以 Vesic 為主）兩套設計修正係數；若承載力控制設計，建議依該手冊分別計算並比較，不應將本頁任一單一理論宣稱為完整符合 2025 USACE 設計程序。")
        a,b,c,d=st.columns(4)
        with a:
            theory5=st.selectbox("理論",['Terzaghi','Meyerhof','Hansen','Vesic'],key='m5_theory')
            B5=st.number_input("基礎短邊 B [m]",0.2,50.0,2.0,0.1,key='m5_b')
            L5=st.number_input("基礎長邊 L [m]",0.2,100.0,3.0,0.1,key='m5_l')
            main_footing_type5=st.selectbox("主承載力分析基礎型式",["isolated","continuous"],
                format_func=lambda x:"獨立／矩形基礎" if x=="isolated" else "連續條形基礎",
                key="m5_main_footing_type")
            if main_footing_type5=="continuous":
                st.caption("主承載力與 qeq 檢核採連續條形基礎 strip 極限；V、H 使用 kN/m，qeq=V/B′。長邊方向偏心不適用。")
        with b:
            src5=st.selectbox("參數來源",['手動輸入','模組一 Hoek-Brown 等效參數（一般淺層圍壓擬合）'],key='m5_src')
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
            c5=st.number_input("凝聚力 c′／不排水抗剪強度 cu [kPa]",0.0,100000.0,cdef,1.0,key='m5_c',disabled=use_hb5)
            phi5=st.number_input("有效內摩擦角 ϕ′ [°]（不排水分析設 0）",0.0,50.0,min(50.0,phidef),1.0,key='m5_phi',disabled=use_hb5)
            st.caption("參數判讀：ϕ′=0 時，c 應輸入不排水抗剪強度 Su／cu；ϕ′>0 時，輸入有效應力 c′、ϕ′。手動欄位預設值僅供操作示範，不代表工址參數；正式設計請採地勘及試驗資料。")
            if use_hb5 and hb_current is None:
                st.error("模組一參數尚未成功計算，不能作為模組五輸入。")
            hb_bearing_material_confirmed5=False
            hb_stress_range_confirmed5=False
            if use_hb5 and hb_current is not None:
                st.caption(f"模組一目前等效參數：c′={c_hb_kpa:.1f} kPa、ϕ′={phi_hb_deg:.2f}°；圍壓範圍 σ3,max={sig3_max:.3f} MPa；分析類型={hb_application}。")
                if hb_application!="general":
                    st.error("目前 Module 1 等效參數是依邊坡／隧道圍壓範圍擬合，不可直接移用至淺基礎承載力。請先在 Module 1 選擇「一般淺層分析」，並輸入具工程依據的基礎剪力區 σ3,max。")
                if phi_hb_deg>50:
                    st.error("模組一等效摩擦角超過本模組承載力公式目前支援的 50° 上限；系統不會把它截斷成 50° 後計算。")
                st.caption("適用性依 USACE EM 1110-1-1905（2025）§1-7(b)：一般淺基礎土壤方法不適用完整、節理、層狀或破裂岩盤；僅高度破碎岩體／岩屑狀材料在岩塊尺度相對基礎寬度足夠小時，才可視為類似密實顆粒土評估。Hoek–Brown 等效 Mohr–Coulomb 參數亦須在代表本基礎剪力區的 σ3 範圍內擬合。")
            hb_bearing_material_confirmed5=False
            hb_stress_range_confirmed5=False
            hb_confirmation_signature=""
        with c:
            gamma5=st.number_input("基礎底以上總單位重 γ_D [kN/m³]",10.0,30.0,18.5,0.5,key='m5_gamma')
            same_gamma_below5=st.checkbox("基礎底下與上覆土同一土層",value=True,key='m5_same_gamma_below')
            if same_gamma_below5:
                gamma_below5=gamma5
            else:
                gamma_below5=st.number_input("基礎底以下總單位重 γ_H [kN/m³]",10.0,30.0,20.0,0.5,key='m5_gamma_below')
            gsub5=st.number_input("基礎底以下有效單位重 γ′_H [kN/m³]",5.0,15.0,9.5,0.5,key='m5_gsub')
            st.caption("地下水位位於基礎底下剪力區時，Nγ 項有效單位重依剪力區深度 H=B′tan(45+ϕ′/2) 估算；上下土層不同時，請取消同層勾選並輸入 γ_H。")
            df5=st.number_input("基礎埋深 Df [m]",0.0,30.0,1.5,0.1,key='m5_df')
        with d:
            dw5=st.number_input("地下水位深度 Dw [m]（自地表）",0.0,100.0,5.0,0.1,key='m5_dw')
            fs5=st.number_input("安全係數 FS",1.1,5.0,3.0,0.1,key='m5_fs')
            if fs5<3.0: st.warning("目前 allowable bearing pressure 使用的 FS 低於 USACE EM 1110-1-1905（2025）表 2-1 靜力承載力最低值 3.0；可供其他規範／敏感度比較，但不可視為符合 USACE 靜力承載力安全要求。實際 qeq 檢核仍固定以 FS≥3.0 判定。")
            beta5=st.number_input("載重傾角 β [°]（Meyerhof 使用）",0.0,60.0,0.0,1.0,key='m5_beta',disabled=(theory5!='Meyerhof'))
        failure_mode5=st.selectbox("Terzaghi 剪力破壞模式",['general','local'],format_func=lambda x:'一般剪力破壞' if x=='general' else '局部剪力破壞（c、ϕ 折減）',disabled=(theory5!='Terzaghi'),key='m5_failure_mode')
        st.markdown("**載重分量（供 Hansen／Vesic 傾斜係數使用）**")
        hcol,vcol=st.columns(2)
        with hcol: H5=st.number_input("水平載重 H [kN；連續基礎請用 kN/m]",0.0,1000000.0,0.0,10.0,key='m5_h')
        with vcol: V5=st.number_input("垂直載重 V [kN；連續基礎請用 kN/m]（Q+Wf）",0.1,1000000.0,1000.0,10.0,key='m5_v')
        st.caption("H、V 為基礎底面作用力；V 應採傳遞至地盤的總垂直力 Q+Wf，包含結構荷載、基礎自重及基礎上覆土重。連續條形基礎的 V、H 應採每延米線荷載（kN/m）。請勿直接以任意預設值作設計輸入。")
        loads_confirmed5=st.checkbox("已確認 V 為本次設計總垂直力 Q+Wf（含基礎自重及覆土）",value=False,key="m5_loads_confirmed")
        if theory5=='Terzaghi':
            st.session_state['m5_eL']=0.0
            st.session_state['m5_eB']=0.0
        if main_footing_type5=="continuous":
            st.session_state['m5_eL']=0.0
            st.session_state['m5_load_dir']="parallel_B"
        excol,eycol=st.columns(2)
        with eycol: eB5=st.number_input("短邊方向偏心距 eB [m]",0.0,max(0.0,B5/2-0.001),0.0,0.01,key='m5_eB',disabled=(theory5=='Terzaghi'))
        eL_max5=max(0.0,min(L5/2-0.001,(L5-(B5-2*eB5))/2-0.001))
        eL_disabled5=(theory5=='Terzaghi' or main_footing_type5=='continuous' or eL_max5<0.001)
        with excol: eL5=st.number_input("長邊方向偏心距 eL [m]",0.0,max(0.001,eL_max5),0.0,0.01,key='m5_eL',disabled=eL_disabled5)
        if theory5=='Terzaghi': st.caption("Terzaghi 本頁不支援偏心荷載；切換至 Terzaghi 時偏心距會重設為 0。")
        load_dir5=st.selectbox("水平力方向（Vesic 公式）",['parallel_B','parallel_L'],format_func=lambda x:'平行短邊 B' if x=='parallel_B' else '平行長邊 L',disabled=(theory5!='Vesic' or main_footing_type5=='continuous'),key='m5_load_dir')
        adhesion5=st.number_input("基底黏著係數 ca/c（Hansen／Vesic）",0.0,1.0,0.6,0.1,key='m5_adhesion',disabled=(theory5 not in ('Hansen','Vesic')))
        if use_hb5 and hb_current is not None:
            # Re-key confirmations to all relevant source and foundation inputs;
            # a changed load, geometry, water level or soil profile requires review.
            hb_confirmation_signature=(
                f"{gsi:.0f}-{mi:.2f}-{sig_ci:.2f}-{d_factor:.2f}-{sig3_max:.3f}-"
                f"{hb_application}-{hb_metadata.get('structure_code','')}-"
                f"{B5:.2f}-{L5:.2f}-{df5:.2f}-{dw5:.2f}-"
                f"{gamma5:.2f}-{gamma_below5:.2f}-{gsub5:.2f}-{V5:.1f}-{H5:.1f}-"
                f"{eB5:.3f}-{eL5:.3f}-{beta5:.1f}-{main_footing_type5}-"
                f"{theory5}-{failure_mode5}-{load_dir5}-{adhesion5:.2f}"
            )
            hb_bearing_material_confirmed5=st.checkbox(
                f"已確認基礎承載剪力區為高度破碎岩體／岩屑狀岩體，且中值岩塊尺寸 ≤ B/50 = {B5/50:.3f} m；不是完整、少數節理控制或層狀岩盤",
                value=False,key=f"m5_hb_material_{hb_confirmation_signature}")
            hb_stress_range_confirmed5=st.checkbox(
                f"已確認 Module 1 等效 c′、ϕ′ 擬合圍壓上限 σ3,max={sig3_max:.3f} MPa，代表本基礎承載剪力區的圍壓範圍",
                value=False,key=f"m5_hb_range_{hb_confirmation_signature}")
        hb_bearing_source_valid5=(hb_current is not None and hb_application=="general"
            and phi_hb_deg<=50 and hb_bearing_material_confirmed5
            and hb_stress_range_confirmed5)
        st.caption("本頁 Hansen／Vesic 採 USACE 1992 經典表 4-5／4-6，水平力修正使用基底界面黏著 ca；ca/c 應依基礎底面粗糙度或試驗決定，0.6 僅為可調預設值。φ′=0 不排水分析採總應力覆土，φ′>0 排水分析採有效應力覆土。")
        hb_source_signature=(float(gsi),float(sig3_max),float(d_factor),float(sig_ci),float(mi),hb_application,
            str(hb_metadata.get("structure_code",""))) if use_hb5 and hb_current is not None else ()
        m5_input_signature=(theory5,main_footing_type5,src5,float(c5),float(phi5),float(gamma5),float(gamma_below5),bool(same_gamma_below5),float(gsub5),float(B5),float(L5),float(df5),float(dw5),float(fs5),float(beta5),float(H5),float(V5),float(eB5),float(eL5),failure_mode5,load_dir5,float(adhesion5),hb_source_signature,hb_confirmation_signature,bool(hb_bearing_material_confirmed5),bool(hb_stress_range_confirmed5),bool(loads_confirmed5))
        if st.button("計算極限承載力",key='m5_run'):
            clear_result_state(st.session_state, 'm5_result', 'm5_result_signature')
            if use_hb5 and not hb_bearing_source_valid5:
                st.error("Module 1 Hoek–Brown 參數未通過淺基礎適用性確認，或不是一般淺層圍壓擬合；已停止計算。請改用適當試驗參數或修正 Module 1 圍壓範圍。")
            else:
                try:
                    if abs(math.degrees(math.atan2(H5,V5))-beta5)>2.0 and H5>0 and theory5=='Meyerhof':
                        st.warning("載重傾角 β 與 H/V 計算角度差異超過 2°；H/V 為 Hansen/Vesic 計算依據，請核對輸入。")
                    result5=bearing_capacity(theory=theory5,c_kpa=c5,phi_deg=phi5,gamma_moist=gamma5,gamma_sub=gsub5,gamma_below=gamma_below5,B=B5,L=L5,Df=df5,water_depth=dw5,fs=fs5,load_angle=(beta5 if theory5=='Meyerhof' else 0.0),horizontal_load=(H5 if theory5 in ('Hansen','Vesic') else 0.0),vertical_load=(V5 if theory5 in ('Hansen','Vesic') else None),failure_mode=(failure_mode5 if theory5=='Terzaghi' else 'general'),load_direction=load_dir5,adhesion_ratio=adhesion5,eccentricity_B=eB5,eccentricity_L=eL5,footing_type=main_footing_type5)
                    store_result_state(st.session_state, 'm5_result', 'm5_result_signature', result5, m5_input_signature)
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"承載力計算失敗：{exc}")
        result5, result5_is_current = read_result_state(st.session_state, 'm5_result', 'm5_result_signature', m5_input_signature)
        if result5 and not result5_is_current:
            st.warning("模組五輸入參數已變更；目前顯示的舊結果不再對應現有輸入。請重新按「計算極限承載力」更新結果。")
            result5=None
        m5_transfer_candidate=None
        if result5:
            r1,r2,r3=st.columns(3)
            r1.metric("總極限承載力 qu",f"{result5['qu_gross']:.1f} kPa")
            r2.metric("淨容許承載力 qa,net",f"{result5['qa_net']:.1f} kPa")
            r3.metric("總容許承載力 qa,gross",f"{result5['qa_gross']:.1f} kPa")

            main_load_complete=((theory5=="Meyerhof" and abs(beta5-math.degrees(math.atan2(H5,V5)))<=0.1) or
                (theory5 in ("Hansen","Vesic")) or
                (theory5=="Terzaghi" and H5<=0))
            main_reason=("目前 H>0，但所選理論沒有套用與 H/V 相符的載重傾斜修正；請選 Hansen／Vesic，或在 Meyerhof 中將 β 設為 atan(H/V)。" if not main_load_complete else None)
            bearing_check5=_render_bearing_safety_check(
                qult_kpa=result5["qu_gross"],vertical_load_kN=V5,
                width_m=B5,length_m=L5,depth_m=df5,water_depth_m=dw5,
                eccentricity_B_m=eB5,eccentricity_L_m=eL5,
                footing_type=main_footing_type5,complete_capacity_model=main_load_complete,
                incomplete_reason=main_reason,load_confirmed=loads_confirmed5)
            factors=pd.DataFrame([
                {'項目':'凝聚力項 cNc','承載力因子':result5['Nc'],'形狀係數':result5['sc'],'深度係數':result5['dc'],'傾斜係數':result5['ic'],'貢獻(kPa)':result5['term_c']},
                {'項目':'覆土項 qNq','承載力因子':result5['Nq'],'形狀係數':result5['sq'],'深度係數':result5['dq'],'傾斜係數':result5['iq'],'貢獻(kPa)':result5['term_q']},
                {'項目':'單位重項 0.5γBNγ','承載力因子':result5['Ngamma'],'形狀係數':result5['sg'],'深度係數':result5['dg'],'傾斜係數':result5['ig'],'貢獻(kPa)':result5['term_gamma']}])
            st.dataframe(factors,hide_index=True,use_container_width=True)
            q_label5="基礎底總覆土壓力 q₀（不排水總應力）" if result5['phi_used']==0 else "基礎底有效覆土壓力 q′₀（排水有效應力）"
            if main_footing_type5=="continuous":
                st.write(f"有效寬度 B′ = {result5['B_effective']:.2f} m ｜ {q_label5} = {result5['q_surcharge']:.2f} kPa ｜ 剪力區深度 H = {result5['shear_zone_depth']:.2f} m ｜ Nγ 項平均有效單位重 γ' = {result5['gamma_effective']:.2f} kN/m³")
            else:
                st.write(f"有效尺寸 B′ × L′ = {result5['B_effective']:.2f} × {result5['L_effective']:.2f} m ｜ {q_label5} = {result5['q_surcharge']:.2f} kPa ｜ 剪力區深度 H = {result5['shear_zone_depth']:.2f} m ｜ Nγ 項平均有效單位重 γ' = {result5['gamma_effective']:.2f} kN/m³")
            st.caption(f"模組四沉陷承載力上限可帶入：砂土／礫土使用 qult={result5['qu_gross']:.1f} kPa 並由模組四套用其 FS；黏土主固結使用 qa,net(FS=3.0)={result5['qu_net']/3.0:.1f} kPa。頁面 qa,net(FS={fs5:.1f})={result5['qa_net']:.1f} kPa 仍依目前選定 FS 顯示，不直接作為 USACE 靜力最低 FS 的跨模組值。")
            st.caption(f"qult/FS 的參考換算值為 {result5['qa_gross_direct_FS']:.1f} kPa；這不是工址實際安全係數。實際 FS 必須以本頁下方 qeq=V/A′−uD 與 qult 比較，不能以容許承載力欄位取代。")
            if theory5=='Terzaghi': st.caption(f"Terzaghi {result5['failure_mode']}：採用 c = {result5['c_used']:.2f} kPa、ϕ = {result5['phi_used']:.2f}°；承載力因子依 USACE 表列值線性插值。")
            if '模組一' in src5:
                st.warning(f"本次使用模組一等效 Mohr–Coulomb 參數；其 c′、ϕ′係在 σ3,max={sig3_max:.3f} MPa 範圍內擬合，須確認與淺基礎破壞應力範圍相符。若不相符，請改用試驗參數或重新設定模組一圍壓範圍。")
            st.warning(result5['limitations'])
            settlement_transfer_geometry_supported5=(
                abs(float(H5))<=1e-6 and abs(float(eB5))<=1e-6 and abs(float(eL5))<=1e-6
            )
            if (loads_confirmed5 and main_load_complete
                    and bearing_check5.get("passes_middle_third")
                    and bearing_check5.get("FS_bearing") is not None
                    and float(result5.get("qu_net",0.0))>0.0
                    and settlement_transfer_geometry_supported5):
                transfer_id5=hashlib.sha256(repr(m5_input_signature).encode("utf-8")).hexdigest()[:12]
                m5_transfer_candidate={
                    "transfer_id":transfer_id5,
                    "qult_gross_kpa":float(result5["qu_gross"]),
                    "qa_gross_kpa":float(result5["qu_net"]/3.0+result5["q_surcharge"]),
                    "qa_net_kpa":float(result5["qu_net"]/3.0),
                    "qeq_gross_kpa":float(bearing_check5["qeq_gross_kpa"]),
                    "B_m":float(B5),"L_m":float(L5),"Df_m":float(df5),"Dw_m":float(dw5),
                    "footing_type":str(main_footing_type5),"source":str(src5),
                    "theory":str(theory5),"FS_bearing":float(bearing_check5["FS_bearing"]),
                    "H_kN":float(H5),"eB_m":float(eB5),"eL_m":float(eL5),
                    "scope":"Module 5 primary level-base/level-ground bearing result",
                    "passes_bearing":bool(bearing_check5["passes_bearing"]),
                    "load_confirmed":True,"complete_capacity_model":True,
                }
            elif (loads_confirmed5 and main_load_complete
                    and bearing_check5.get("passes_middle_third")
                    and bearing_check5.get("FS_bearing") is not None
                    and not settlement_transfer_geometry_supported5):
                st.warning("Module 4 沉陷方法的跨模組承載力帶入目前僅支援中央垂直荷載（H=0、eB=eL=0）。跨模組值取自 Module 5 主承載力的水平基底／地表分析，不會自動採用另行計算的斜坡／傾斜基底結果；若實際基底或地表有坡度，請勿直接移用。")
        new_transfer_id5=(m5_transfer_candidate["transfer_id"] if m5_transfer_candidate else None)
        old_transfer_id5=st.session_state.get("_m5_bearing_transfer_id")
        if old_transfer_id5!=new_transfer_id5:
            st.session_state["_m5_bearing_transfer_id"]=new_transfer_id5
            st.session_state["m5_bearing_transfer"]=m5_transfer_candidate
            st.rerun()
        else:
            st.session_state["m5_bearing_transfer"]=m5_transfer_candidate
        st.caption("Hoek–Brown 岩體等效 c′、ϕ′僅應用於適當岩體尺度與破壞模式；不可不加判斷地當作一般土壤參數。SPT 推估 ϕ 亦僅為經驗參考，不取代三軸／直剪試驗。")
        st.caption("另提醒：USACE 2025 的 AASHTO/FHWA Vesic-based 設計係數系統與本頁 1992 經典 Vesic 表 4-6 不同：2025 系統的水平力係數使用土體 c、φ′=0 深度係數保守省略，且 FHWA 建議不要同時套用形狀與載重傾斜修正；本頁經典公式則使用基底黏著 ca，φ′=0 採 dc=1+0.4k。本頁不宣稱等同完整 AASHTO/FHWA 設計程序。")
        with st.expander("理論公式與文獻來源",expanded=False):
            st.markdown("- [USACE EM 1110-1-1905（2025）：淺基礎承載力設計（現行手冊）](https://publibrary.sec.usace.army.mil/api/download?filename=EM+1110-1-1905_Geotechincal+Design+of+Shallow+Foundations+on+Soils_2025+07+22+-+Final.pdf&id=54658636-77d2-48df-f26b-5295a01899a7&preview=true)\n- [USACE EM 1110-1-1905（1992）：經典承載力因子表](https://www.publications.usace.army.mil/Portals/76/Publications/EngineerManuals/EM_1110-1-1905.pdf)\n- [FHWA GEC No. 6：Shallow Foundations](https://www.fhwa.dot.gov/engineering/geotech/pubs/010943.pdf)\n- [geolysis 開源套件公式文件](https://docs.geolysis.io/en/latest/formulas/ultimate-bearing-capacity/)")
    
    
        st.markdown("---")
        st.subheader("進階極限狀態分析（擴充）")
        st.caption("以下功能分別計算，不與原本水平地表靜力承載力混為一談。各項結果需依實際地層、地下水、荷載組合及採用規範審查。")
    
        with st.expander("① 斜坡地表／② 傾斜基底承載力修正",expanded=False):
            st.caption("依 USACE EM 1110-1-1905（2025）表 5-3／5-4 的 Meyerhof-based 修正係數；排水載重傾斜角 β 由本頁 H/V 自動計算，不沿用經典理論的手動 β；地表坡面假設由基礎向外下降。坡體整體穩定仍須另外通過檢核。")
            sc1,sc2,sc3=st.columns(3)
            with sc1:
                base_ang5=st.number_input("基底／剪力鍵等效傾角 αb [°]",0.0,59.0,0.0,1.0,key="m5x_base_angle")
            with sc2:
                ground_ang5=st.number_input("鄰接地表坡角 αg [°]",0.0,44.0,0.0,1.0,key="m5x_ground_angle")
            with sc3:
                slope_dist5=st.number_input("基礎有效邊至坡頂距離 dg [m]",0.0,100.0,0.0,0.5,key="m5x_slope_distance")
            slope_fs5=st.number_input("鄰接坡體整體穩定 FS（須 > 1.3）",0.0,10.0,0.0,0.05,key="m5x_slope_fs",disabled=(ground_ang5<=0))
            st.caption("USACE 2025 表 5-3 註 b：鄰接坡體地表坡角修正係數以坡體整體穩定 FS > 1.3 為前提。請先完成獨立整體穩定檢核；未達或未提供 FS 時，系統會停止坡角修正。")
            if use_hb5 and not hb_bearing_source_valid5:
                st.warning("Module 1 等效參數未通過淺基礎適用性與圍壓確認；斜坡／傾斜基底承載力亦不會使用未確認的岩體參數。")
            if st.button("計算斜坡／傾斜基底承載力",key="m5x_slope_run",disabled=(use_hb5 and not hb_bearing_source_valid5)):
                try:
                    base_for_slope=bearing_capacity(theory="Meyerhof",c_kpa=c5,phi_deg=phi5,
                        gamma_moist=gamma5,gamma_sub=gsub5,gamma_below=gamma_below5,
                        B=B5,L=L5,Df=df5,water_depth=dw5,fs=fs5,footing_type=main_footing_type5,
                        load_angle=beta5,eccentricity_B=eB5,eccentricity_L=eL5)
                    slope_result=bearing_capacity_slope_base_corrections(
                        base_result=base_for_slope,c_kpa=c5,phi_deg=phi5,
                        base_inclination_deg=base_ang5,ground_inclination_deg=ground_ang5,
                        slope_distance_m=slope_dist5,
                        adjacent_slope_fs=(slope_fs5 if ground_ang5>0 else None),
                        horizontal_load=H5,vertical_load=V5)
                    store_result_state(st.session_state, "m5x_slope_result", "m5x_slope_signature", slope_result, (src5,hb_source_signature,hb_confirmation_signature,bool(hb_bearing_material_confirmed5),bool(hb_stress_range_confirmed5),c5,phi5,gamma5,gsub5,gamma_below5,B5,L5,df5,dw5,fs5,beta5,eB5,eL5,main_footing_type5,base_ang5,ground_ang5,slope_dist5,slope_fs5,H5,V5))
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"斜坡／基底傾斜計算失敗：{exc}")
            slope_sig=(src5,hb_source_signature,hb_confirmation_signature,bool(hb_bearing_material_confirmed5),bool(hb_stress_range_confirmed5),c5,phi5,gamma5,gsub5,gamma_below5,B5,L5,df5,dw5,fs5,beta5,eB5,eL5,main_footing_type5,base_ang5,ground_ang5,slope_dist5,slope_fs5,H5,V5)
            slope_result, slope_is_current = read_result_state(st.session_state, "m5x_slope_result", "m5x_slope_signature", slope_sig)
            if slope_result and slope_is_current:

                _render_bearing_safety_check(
                    qult_kpa=slope_result["qu_gross"],vertical_load_kN=V5,
                    width_m=B5,length_m=L5,depth_m=df5,water_depth_m=dw5,
                    eccentricity_B_m=eB5,eccentricity_L_m=eL5,
                    footing_type=main_footing_type5,complete_capacity_model=True,load_confirmed=loads_confirmed5)
                st.metric("修正後總極限承載力",f"{slope_result['qu_gross']:.1f} kPa")
                st.write(f"形狀係數：sc={slope_result['sc']:.3f}、sq={slope_result['sq']:.3f}、sγ={slope_result['sg']:.3f}；深度係數：dc={slope_result['dc']:.3f}、dq={slope_result['dq']:.3f}、dγ={slope_result['dg']:.3f}")
                if phi5>0:
                    st.write(f"載重傾斜角 β=atan(H/V)={slope_result['load_inclination_beta_2025_deg']:.2f}°；載重係數 ic=iq={slope_result['load_factor_c_2025']:.3f}、iγ={slope_result['load_factor_gamma_2025']:.3f}")
                else:
                    st.write(f"不排水載重比 H/V={H5/V5:.3f}；USACE 2025 Table 5-4 凝聚力項 ic={slope_result['load_factor_c_2025']:.3f}，覆土項 iq=1.000；Nγ 項不使用。")
                st.write(f"基底係數：bc={slope_result['base_factor_c']:.3f}、bq={slope_result['base_factor_q']:.3f}、bγ={slope_result['base_factor_gamma']:.3f}；地表係數：gc={slope_result['ground_factor_c']:.3f}、gq={slope_result['ground_factor_q']:.3f}、gγ={slope_result['ground_factor_gamma']:.3f}")
                if phi5>0:
                    st.caption(f"排水 Nγ 項有效單位重 γ′={slope_result['gamma_effective']:.2f} kN/m³；{slope_result['gamma_effective_method']}，修正係數={slope_result['gamma_effective_2025_factor']:.3f}。")
                else:
                    st.caption("ϕ=0 不排水分析不使用 Nγ 單位重項；Table 5-4 地表傾斜係數修正凝聚力項，覆土項另依 q₀=γDf cosαg 計算。")
                st.caption(slope_result["limitations"])
            elif slope_result:
                st.warning("輸入已變更，請重新執行斜坡／基底傾斜計算。")
    
        with st.expander("③ 多層地盤：強上層覆蓋弱下層穿刺破壞",expanded=False):
            st.caption("依 USACE 2025 式 5-17／5-18，採 2V:1H 應力擴散。分別計算上、下層同一基礎的極限承載力，再檢查穿刺控制。")
            la,lb,lc=st.columns(3)
            hb_layer_suffix5="hb" if use_hb5 else "manual"
            c_top_default5=0.0 if use_hb5 else float(c5)
            phi_top_default5=0.0 if use_hb5 else float(phi5)
            with la:
                c_top5=st.number_input("上層 c／Su [kPa]",0.0,100000.0,c_top_default5,1.0,key=f"m5x_c_top_{hb_layer_suffix5}")
                phi_top5=st.number_input("上層 φ [°]",0.0,50.0,phi_top_default5,1.0,key=f"m5x_phi_top_{hb_layer_suffix5}")
            with lb:
                c_low5=st.number_input("下層 c／Su [kPa]",0.0,100000.0,0.0,1.0,key=f"m5x_c_low_{hb_layer_suffix5}")
                phi_low5=st.number_input("下層 φ [°]",0.0,50.0,0.0,1.0,key=f"m5x_phi_low_{hb_layer_suffix5}")
            st.caption("多層穿刺分析各層 c／Su、φ 必須依該層試驗或地勘資料分別輸入；系統不再以固定 0.5c 或 0.7φ 推定下層強度。選用 Module 1 Hoek–Brown 來源時，各層欄位另行輸入，避免把單一岩體等效參數複製到不同地層。")
            with lc:
                strong_h5=st.number_input("強上層厚度 Hs [m]",0.05,20.0,1.0,0.05,key="m5x_hs")
                footing_kind5=st.selectbox("基礎型式",["isolated","continuous"],format_func=lambda x:"獨立／矩形基礎" if x=="isolated" else "連續條形基礎",key="m5x_layer_type")
            if footing_kind5=="continuous": st.caption("連續條形基礎按 L/B→∞ 的 strip 極限計算形狀係數；不採用目前 L 欄位的有限長寬比。")
            layer_check_unsupported=(H5>0 or beta5>0 or eB5>0 or eL5>0 or base_ang5>0 or ground_ang5>0)
            if layer_check_unsupported:
                st.warning("目前簡化兩層穿刺路徑尚未整合水平力、偏心及斜坡／傾斜基底修正；請先將這些作用設為 0，否則不會把結果當成完整設計檢核。")
            layer_hb_unsupported5=(use_hb5 and not hb_bearing_source_valid5)
            if layer_hb_unsupported5:
                st.warning("Module 1 等效參數尚未通過淺基礎適用性確認；多層穿刺計算已停用。")
            if st.button("計算多層穿刺承載力",key="m5x_layer_run",disabled=(layer_check_unsupported or layer_hb_unsupported5)):
                try:
                    top=bearing_capacity(theory="Meyerhof",c_kpa=c_top5,phi_deg=phi_top5,footing_type=footing_kind5,
                        gamma_moist=gamma5,gamma_sub=gsub5,gamma_below=gamma_below5,
                        B=B5,L=L5,Df=df5,water_depth=dw5,fs=fs5)
                    low=bearing_capacity(theory="Meyerhof",c_kpa=c_low5,phi_deg=phi_low5,footing_type=footing_kind5,
                        gamma_moist=gamma5,gamma_sub=gsub5,gamma_below=gamma_below5,
                        B=B5,L=L5,Df=df5,water_depth=dw5,fs=fs5)
                    layered=layered_bearing_capacity_punching(
                        q_ult_strong_kpa=top["qu_gross"],q_ult_weak_kpa=low["qu_gross"],
                        strong_layer_thickness_m=strong_h5,footing_width_m=B5,
                        footing_length_m=L5,footing_type=footing_kind5)
                    store_result_state(st.session_state, "m5x_layer_result", "m5x_layer_signature", layered, (src5,hb_source_signature,hb_confirmation_signature,bool(hb_bearing_material_confirmed5),bool(hb_stress_range_confirmed5),c_top5,phi_top5,c_low5,phi_low5,strong_h5,footing_kind5,B5,L5,gamma5,gsub5,gamma_below5,df5,dw5,H5,beta5,eB5,eL5,base_ang5,ground_ang5))
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"多層承載力計算失敗：{exc}")
            layer_sig=(src5,hb_source_signature,hb_confirmation_signature,bool(hb_bearing_material_confirmed5),bool(hb_stress_range_confirmed5),c_top5,phi_top5,c_low5,phi_low5,strong_h5,footing_kind5,B5,L5,gamma5,gsub5,gamma_below5,df5,dw5,H5,beta5,eB5,eL5,base_ang5,ground_ang5)
            layered, layer_is_current = read_result_state(st.session_state, "m5x_layer_result", "m5x_layer_signature", layer_sig)
            if layered and layer_is_current:

                _render_bearing_safety_check(
                    qult_kpa=layered["qult_kpa"],vertical_load_kN=V5,
                    width_m=B5,length_m=L5,depth_m=df5,water_depth_m=dw5,
                    footing_type=footing_kind5,complete_capacity_model=not layer_check_unsupported,
                    incomplete_reason="兩層穿刺承載力尚未包含目前輸入的水平力、偏心或斜坡／傾斜基底修正。",load_confirmed=loads_confirmed5)
                st.metric("控制總極限承載力",f"{layered['qult_kpa']:.1f} kPa")
                st.write(f"上層承載力 {layered['qult_strong_kpa']:.1f} kPa；下層穿刺換算 {layered['punching_capacity_kpa']:.1f} kPa；控制模式：{layered['controlling_mode']}")
                st.caption(layered["limitations"])
    
            elif layered:
                st.warning("輸入已變更，請重新執行多層穿刺計算。")
            st.markdown("**多層地盤剖面（可輸入 2 層以上）**")
            st.caption("每列為一個水平土層；厚度為自基礎底面向下的該層厚度。第一層另提供基礎上覆土天然／水下單位重。")
            profile_c5=0.0 if use_hb5 else float(c5)
            profile_phi5=0.0 if use_hb5 else float(phi5)
            multi_layer_csv5=st.text_area("多層土壤 CSV：thickness_m,c_kpa,phi_deg,gamma_below_kn_m3",
                value=f"thickness_m,c_kpa,phi_deg,gamma_below_kn_m3\\n1.0,{c_top5},{phi_top5},{gamma_below5}\\n2.0,{c_low5},{phi_low5},{gamma_below5}\\n3.0,{profile_c5},{profile_phi5},{gamma_below5}",
                height=110,key=f"m5x_multi_layer_csv_{hb_layer_suffix5}")
            if use_hb5:
                st.caption("Module 1 Hoek–Brown 參數不會自動複製至多層 CSV；請依每一層的地勘／試驗資料填入，僅在確認該層符合 §1-7(b) 時才可使用岩體等效參數。")
            if st.button("計算多層地盤穿刺／承載力",key="m5x_multi_layer_run",disabled=(use_hb5 and not hb_bearing_source_valid5)):
                try:
                    ml=pd.read_csv(StringIO(multi_layer_csv5))
                    required_cols={"thickness_m","c_kpa","phi_deg","gamma_below_kn_m3"}
                    if not required_cols.issubset(ml.columns):
                        raise ValueError("CSV 欄位不完整")
                    layer_rows=ml.to_dict("records")
                    layer_rows[0]["gamma_moist_kn_m3"]=gamma5
                    layer_rows[0]["gamma_sub_kn_m3"]=gsub5
                    mr=layered_bearing_capacity_profile(layers=layer_rows,
                        footing_width_m=B5,footing_length_m=L5,footing_depth_m=df5,
                        water_depth_m=dw5,fs=fs5,footing_type=footing_kind5,
                        eccentricity_B_m=eB5,eccentricity_L_m=eL5)
                    multi_layer_sig=(src5,hb_source_signature,hb_confirmation_signature,bool(hb_bearing_material_confirmed5),bool(hb_stress_range_confirmed5),multi_layer_csv5,B5,L5,df5,dw5,footing_kind5,eB5,eL5,gamma5,gsub5,gamma_below5,V5,H5,base_ang5,ground_ang5)
                    store_result_state(st.session_state, "m5x_multi_layer_result", "m5x_multi_layer_signature", mr, multi_layer_sig)
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"多層地盤分析失敗：{exc}")
            multi_layer_sig=(src5,hb_source_signature,hb_confirmation_signature,bool(hb_bearing_material_confirmed5),bool(hb_stress_range_confirmed5),multi_layer_csv5,B5,L5,df5,dw5,footing_kind5,eB5,eL5,gamma5,gsub5,gamma_below5,V5,H5,base_ang5,ground_ang5)
            mr, mr_is_current = read_result_state(st.session_state, "m5x_multi_layer_result", "m5x_multi_layer_signature", multi_layer_sig)
            if mr and mr_is_current:

                profile_check_unsupported=(H5>0 or beta5>0 or base_ang5>0 or ground_ang5>0)
                _render_bearing_safety_check(
                    qult_kpa=mr["qult_kpa"],vertical_load_kN=V5,
                    width_m=B5,length_m=L5,depth_m=df5,water_depth_m=dw5,
                    eccentricity_B_m=eB5,eccentricity_L_m=eL5,
                    footing_type=footing_kind5,complete_capacity_model=not profile_check_unsupported,
                    incomplete_reason="多層剖面計算尚未整合水平力及斜坡／傾斜基底修正。",load_confirmed=loads_confirmed5)
                st.metric("多層地盤控制總極限承載力",f"{mr['qult_kpa']:.1f} kPa")
                st.write(f"控制模式：{mr['controlling_mode']}；控制層：第 {mr['controlling_layer']} 層")
                st.dataframe(pd.DataFrame(mr["layers"]),hide_index=True,use_container_width=True)
                if mr.get("warning"):
                    st.warning(mr["warning"])
                st.caption(mr["limitations"])
    
        with st.expander("④ 地震等效靜力載重包絡（偽靜力）",expanded=False):
            st.warning("此面板將 kh、kv 轉成基礎慣性等效作用，並非完整地震承載力分析；不包含土體慣性、液化、循環強度折減或震陷。")
            st.caption("H5 為地震前既有靜力水平力（不含地震慣性力）；W 為有效地震重量，系統採 H+khW 及 V±kvW。W 預設等於 V5 供初步估算；若結構耐震分析已提供有效地震重量，請改填該值。")
            ea,eb,ec=st.columns(3)
            with ea:
                kh5=st.number_input("水平地震係數 kh",0.0,1.0,0.15,0.01,key="m5x_kh")
            with eb:
                kv5=st.number_input("垂直地震係數 kv（輸入正值大小；自動計算向下增／減）",0.0,0.5,0.0,0.01,key="m5x_kv")
            with ec:
                seismic_footing5=st.selectbox("地震偏心／孔壓承載力基礎型式",["spread","strip"],
                    index=0 if footing_kind5=="isolated" else 1,
                    format_func=lambda x:"獨立／擴展基礎" if x=="spread" else "連續條形基礎",
                    key="m5x_seismic_footing")
                seismic_area_default5=max(0.1,(B5-2*eB5) if seismic_footing5=="strip" else (B5-2*eB5)*(L5-2*eL5))
                seismic_area_unit5="m²/m" if seismic_footing5=="strip" else "m²"
                seismic_force_unit5="kN/m" if seismic_footing5=="strip" else "kN"
                seismic_moment_unit5="kN·m/m" if seismic_footing5=="strip" else "kN·m"
                area5=st.number_input(f"基礎有效面積 A′ [{seismic_area_unit5}]",0.1,5000.0,float(seismic_area_default5),0.1,key=f"m5x_area_{seismic_footing5}")
                seismic_weight5=st.number_input(f"有效地震重量 W [{seismic_force_unit5}]（預設 V）",0.1,1000000.0,float(max(0.1,V5)),10.0,key=f"m5x_seismic_weight_{seismic_footing5}")
                st.caption("連續條形基礎請使用每延米：V、H、W 為 kN/m，A′ 為 m²/m（數值按 B′×1 m），彎矩為 kN·m/m。切換基礎型式後，面積、重量及彎矩欄位會使用各自的單位狀態。")
            sm1,sm2=st.columns(2)
            with sm1:
                seismic_moment_B5=st.number_input(f"地震基礎底彎矩 M_B,E [{seismic_moment_unit5}]（短邊偏心方向）",-10000000.0,10000000.0,0.0,10.0,key=f"m5x_seismic_moment_B_{seismic_footing5}")
            with sm2:
                seismic_moment_L5=st.number_input(f"地震基礎底彎矩 M_L,E [{seismic_moment_unit5}]（長邊偏心方向）",-10000000.0,10000000.0,0.0,10.0,key=f"m5x_seismic_moment_L_{seismic_footing5}")
            st.markdown("**地震彎矩與偏心檢核（一般地震載重適用，不依賴孔壓折減條件）**")
            st.caption("請輸入結構耐震分析傳至基礎底面的水平地震彎矩分量；正負號以 +kh 方向為基準，系統假設反向作用時彎矩線性反號。靜力偏心距 eB/eL 會先換算為帶方向的靜力彎矩 V·e。連續基礎請使用每延米彎矩（kN·m/m），且不支援長邊方向彎矩。此兩個彎矩輸入會供本區一般地震偏心檢核及下方地震孔壓折減承載力使用，不會改變上方單純 H/V 等效載重表。")
            if kh5>0 and abs(seismic_moment_B5)<1e-9 and abs(seismic_moment_L5)<1e-9:
                st.warning("目前兩個地震基礎底彎矩均為 0；系統不會由 khW 自行猜測作用高度。若結構分析已有地震彎矩，請輸入其傳至基礎底面的帶符號分量；未輸入時結果不包含地震傾覆偏心。")
            sd1,sd2=st.columns(2)
            with sd1:
                static_moment_B_sign5=st.selectbox("靜力短邊偏心方向",options=[1,-1],format_func=lambda x:"+B 方向" if x==1 else "−B 方向",key="m5x_static_moment_B_sign")
            with sd2:
                static_moment_L_sign5=st.selectbox("靜力長邊偏心方向",options=[1,-1],format_func=lambda x:"+L 方向" if x==1 else "−L 方向",key="m5x_static_moment_L_sign")
            seismic_qallow5=st.number_input("地震設計容許承載壓力 q_allow [kPa]（0＝未提供，不判定整體通過）",
                min_value=0.0,max_value=50000.0,value=0.0,step=1.0,key="m5x_seismic_qallow",help="請依適用建築法規／專案設計準則輸入；系統不自動套用地震容許承載力提高係數，也不直接以靜力 qult/FS 代替。")
            seismic_qallow_value5=(seismic_qallow5 if seismic_qallow5>0 else None)
            residual_base_excess_pore_pressure_kpa5=st.number_input(
                "基礎底面殘餘超額孔隙水壓 Δu_res,base [kPa]",0.0,100000.0,0.0,1.0,
                key="m5x_residual_base_u",
                help="若基礎底面土層亦受地震超額孔壓影響，可依 Δu_res,base=ru×σ′v0(Df) 估算；σ′v0 必須依實際分層土層與水位計算。有場址專屬孔壓分析時，優先輸入基底平均殘餘超額孔壓。")
            base_residual_pressure_confirmed5=st.checkbox(
                "已確認基礎底面殘餘超額孔隙水壓 Δu_res,base；輸入 0 代表確認基礎底面沒有額外殘餘超額孔壓",
                value=False,key="m5x_residual_base_u_confirm")
            base_hydrostatic_uD5=max(0.0,(float(df5)-float(dw5))*9.81)
            base_uplift_pressure_kpa5=base_hydrostatic_uD5+(residual_base_excess_pore_pressure_kpa5 if base_residual_pressure_confirmed5 else 0.0)
            seismic_qallow_for_base_pressure5=(seismic_qallow_value5 if base_residual_pressure_confirmed5 else None)
            st.caption(f"地震 qeq 使用基底總孔隙水壓 u_D={base_uplift_pressure_kpa5:.2f} kPa（靜水壓 {base_hydrostatic_uD5:.2f} + 已確認殘餘超額孔壓 {base_uplift_pressure_kpa5-base_hydrostatic_uD5:.2f} kPa）。")
            if seismic_qallow_value5 is not None and not base_residual_pressure_confirmed5:
                st.warning("已輸入 q_allow，但尚未確認基礎底面殘餘超額孔隙水壓；系統暫不執行 qeq≤q_allow 通過判定，以免漏扣地震殘餘孔壓。")
            seismic_ecc_sig5=(V5,H5,seismic_weight5,kh5,kv5,seismic_footing5,B5,L5,eB5,eL5,
                seismic_moment_B5,seismic_moment_L5,static_moment_B_sign5,static_moment_L_sign5,
                seismic_qallow_for_base_pressure5,base_uplift_pressure_kpa5,
                residual_base_excess_pore_pressure_kpa5,base_residual_pressure_confirmed5)
            if st.button("計算地震傾覆幾何與有效承載壓力",key="m5x_seismic_ecc_run"):
                try:
                    seismic_ecc5=seismic_foundation_eccentricity_cases(
                        vertical_load_kN=V5,horizontal_load_kN=H5,
                        seismic_weight_kN=seismic_weight5,kh=kh5,kv=kv5,
                        footing_type=seismic_footing5,B=B5,L=L5,
                        eccentricity_B=eB5,eccentricity_L=eL5,
                        seismic_moment_B_kNm=seismic_moment_B5,
                        seismic_moment_L_kNm=seismic_moment_L5,
                        static_moment_B_sign=static_moment_B_sign5,
                        static_moment_L_sign=static_moment_L_sign5,
                        allowable_bearing_pressure_kpa=seismic_qallow_for_base_pressure5,
                        base_uplift_pressure_kpa=base_uplift_pressure_kpa5)
                    store_result_state(st.session_state,"m5x_seismic_ecc_result","m5x_seismic_ecc_signature",seismic_ecc5,seismic_ecc_sig5)
                except Exception as ecc_exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"地震傾覆幾何／有效承載壓力檢核失敗：{ecc_exc}")
            seismic_ecc5,seismic_ecc_current5=read_result_state(
                st.session_state,"m5x_seismic_ecc_result","m5x_seismic_ecc_signature",seismic_ecc_sig5)
            if seismic_ecc5 and seismic_ecc_current5:
                st.metric("地震合力位置／有效接觸檢核","全部組合位於基礎範圍內" if seismic_ecc5["geometry_passes"] else "有組合超出基礎範圍")
                if not seismic_ecc5["geometry_passes"]:
                    st.error("至少一組地震載重組合的合力超出基礎底面範圍、有效尺寸非正或有效軸向交換；須另作接觸／抗拔／雙向偏心分析。")
                if not seismic_ecc5["middle_third_passes"]:
                    st.info("部分組合超出靜力中間三分點。依 USACE §9-10(e)，地震極端事件的判斷不以靜力中三分點作唯一標準；仍須確認 qeq 不超過適用的地震容許承載壓力，若專案規範另要求中三分點則仍應遵守。")
                st.caption(f"已依 USACE 式 5-2／5-3 扣除基礎底面總孔隙水壓 u_D={seismic_ecc5['base_uplift_pressure_kpa']:.2f} kPa；其中殘餘超額孔壓由使用者確認輸入，不由 ru 自動推估。")
                if not seismic_ecc5["uplift_contact_passes"]:
                    st.error("至少一組地震組合扣除基礎底面總孔隙水壓後未維持正向接觸壓力，須另作抗浮／揚壓檢核。")
                if seismic_ecc5["bearing_pressure_check_complete"]:
                    st.metric("地震有效承載壓力 qeq ≤ q_allow",
                        "全部組合符合" if seismic_ecc5["bearing_pressure_passes"] else "有組合超過")
                    if seismic_ecc5["overall_seismic_overturning_passes"] is False:
                        st.error("地震傾覆／承載整體檢核未通過：合力位置或有效承載壓力至少一項不符合。")
                else:
                    if seismic_qallow_value5 is not None and not base_residual_pressure_confirmed5:
                        st.warning("尚未確認基礎底面殘餘超額孔隙水壓；目前僅回報合力位置與幾何，暫不判定 qeq≤q_allow。")
                    else:
                        st.warning("尚未提供適用規範／專案的地震 q_allow；目前只有合力位置與有效尺寸幾何檢核，不代表整體地震傾覆／承載通過。")
                st.dataframe(_seismic_case_dataframe(seismic_ecc5["cases"],seismic_footing5),hide_index=True,use_container_width=True)
                st.caption(seismic_ecc5["limitations"])
            if st.button("計算地震等效載重",key="m5x_seismic_run"):
                try:
                    seismic=seismic_bearing_capacity_pseudostatic(vertical_load_kN=V5,
                        horizontal_load_kN=H5,footing_area_m2=area5,kh=kh5,kv=kv5,
                        seismic_weight_kN=seismic_weight5)
                    store_result_state(st.session_state, "m5x_seismic_result", "m5x_seismic_signature", seismic, (V5,H5,area5,kh5,kv5,seismic_weight5,seismic_footing5))
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"地震等效載重計算失敗：{exc}")
            seismic, seismic_is_current = read_result_state(st.session_state, "m5x_seismic_result", "m5x_seismic_signature", (V5,H5,area5,kh5,kv5,seismic_weight5,seismic_footing5))
            if seismic and seismic_is_current:
                st.dataframe(_seismic_case_dataframe(seismic["cases"],seismic_footing5),hide_index=True,use_container_width=True)
    
                st.caption(seismic["limitations"])
            st.markdown("**地震超額孔隙水壓／強度損失之承載力折減（USACE 2025 式 9-3／9-4）**")
            st.caption("僅適用砂狀排水土（c′≈0、φ′>0）。依 USACE §9-10(c)(3)，FS_liq 必須 >1.0，且須確認不預期顯著側向擴展；FS_liq≤1.0 或顯著側向擴展時不得使用本式，應改採液化後殘餘強度、穿刺剪力及整體穩定分析。邊際液化範圍 1.0<FS_liq≤1.4 可在符合上述條件時使用式 9-3／9-4，ru 必須由 Figure 9-1 或場址專屬孔壓分析取得。超額孔隙水壓可選完整或部分剪力區；部分區另須提供 f 及兩種土層有效單位重。此分支僅支援水平基底與水平地表。")
            st.info("本區將水平地震作用按與既有 H 同向的不利包絡 H+kh·W，並計算兩個垂直地震方向 V±kvW，再套用 Meyerhof 載重傾斜與 USACE 形狀、深度及地下水修正。方向性限制：只有水平基底、水平地表才可使用；地震水平力反向相對於斜坡／傾斜基底的作用方向尚未建模，非零坡角會停用本計算。地震彎矩造成的偏心已逐組合計算；地震傾覆幾何依 §9-10(e) 檢核合力是否位於基礎範圍內，中三分點另列為靜力參考。部分剪力區可依手冊以使用者輸入的加權比例與兩種有效單位重估算 γ′b，但系統不會自動由地層深度推定比例。仍未納入基底殘餘超額孔壓上拔及土體慣性；孔壓折減極限抗力不是地震 FS，完整承載壓力檢核須提供適用的地震 q_allow。另請注意：表 2-1 註 2 的 FS=1.1 僅適用滑動，不是承載力地震 FS；承載力風震容許應力增幅須依適用建築法規／UFC，且土層有剪力強度損失（SSL）疑慮時不得採用。")
            ss1,ss2,ss3=st.columns(3)
            with ss1:
                ru5=st.number_input("殘餘超額孔隙水壓比 ru",0.0,0.99,0.0,0.01,key="m5x_ru",
                    help="USACE §9-9c 定義 ru=殘餘超額孔隙水壓／初始有效上覆應力；請依 Figure 9-1 或場址專屬孔壓分析取得。")
            fsliq5=st.number_input("剪力區液化安全係數 FS_liq",0.0,10.0,0.0,0.05,key="m5x_fs_liq",
                help="須由獨立液化評估取得；FS_liq≤1.0 不得使用式 9-3／9-4。")
            no_significant_lateral_spreading_confirmed5=st.checkbox("已依場址評估確認不預期顯著側向擴展",value=False,key="m5x_no_significant_lateral_spreading")
            ru_source_confirmed5=st.checkbox("ru 已由 USACE Figure 9-1（依 FS_liq）或場址專屬孔壓分析取得；若 ru=0，代表已確認無殘餘超額孔壓",value=False,key="m5x_ru_source_confirm")
            seismic_pore_pressure_applicability_ready5=(fsliq5>1.0 and no_significant_lateral_spreading_confirmed5 and ru_source_confirmed5)
            if 0.0<fsliq5<=1.0:
                st.error("FS_liq≤1.0：可能已觸發液化，式 9-3／9-4 不適用；請改採液化後殘餘強度及穿刺剪力／整體穩定分析。")
            elif 1.0<fsliq5<=1.4:
                st.info("目前屬邊際液化範圍；在不預期顯著側向擴展且 ru 來源確認後，可依 §9-10(c)(3) 使用本式評估。")
                if ru5==0.0:
                    st.warning("FS_liq 位於邊際液化範圍但 ru=0；請再次核對 Figure 9-1 或場址孔壓分析，勿將預設 0 當成無孔壓的證據。")
            with ss2:
                st.caption("Nγ、γ′、形狀／深度／載重傾斜／基底／地表修正將依目前 φ、基礎幾何、地下水及地震合力 H_eq/V_eq 組合自動計算，不再要求手動猜測係數。")
            with ss3:
                st.caption("兩組垂直地震係數方向均會計算，並以較低地震極限抗力作控制。")
            shear_zone_mode5=st.selectbox("超額孔隙水壓影響範圍",["unconfirmed","full","partial"],
                format_func=lambda x:{"unconfirmed":"尚未確認","full":"影響完整承載力剪力區","partial":"僅影響部分剪力區（加權平均）"}[x],
                key="m5x_shear_zone_mode")
            full_shear_zone_confirmed5=(shear_zone_mode5=="full")
            partial_shear_zone_affected_fraction5=None
            gamma_effective_susceptible5=None
            gamma_effective_unaffected5=None
            partial_zone_inputs_confirmed5=False
            if shear_zone_mode5=="partial":
                gamma_effective_default5=float(gamma_below5)*min(0.45+0.55*(max(float(dw5)-float(df5),0.0)/max(float(B5),1e-9)),1.0)
                pf1,pf2=st.columns(2)
                with pf1:
                    partial_shear_zone_affected_fraction5=st.number_input("受影響剪力區加權比例 f",0.01,0.99,0.50,0.01,key="m5x_partial_shear_fraction",
                        help="預設 0.50 僅為欄位初始值，不是建議比例；須依 USACE Figure 5-4 承載力剪力區內受影響土層的分布／體積比例自行判讀，不是整個鑽孔深度比例。")
                    gamma_effective_susceptible5=st.number_input("受影響土層有效單位重 γ′sus [kN/m³]",0.1,40.0,float(max(0.1,gamma_effective_default5)),0.1,key="m5x_gamma_sus",
                        help="輸入受影響土層在相應地下水條件下的有效／浮單位重。")
                with pf2:
                    gamma_effective_unaffected5=st.number_input("未受影響土層有效單位重 γ′unaff [kN/m³]",0.1,40.0,float(max(0.1,gamma_effective_default5)),0.1,key="m5x_gamma_unaff",
                        help="輸入未受超額孔隙水壓影響土層在相應地下水條件下的有效／浮單位重。")
                st.caption("部分區加權公式：γ′b = f(1−ru)γ′sus + (1−f)γ′unaff。系統不自動推定 f；依 Eq. 5-19 預填的單位重僅為起始參考，若有分層資料須自行修正。")
                partial_zone_inputs_confirmed5=st.checkbox("已依 Figure 5-4 剪力區範圍與地層資料確認 f、γ′sus、γ′unaff",value=False,key="m5x_partial_zone_inputs_confirm")
            shear_zone_ready5=(full_shear_zone_confirmed5 or
                (shear_zone_mode5=="partial" and partial_zone_inputs_confirmed5
                 and partial_shear_zone_affected_fraction5 is not None
                 and gamma_effective_susceptible5 is not None and gamma_effective_unaffected5 is not None))
            if not (seismic_pore_pressure_applicability_ready5 and shear_zone_ready5):
                st.warning("請先輸入 FS_liq>1.0、確認不預期顯著側向擴展、確認 ru 來源，並選擇完整或部分剪力區影響範圍；部分區須填妥 f 與兩種有效單位重。")
            seismic_geometry_unsupported5 = (abs(base_ang5) > 1e-9 or abs(ground_ang5) > 1e-9)
            if seismic_geometry_unsupported5:
                st.warning("目前輸入含非零基底或地表傾角。由於地震水平力正反向相對於坡面／基底的方向性尚未建模，已停用地震孔壓折減承載力；請勿將靜力斜坡修正直接視為地震修正。")
            if use_hb5:
                st.warning("USACE §9-10(c)(3) 式 9-3／9-4 僅適用砂狀、近似無凝聚力的土壤；Module 1 Hoek–Brown 岩體等效參數不可用於此孔壓折減分支。請切回手動輸入並提供砂土 c′≈0、φ′>0 參數。")
            if st.button("計算地震孔壓折減承載力",key="m5x_seismic_capacity_run",disabled=(use_hb5 or not (seismic_pore_pressure_applicability_ready5 and shear_zone_ready5) or seismic_geometry_unsupported5)):
                try:
                    sr=seismic_bearing_capacity_residual_pore_pressure_cases(
                        vertical_load_kN=V5,horizontal_load_kN=H5,kh=kh5,kv=kv5,
                        seismic_weight_kN=seismic_weight5,
                        seismic_moment_B_kNm=seismic_moment_B5,
                        seismic_moment_L_kNm=seismic_moment_L5,
                        static_moment_B_sign=static_moment_B_sign5,
                        static_moment_L_sign=static_moment_L_sign5,
                        footing_type=seismic_footing5,
                        residual_excess_pore_pressure_ratio=ru5,
                        factor_of_safety_liquefaction=fsliq5,
                        no_significant_lateral_spreading_confirmed=no_significant_lateral_spreading_confirmed5,
                        ru_source_confirmed=ru_source_confirmed5,
                        full_shear_zone_confirmed=full_shear_zone_confirmed5,
                        partial_shear_zone_affected_fraction=partial_shear_zone_affected_fraction5,
                        gamma_effective_susceptible_kn_m3=gamma_effective_susceptible5,
                        gamma_effective_unaffected_kn_m3=gamma_effective_unaffected5,
                        c_kpa=c5,phi_deg=phi5,gamma_moist=gamma5,
                        gamma_sub=gsub5,gamma_below=gamma_below5,
                        B=B5,L=L5,Df=df5,water_depth=dw5,
                        eccentricity_B=eB5,eccentricity_L=eL5,
                        base_inclination_deg=base_ang5,
                        ground_inclination_deg=ground_ang5,
                        slope_distance_m=slope_dist5,
                        adjacent_slope_fs=(slope_fs5 if ground_ang5>0 else None),
                        base_uplift_pressure_kpa=base_uplift_pressure_kpa5)
                    store_result_state(st.session_state, "m5x_seismic_capacity_result", "m5x_seismic_capacity_signature", sr,
                        (src5,hb_source_signature,hb_confirmation_signature,bool(hb_bearing_material_confirmed5),bool(hb_stress_range_confirmed5),V5,H5,kh5,kv5,seismic_weight5,seismic_moment_B5,seismic_moment_L5,static_moment_B_sign5,static_moment_L_sign5,ru5,seismic_footing5,c5,phi5,gamma5,gsub5,gamma_below5,B5,L5,df5,dw5,eB5,eL5,base_ang5,ground_ang5,slope_dist5,slope_fs5,shear_zone_mode5,partial_shear_zone_affected_fraction5,gamma_effective_susceptible5,gamma_effective_unaffected5,partial_zone_inputs_confirmed5,fsliq5,no_significant_lateral_spreading_confirmed5,ru_source_confirmed5,
                        base_uplift_pressure_kpa5,residual_base_excess_pore_pressure_kpa5,base_residual_pressure_confirmed5))
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"地震孔壓折減承載力計算失敗：{exc}")
            sr_sig=(src5,hb_source_signature,hb_confirmation_signature,bool(hb_bearing_material_confirmed5),bool(hb_stress_range_confirmed5),V5,H5,kh5,kv5,seismic_weight5,seismic_moment_B5,seismic_moment_L5,static_moment_B_sign5,static_moment_L_sign5,ru5,seismic_footing5,c5,phi5,gamma5,gsub5,gamma_below5,B5,L5,df5,dw5,eB5,eL5,base_ang5,ground_ang5,slope_dist5,slope_fs5,shear_zone_mode5,partial_shear_zone_affected_fraction5,gamma_effective_susceptible5,gamma_effective_unaffected5,partial_zone_inputs_confirmed5,fsliq5,no_significant_lateral_spreading_confirmed5,ru_source_confirmed5,
                base_uplift_pressure_kpa5,residual_base_excess_pore_pressure_kpa5,base_residual_pressure_confirmed5)
            sr, sr_is_current = read_result_state(st.session_state, "m5x_seismic_capacity_result", "m5x_seismic_capacity_signature", sr_sig)
            if sr and sr_is_current:
                if sr["qu_seismic_governing_kpa"] is None:
                    st.metric("控制地震孔壓折減極限承載力","無有效值")
                    st.error(sr["governing_case"].get("zero_resistance_reason","至少一組地震組合未能維持有效壓縮接觸；請另作接觸壓力／雙向偏心分析。"))
                else:
                    st.metric("控制地震孔壓折減極限承載力",f"{sr['qu_seismic_governing_kpa']:.1f} kPa")
                if not sr.get("overturning_geometry_check_pass",sr.get("overturning_check_pass",True)):
                    st.error("至少一組地震載重組合的合力超出基礎底面範圍、有效尺寸非正或有效軸向交換；依 USACE §9-10(e) 幾何檢核不符合。")
                if not sr.get("middle_third_check_pass",True):
                    st.info("至少一組地震組合超出靜力中間三分點。地震極端事件不以此作唯一判定；仍須檢核有效承載壓力是否不超過適用的地震 q_allow。")
                st.caption(f"適用性輸入：FS_liq={sr['factor_of_safety_liquefaction']:.2f}；ru={sr['ru']:.2f}；已確認無顯著側向擴展及 ru 來源。")
                st.caption(f"已依 USACE 式 5-2／5-3 扣除基礎底面總孔隙水壓 u_D={sr['base_uplift_pressure_kpa']:.2f} kPa；此值含已確認輸入的基底殘餘超額孔壓。")
                if any(case.get("average_contact_pressure_kpa") is not None and case["average_contact_pressure_kpa"]<=0 for case in sr["cases"]):
                    st.error("至少一組地震組合扣除基礎底面總孔隙水壓後未維持正向接觸壓力，須另作抗浮／揚壓檢核。")
                if seismic_qallow_for_base_pressure5 is not None:
                    sr_qallow_cases=[case for case in sr["cases"] if case.get("average_contact_pressure_kpa") is not None]
                    sr_qallow_pass=(len(sr_qallow_cases)==len(sr["cases"]) and all(0.0<case["average_contact_pressure_kpa"]<=seismic_qallow_for_base_pressure5 for case in sr_qallow_cases))
                    st.metric("孔壓折減分支地震 qeq ≤ q_allow","全部組合符合" if sr_qallow_pass else "有組合超過／無有效值")
                    if not sr_qallow_pass:
                        st.error("孔壓折減分支至少一組有效承載壓力超過 q_allow，或無法計算有效接觸壓力。")
                else:
                    if seismic_qallow_value5 is not None and not base_residual_pressure_confirmed5:
                        st.warning("尚未確認基礎底面殘餘超額孔隙水壓；本分支暫不判定 qeq≤q_allow。")
                    else:
                        st.warning("未提供地震設計容許承載壓力 q_allow；本分支僅回報孔壓折減極限抗力與偏心幾何，不代表地震承載安全通過。")
                st.dataframe(_seismic_case_dataframe(sr['cases'],seismic_footing5),hide_index=True,use_container_width=True)
                st.caption(sr["limitations"])
    
    
        with st.expander("⑤ 基礎底面滑動安全係數",expanded=False):
            st.caption("依 USACE 2025 式 5-28／5-29。基底摩擦、黏著、揚壓力分別輸入；主動／被動土壓需先以 developed strength 另行計算。")
            slide_footing5=st.selectbox("滑動檢核基礎型式",["isolated","continuous"],
                index=0 if seismic_footing5=="spread" else 1,
                format_func=lambda x:"獨立／矩形基礎" if x=="isolated" else "連續條形基礎",
                key="m5x_slide_footing")
            slide_is_line5=(slide_footing5=="continuous")
            slide_force_unit5="kN/m" if slide_is_line5 else "kN"
            slide_area_unit5="m²/m" if slide_is_line5 else "m²"
            slide_area_default5=max(0.1,B5*(1.0 if slide_is_line5 else L5))
            slide_area_key5="m5x_slide_area_continuous" if slide_is_line5 else "m5x_slide_area_isolated"
            if slide_is_line5:
                st.info("連續條形基礎採每延米線荷載：V、U、H、Pa、Pp 使用 kN/m；基底面積 A 使用 m²/m，預設為 B×1 m。若上方輸入為總力，請先換算為每延米。")
            sa,sb,sc=st.columns(3)
            with sa:
                slide_v5=st.number_input(f"靜力總垂直力 V [{slide_force_unit5}]",0.1,1000000.0,float(V5),10.0,key="m5x_slide_v")
                slide_u5=st.number_input(f"基底揚壓力合力 U [{slide_force_unit5}]",0.0,1000000.0,0.0,10.0,key="m5x_slide_u",
                    help="地震抗浮檢核使用整個基礎底面的總揚壓合力；應包含靜水壓及地震殘餘超額孔隙水壓，不是單位面積壓力。")
                slide_h5=st.number_input(f"靜力水平力 H [{slide_force_unit5}]（不含 khW）",0.0,1000000.0,float(H5),10.0,key="m5x_slide_h")
            with sb:
                slide_area5=st.number_input(f"基底接觸面積 A [{slide_area_unit5}]",0.1,5000.0,float(slide_area_default5),0.1,key=slide_area_key5)
                slide_phi5=st.number_input("基底界面摩擦角 δ′ [°]",0.0,50.0,(0.0 if use_hb5 else float(phi5)),1.0,key=f"m5x_slide_phi_{'hb' if use_hb5 else 'manual'}")
                slide_c5=st.number_input("基底土層 c′／Su [kPa]",0.0,100000.0,0.0,1.0,key=f"m5x_slide_c_{'hb' if use_hb5 else 'manual'}")
            with sc:
                slide_ar5=st.number_input("基底黏著比 ca/c′（或 ca/Su）",0.0,1.0,0.0,0.05,key="m5x_slide_ar")
                slide_pa5=st.number_input(f"主動土壓力 Pa [{slide_force_unit5}]",0.0,1000000.0,0.0,10.0,key="m5x_slide_pa")
                slide_pp5=st.number_input(f"已折減被動抗力 Pp [{slide_force_unit5}]",0.0,1000000.0,0.0,10.0,key="m5x_slide_pp")
            slide_case5=st.selectbox("荷載組合",["常時／靜力","含地震荷載"],index=0,key="m5x_slide_case")
            slide_load_case5="seismic" if slide_case5=="含地震荷載" else "static"
            slide_req5=st.number_input("要求滑動安全係數",1.1,5.0,2.0,0.1,key="m5x_slide_req")
            slide_min_fs5=1.1 if slide_load_case5=="seismic" else 2.0
            slide_uplift_resisting_weight5=st.number_input(f"抗浮永久向下重量 Wf+Ws+Wc [{slide_force_unit5}]",0.0,1000000.0,0.0,10.0,key="m5x_uplift_resisting_weight",
                help="依 USACE Eq. 5-36：Wf 含基礎及基礎承載高程以上土重；Ws 含結構／固定設備及結構頂面以上土重；Wc 為結構內水重。只輸入可計入抗浮的重量。")
            slide_uplift_weights_confirmed5=st.checkbox("已確認 Wf+Ws+Wc 為可計入抗浮的永久重量，且上方 W 代表結構重量 Ws 並包含於此總重量",value=False,key="m5x_uplift_weights_confirm")
            slide_uplift_pressure_confirmed5=st.checkbox("已確認 U 為整個基礎底面的總揚壓合力，包含靜水壓及地震殘餘超額孔隙水壓",value=False,key="m5x_uplift_pressure_confirm")
            uplift_units_match5=(slide_is_line5==(seismic_footing5=="strip"))
            hydrostatic_uD5=max(0.0,(float(df5)-float(dw5))*9.81)
            uplift_base_area5=float(B5)*(1.0 if slide_is_line5 else float(L5))
            hydrostatic_U_ref5=base_uplift_pressure_kpa5*uplift_base_area5
            st.caption(f"基底總孔隙水壓參考值 u_D={base_uplift_pressure_kpa5:.2f} kPa（靜水壓 {hydrostatic_uD5:.2f} + 已確認殘餘超額孔壓 {base_uplift_pressure_kpa5-hydrostatic_uD5:.2f}）；對應 U_ref≈{hydrostatic_U_ref5:.2f} {slide_force_unit5}。")
            if abs(float(slide_area5)-uplift_base_area5)>max(0.01,0.01*uplift_base_area5):
                st.warning("滑動面積 A 與基礎幾何 B×L（連續基礎 B×1 m）不一致；抗浮 U 應以完整基礎底面積積分，請核對 U。")
            if slide_u5+1e-9<hydrostatic_U_ref5:
                st.warning("目前輸入 U 小於僅由地下水位估算的靜水揚壓參考值；請核對基底面積、水位及 U，避免低估揚壓。")
            if not uplift_units_match5:
                st.warning("抗浮檢核的基礎型式與上方地震重量 W 的單位型式不同；請將兩者統一為 kN 或 kN/m 後再計算。")
            slide_uplift_ready5=(slide_load_case5=="seismic" and slide_u5>0 and slide_u5+1e-9>=hydrostatic_U_ref5
                and slide_uplift_resisting_weight5>0 and slide_uplift_weights_confirmed5
                and slide_uplift_pressure_confirmed5 and uplift_units_match5
                and abs(float(slide_area5)-uplift_base_area5)<=max(0.01,0.01*uplift_base_area5))
            st.caption(f"USACE 2025 表 2-1：常時滑動 FS ≥ 2.0；只有含地震荷載組合時，註 2 才允許降至 FS ≥ 1.1。目前組合最低要求：{slide_min_fs5:.1f}。地震抗浮另依 §9-10(f) 要求 FS≥1.5，不可使用滑動 FS=1.1 取代。")
            st.caption("地震模式會自動讀取上方 Module 5 的 kh、kv、W，組合 H_eq=H+khW 與 V_eq=V±kvW，並取兩組垂直方向中較小的滑動 FS。此處 H、V 請輸入未含地震增量的靜力基準值，避免重複計入。基底揚壓 U 與 Pa/Pp 仍須依實際水位及控制水平作用方向另行確認；不對稱回填幾何請輸入正反向中較不利的 Pa/Pp。另有獨立地震抗浮 FS 檢核：Wf+Ws+Wc、Ws 與 U 必須依 §5-7／§9-10(f) 定義輸入。")
            auto_earth5=st.checkbox("依 USACE developed strength 自動估算 Rankine 主動／被動土壓",value=False,key="m5x_slide_auto_earth")
            slide_gamma5=st.number_input("回填土有效單位重 γ′ [kN/m³]",1.0,25.0,float(max(1.0,min(25.0,gsub5))),0.5,key="m5x_slide_gamma")
            slide_backfill_phi5=st.number_input("回填土摩擦角 φ′ [°]",0.0,50.0,(0.0 if use_hb5 else float(phi5)),1.0,key=f"m5x_slide_backfill_phi_{'hb' if use_hb5 else 'manual'}")
            slide_backfill_c5=st.number_input("回填土凝聚力 c′ [kPa]",0.0,100000.0,(0.0 if use_hb5 else float(c5)),1.0,key=f"m5x_slide_backfill_c_{'hb' if use_hb5 else 'manual'}")
            if use_hb5:
                st.warning("基底界面 δ′、界面 c′／Su 與回填土 φ′、c′ 是獨立材料參數，不應直接沿用 Module 1 岩體等效 c′、φ′；目前已將這些欄位預設為 0，請依界面試驗／粗糙度與回填土資料輸入。")
            if st.button("計算基底滑動安全係數",key="m5x_slide_run"):
                try:
                    if auto_earth5:
                        earth=developed_rankine_sliding_earth_pressures(
                            effective_unit_weight_kn_m3=slide_gamma5,footing_depth_m=df5,
                            footing_length_m=(1.0 if slide_is_line5 else L5),friction_angle_deg=slide_backfill_phi5,
                            cohesion_kpa=slide_backfill_c5,fs_sliding=slide_req5,
                            load_case=slide_load_case5)
                        active_used=earth["active_force_kN"]
                        passive_used=earth["passive_force_kN"]
                        st.session_state["m5x_slide_earth_result"]=earth
                    else:
                        active_used=slide_pa5
                        passive_used=slide_pp5
                        st.session_state["m5x_slide_earth_result"]=None
                    if slide_load_case5=="seismic":
                        slide=foundation_sliding_pseudostatic_cases(
                            vertical_load_kN=slide_v5,uplift_kN=slide_u5,
                            horizontal_load_kN=slide_h5,seismic_weight_kN=seismic_weight5,
                            kh=kh5,kv=kv5,area_m2=slide_area5,
                            friction_angle_deg=slide_phi5,cohesion_kpa=slide_c5,
                            adhesion_ratio=slide_ar5,active_force_kN=active_used,
                            passive_force_kN=passive_used,fs_required=slide_req5)
                    else:
                        slide=foundation_sliding_factor_of_safety(vertical_load_kN=slide_v5,
                            uplift_kN=slide_u5,horizontal_load_kN=slide_h5,area_m2=slide_area5,
                            friction_angle_deg=slide_phi5,cohesion_kpa=slide_c5,
                            adhesion_ratio=slide_ar5,active_force_kN=active_used,
                            passive_force_kN=passive_used,fs_required=slide_req5,
                            load_case=slide_load_case5)
                    store_result_state(st.session_state, "m5x_slide_result", "m5x_slide_signature", slide, (src5,slide_v5,slide_u5,slide_h5,slide_area5,slide_phi5,slide_c5,slide_ar5,slide_pa5,slide_pp5,slide_req5,slide_load_case5,kh5,kv5,seismic_weight5,slide_footing5,auto_earth5,slide_gamma5,slide_backfill_phi5,slide_backfill_c5))
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"基底滑動計算失敗：{exc}")
            slide_sig=(src5,slide_v5,slide_u5,slide_h5,slide_area5,slide_phi5,slide_c5,slide_ar5,slide_pa5,slide_pp5,slide_req5,slide_load_case5,kh5,kv5,seismic_weight5,slide_footing5,auto_earth5,slide_gamma5,slide_backfill_phi5,slide_backfill_c5)
            slide, slide_is_current = read_result_state(st.session_state, "m5x_slide_result", "m5x_slide_signature", slide_sig)
            if slide and slide_is_current:
                st.metric("FS 滑動", "∞" if math.isinf(slide["FS_sliding"]) else f"{slide['FS_sliding']:.2f}",
                    delta=("符合輸入門檻" if slide["passes"] else "低於輸入門檻"))
                if slide_load_case5=="seismic" and slide.get("cases"):
                    slide_cases_df=pd.DataFrame(slide["cases"])
                    if slide_is_line5:
                        slide_cases_df=slide_cases_df.rename(columns={
                            "resisting_force_kN":"resisting_force_kN_per_m",
                            "driving_force_kN":"driving_force_kN_per_m",
                            "passive_resistance_used_kN":"passive_resistance_used_kN_per_m",
                            "horizontal_load_kN":"horizontal_load_kN_per_m",
                            "vertical_load_kN":"vertical_load_kN_per_m",
                        })
                    st.dataframe(slide_cases_df,hide_index=True,use_container_width=True)
                if slide.get("passive_balance_controls"):
                    st.warning("被動土壓力已完全抵銷外部驅動力；顯示 FS = ∞ 僅代表本式淨驅動力為零，不應與一般有限 FS 數值直接比較。")
                st.caption("依 USACE EM 1110-1-1905（2025）式 5-28 至 5-30：基底界面抗力使用界面 δ′、c_a/c′（或 c_a/s_u）；牆前／牆後主動與被動土壓力則另以 developed φ_d、c_d 計算。兩者分屬不同剪力區，並非混用安全係數。")
                st.caption(slide["limitations"])
                earth_result=st.session_state.get("m5x_slide_earth_result")
                if earth_result:
                    st.write(f"developed φd={earth_result['developed_phi_deg']:.2f}°；Ka,d={earth_result['Ka_developed']:.3f}；Kp,d={earth_result['Kp_developed']:.3f}；Pa,d={earth_result['active_force_kN']:.1f} {slide_force_unit5}；Pp,d={earth_result['passive_force_kN']:.1f} {slide_force_unit5}")
                    st.caption(earth_result["limitations"])

            if slide_load_case5=="seismic" and slide_u5<=0:
                st.info("U=0：未輸入基底揚壓力，抗浮 FS 不計算；請先確認靜水壓及地震殘餘超額孔壓是否確實為零。")
            elif slide_load_case5=="seismic" and not slide_uplift_ready5:
                st.warning("地震抗浮檢核尚未就緒：請輸入 Wf+Ws+Wc，確認重量定義及 U（含靜水壓與殘餘超額孔壓），並確認 kN／kN/m 單位一致。")
            if st.button("計算地震基礎抗浮安全係數（USACE FS ≥ 1.5）",key="m5x_uplift_run",disabled=not slide_uplift_ready5):
                try:
                    uplift=seismic_uplift_stability_cases(
                        resisting_weight_kN=slide_uplift_resisting_weight5,
                        structure_seismic_weight_kN=seismic_weight5,
                        uplift_force_kN=slide_u5,kv=kv5,fs_required=1.5)
                    uplift_sig=(slide_load_case5,slide_uplift_resisting_weight5,seismic_weight5,slide_u5,kv5,
                        slide_uplift_weights_confirmed5,slide_uplift_pressure_confirmed5,
                        slide_footing5,seismic_footing5,slide_area5,uplift_base_area5,df5,dw5,B5,L5,
                        base_uplift_pressure_kpa5,residual_base_excess_pore_pressure_kpa5,base_residual_pressure_confirmed5)
                    store_result_state(st.session_state,"m5x_uplift_result","m5x_uplift_signature",uplift,uplift_sig)
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"地震抗浮計算失敗：{exc}")
            uplift_sig=(slide_load_case5,slide_uplift_resisting_weight5,seismic_weight5,slide_u5,kv5,
                slide_uplift_weights_confirmed5,slide_uplift_pressure_confirmed5,
                slide_footing5,seismic_footing5,slide_area5,uplift_base_area5,df5,dw5,B5,L5,
                base_uplift_pressure_kpa5,residual_base_excess_pore_pressure_kpa5,base_residual_pressure_confirmed5)
            uplift,uplift_is_current=read_result_state(st.session_state,"m5x_uplift_result","m5x_uplift_signature",uplift_sig)
            if uplift and uplift_is_current and uplift.get("applicable"):
                st.metric("控制地震抗浮安全係數 FS_uplift",f"{uplift['FS_uplift']:.2f}",
                    delta=("符合最低 1.5" if uplift["passes"] else "低於最低 1.5"))
                st.dataframe(pd.DataFrame(uplift["cases"]),hide_index=True,use_container_width=True)
                st.caption(uplift["limitations"])

        with st.expander("⑥ 整體穩定：Bishop 簡化法（使用者提供圓弧切片）",expanded=False):
            st.warning("本 Bishop 計算目前僅為靜態圓弧滑動分析，不含 kh／kv 偽靜力、地震孔壓累積、液化後殘餘強度或側向擴展；不可將此 FS 當作地震整體穩定結果。USACE EM 1110-1-1905（2025）§1-7(f) 未提供靜態／地震邊坡穩定方法，應另依 EM 1110-2-1902 及場址地震設計要求分析。")
            st.caption("輸入同一圓弧滑動面的切片資料。底角正值代表朝滑動方向下降；各片 c′、φ′及孔隙水壓應使用該片底面平均值。")
            bishop_csv=st.text_area("切片 CSV：width_m,weight_kN,base_angle_deg,cohesion_kpa,friction_angle_deg,pore_pressure_kpa",
                value="",placeholder="width_m,weight_kN,base_angle_deg,cohesion_kpa,friction_angle_deg,pore_pressure_kpa\n1,100,10,10,25,0\n…請填入本工程同一圓弧滑動面的各片資料",
                height=120,key="m5x_bishop_csv")
            bishop_slice_context5=hashlib.sha256(bishop_csv.encode("utf-8")).hexdigest()[:12]
            bishop_slices_confirmed5=st.checkbox(
                "已確認各切片寬度、重量、底角、c′、φ′及孔壓均取自本工程同一圓弧滑動面",
                value=False,key=f"m5x_bishop_slices_confirm_{bishop_slice_context5}")
            bishop_slice_sig=(bishop_csv,bool(bishop_slices_confirmed5))
            if st.button("計算 Bishop 整體穩定 FS",key="m5x_bishop_run",disabled=(not bishop_csv.strip() or not bishop_slices_confirmed5)):
                try:
                    slices=pd.read_csv(StringIO(bishop_csv)).to_dict("records")
                    bishop=bishop_simplified_factor_of_safety(slices=slices)
                    store_result_state(st.session_state, "m5x_bishop_result", "m5x_bishop_signature", bishop, bishop_slice_sig)
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"Bishop 整體穩定計算失敗：{exc}")
            bishop, bishop_is_current = read_result_state(st.session_state, "m5x_bishop_result", "m5x_bishop_signature", bishop_slice_sig)
            if bishop and bishop_is_current:
                st.metric("Bishop 簡化法 FS",f"{bishop['FS']:.3f}")
                st.caption(f"迭代 {bishop['iterations']} 次；{bishop['limitations']}")
    
    
        with st.expander("⑥B 整體穩定：Bishop 圓弧滑動面自動搜尋（均質土）",expanded=False):
            st.warning("本自動搜尋同樣僅計算靜態 Bishop FS，不含 kh／kv、地震孔壓累積、液化後殘餘強度或側向擴展；不可用來宣稱地震整體穩定通過。地震邊坡穩定須另依 EM 1110-2-1902 與適用的場址地震設計程序辦理。")
            st.caption("以地表折線、均質土強度及圓心／半徑網格搜尋候選圓弧，回報最低 Bishop FS。座標 y 為高程（向上為正）；本功能不是分層或非圓弧分析。")
            profile_csv5=st.text_area("地表剖面 CSV：x_m,elevation_m（由左至右）",
                value="",placeholder="x_m,elevation_m\n0,10\n5,8\n10,0\n20,0\n…請改填本工程實際地表剖面",
                height=90,key="m5x_profile")
            ba,bb,bc=st.columns(3)
            with ba:
                bishop_c5=st.number_input("均質土坡體 c′ [kPa]",0.0,10000.0,0.0,1.0,key="m5x_auto_c_slope")
                bishop_phi5=st.number_input("均質土坡體 φ′ [°]",0.0,50.0,0.0,1.0,key="m5x_auto_phi_slope")
                st.caption("此自動搜尋是均質土坡穩定分析，須輸入坡體專屬 c′、φ′；不會自動沿用 Module 1／Module 5 的基礎承載力參數。")
            with bb:
                bishop_gamma5=st.number_input("均質土總單位重 γ [kN/m³]",10.0,30.0,18.0,0.5,key="m5x_auto_gamma")
                bishop_has_gw5=st.checkbox("納入地下水位",value=False,key="m5x_auto_has_gw")
                bishop_gw5=(st.number_input("地下水位高程 [m]",-1000.0,1000.0,0.0,0.5,key="m5x_auto_gw")
                            if bishop_has_gw5 else None)
            with bc:
                center_x_min5=st.number_input("圓心 x 最小值 [m]",-100.0,1000.0,3.0,0.5,key="m5x_cxmin")
                center_x_max5=st.number_input("圓心 x 最大值 [m]",-100.0,1000.0,7.0,0.5,key="m5x_cxmax")
                center_y_min5=st.number_input("圓心高程最小值 [m]",-100.0,1000.0,8.0,0.5,key="m5x_cymin")
                center_y_max5=st.number_input("圓心高程最大值 [m]",-100.0,1000.0,14.0,0.5,key="m5x_cymax")
            radii_csv5=st.text_input("搜尋半徑 [m]（逗號分隔）","8,10,12,15",key="m5x_radii")
            slices_auto5=st.number_input("每一滑動面切片數",5,100,20,1,key="m5x_auto_slices")
            bishop_auto_context5=(
                profile_csv5,bishop_c5,bishop_phi5,bishop_gamma5,bishop_has_gw5,bishop_gw5,
                center_x_min5,center_x_max5,center_y_min5,center_y_max5,radii_csv5,slices_auto5
            )
            bishop_auto_context_id5=hashlib.sha256(repr(bishop_auto_context5).encode("utf-8")).hexdigest()[:12]
            bishop_auto_confirmed5=st.checkbox(
                "已確認地表剖面、坡體 c′／φ′、單位重、地下水位及圓弧搜尋範圍均為本工程資料",
                value=False,key=f"m5x_auto_bishop_confirm_{bishop_auto_context_id5}")
            auto_sig=(src5,bishop_auto_context5,bool(bishop_auto_confirmed5))
            if st.button("搜尋最低 Bishop FS",key="m5x_auto_bishop_run",
                    disabled=(not profile_csv5.strip() or not bishop_auto_confirmed5 or (bishop_c5<=0 and bishop_phi5<=0))):
                try:
                    pprof=pd.read_csv(StringIO(profile_csv5))
                    if not {"x_m","elevation_m"}.issubset(pprof.columns):
                        raise ValueError("地表剖面 CSV 必須包含 x_m、elevation_m")
                    radii=[float(x.strip()) for x in radii_csv5.split(",") if x.strip()]
                    search=bishop_circular_search(ground_profile=pprof[["x_m","elevation_m"]].values.tolist(),
                        cohesion_kpa=bishop_c5,friction_angle_deg=bishop_phi5,
                        unit_weight_kn_m3=bishop_gamma5,
                        center_x_values=[center_x_min5+(center_x_max5-center_x_min5)*i/8 for i in range(9)],
                        center_y_values=[center_y_min5+(center_y_max5-center_y_min5)*i/8 for i in range(9)],
                        radius_values=radii,slice_count=slices_auto5,
                        groundwater_elevation=bishop_gw5)
                    store_result_state(st.session_state, "m5x_auto_bishop_result", "m5x_auto_bishop_signature", search, auto_sig)
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"圓弧搜尋失敗：{exc}")
            auto_bishop, auto_bishop_is_current = read_result_state(st.session_state, "m5x_auto_bishop_result", "m5x_auto_bishop_signature", auto_sig)
            if auto_bishop and auto_bishop_is_current:
                st.metric("搜尋到的最低 Bishop FS",f"{auto_bishop['FS']:.3f}")
                st.write(f"圓心=({auto_bishop['center_x_m']:.2f}, {auto_bishop['center_elevation_m']:.2f}) m；半徑={auto_bishop['radius_m']:.2f} m；搜尋有效滑動面 {auto_bishop['evaluated_surfaces']} 組。")
                if auto_bishop.get("search_boundary_warning"):
                    st.warning(auto_bishop["search_boundary_warning"])
                st.caption(auto_bishop["limitations"])
    
    

        with st.expander("⑦ 原位試驗承載力（USACE 2025）",expanded=False):
            st.caption("依 USACE 2025 Eqs. 5-25／5-26、Table 5-5，以剪力區內原位試驗值幾何平均估算承載力。SPT 請輸入模組二校正後的 N60（不是 N1,60）；CPT 輸入淨錐尖阻力 qne；PMT 輸入淨極限壓力 pne。CPT／PMT 單位為 kPa。")
            ia,ib,ic=st.columns(3)
            with ia:
                insitu_type5=st.selectbox("原位試驗類型",["SPT","CPT","PMT"],format_func=lambda x:{"SPT":"SPT（N60）","CPT":"CPT（qne）","PMT":"PMT（pne）"}[x],key="m5x_insitu_type")
                insitu_drainage5=st.selectbox("排水條件",["drained","undrained"],format_func=lambda x:"排水（有效應力）" if x=="drained" else "不排水（總應力）",key="m5x_insitu_drainage")
            with ib:
                insitu_footing5=st.selectbox("基礎型式",["isolated","continuous"],format_func=lambda x:"獨立／矩形" if x=="isolated" else "連續條形",key="m5x_insitu_footing")
                insitu_values5=st.text_input("剪力區試驗值（逗號分隔）",value="",placeholder="例如：12, 12, 15, 14",key="m5x_insitu_values")
            with ic:
                st.metric("目前基礎 B × L",f"{B5:.2f} × {L5:.2f} m")
                st.metric("目前埋深 Df",f"{df5:.2f} m")
                st.caption(f"Dw={dw5:.2f} m；γ={gamma5:.2f} kN/m³；γ′={gsub5:.2f} kN/m³")
            unsupported_insitu5=(H5>0 or beta5>0 or eB5>0 or eL5>0 or base_ang5>0 or ground_ang5>0)
            if unsupported_insitu5:
                st.warning("目前輸入含水平載重、載重傾角或偏心；原位試驗承載力此版僅支援垂直置中載重，已停用計算按鈕，避免忽略修正係數。斜坡地表／傾斜基底也尚未納入此路徑。")
            if st.button("計算原位試驗承載力",key="m5x_insitu_run",disabled=unsupported_insitu5):
                try:
                    raw=[x.strip() for x in insitu_values5.replace("；",",").replace(";",",").replace("，",",").split(",") if x.strip()]
                    values=[float(x) for x in raw]
                    insitu=bearing_capacity_in_situ(
                        test_type=insitu_type5,measurements=values,drainage=insitu_drainage5,
                        B=B5,L=L5,Df=df5,gamma_moist=gamma5,gamma_sub=gsub5,
                        water_depth=dw5,fs=fs5,footing_type=insitu_footing5)
                    sig=(insitu_type5,insitu_drainage5,insitu_footing5,insitu_values5,
                         B5,L5,df5,gamma5,gsub5,dw5,fs5,H5,beta5,eB5,eL5,base_ang5,ground_ang5,slope_dist5,slope_fs5)
                    store_result_state(st.session_state,"m5x_insitu_result","m5x_insitu_signature",insitu,sig)
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"原位試驗承載力計算失敗：{exc}")
            insitu_sig=(insitu_type5,insitu_drainage5,insitu_footing5,insitu_values5,
                        B5,L5,df5,gamma5,gsub5,dw5,fs5,H5,beta5,eB5,eL5,base_ang5,ground_ang5,slope_dist5,slope_fs5)
            insitu_result,insitu_current=read_result_state(
                st.session_state,"m5x_insitu_result","m5x_insitu_signature",insitu_sig)
            if insitu_result and insitu_current:
                mean_unit5="blows/ft" if insitu_type5=="SPT" else "kPa"

                _render_bearing_safety_check(
                    qult_kpa=insitu_result["qu_gross"],vertical_load_kN=V5,
                    width_m=B5,length_m=L5,depth_m=df5,water_depth_m=dw5,
                    footing_type=insitu_footing5,complete_capacity_model=True,load_confirmed=loads_confirmed5)
                st.write(f"剪力區幾何平均 = {insitu_result['geometric_mean']:.3f} {mean_unit5}；等效強度參數 s = {insitu_result['s_parameter_kpa']:.1f} kPa；k = {insitu_result['k']:.2f}")
                r1,r2,r3=st.columns(3)
                r1.metric("極限承載力 qult,gross",f"{insitu_result['qu_gross']:.1f} kPa")
                r2.metric("qult / FS 參考值",f"{insitu_result['qa_gross_direct_FS']:.1f} kPa")
                r3.metric("qu,net / FS 參考值",f"{insitu_result['qa_net_direct_FS']:.1f} kPa")
                st.caption(f"形狀係數={insitu_result['shape_factor']:.3f}；深度係數={insitu_result['depth_factor']:.3f}；基礎底覆土壓力 q0={insitu_result['q_surcharge_kpa']:.1f} kPa。")
                st.caption("上列 qult/FS 是參考換算，不代表已完成實際設計檢核；上方 qeq 與 FS 才是依實際總垂直力及基底水壓計算的檢核值。")
                st.caption(insitu_result["limitations"])



        with st.expander("⑧ 原位試驗分層承載力與弱層穿刺整合",expanded=False):
            st.caption("依 USACE 2025 式 5-25／5-26、表 5-5 分別計算各層原位試驗承載力，再依式 5-17／5-18 檢查強上層覆蓋弱下層的 2V:1H 穿刺。每列厚度是自基礎底面向下的該層厚度；各層可使用不同試驗種類與排水條件。")
            st.caption("CSV 欄位：thickness_m,test_type,drainage,measurements。SPT 輸入 N60（blows/ft）；CPT 輸入 qne（kPa）；PMT 輸入 pne（kPa）。measurements 欄以分號分隔多筆試驗值。drainage 使用 drained 或 undrained。")
            insitu_layer_footing5=st.selectbox("分層基礎型式",["isolated","continuous"],format_func=lambda x:"獨立／矩形基礎" if x=="isolated" else "連續條形基礎",key="m5x_insitu_layer_footing")
            insitu_layer_csv5=st.text_area(
                "各層原位試驗資料（CSV）",
                value="thickness_m,test_type,drainage,measurements\n1.5,SPT,drained,20;22;18\n2.0,SPT,undrained,4;5;4",
                height=125,key="m5x_insitu_layer_csv")
            insitu_layer_unsupported5=(H5>0 or beta5>0 or eB5>0 or eL5>0 or base_ang5>0 or ground_ang5>0)
            if insitu_layer_unsupported5:
                st.warning("此原位試驗分層穿刺路徑目前僅支援置中垂直載重、水平基底及水平地表；請先將水平力、偏心、傾斜基底及坡角設為 0，否則不會執行。")
            if st.button("計算原位試驗分層穿刺",key="m5x_insitu_layer_run",disabled=insitu_layer_unsupported5):
                try:
                    frame=pd.read_csv(StringIO(insitu_layer_csv5))
                    required_cols={"thickness_m","test_type","drainage","measurements"}
                    if not required_cols.issubset(frame.columns):
                        raise ValueError("CSV 必須包含 thickness_m、test_type、drainage、measurements 四欄")
                    layer_rows=[]
                    for row in frame.to_dict("records"):
                        raw=str(row["measurements"]).replace("；",";").replace("，",";").replace("|",";")
                        values=[float(x.strip()) for x in raw.split(";") if x.strip()]
                        layer_rows.append({
                            "thickness_m":float(row["thickness_m"]),
                            "test_type":str(row["test_type"]).strip().upper(),
                            "drainage":str(row["drainage"]).strip().lower(),
                            "measurements":values,
                        })
                    layered_insitu=layered_bearing_capacity_in_situ_profile(
                        layers=layer_rows,footing_width_m=B5,footing_length_m=L5,
                        footing_depth_m=df5,water_depth_m=dw5,
                        gamma_moist_kn_m3=gamma5,gamma_sub_kn_m3=gsub5,
                        footing_type=insitu_layer_footing5,fs=fs5)
                    insitu_layer_sig=(insitu_layer_csv5,insitu_layer_footing5,B5,L5,df5,dw5,
                        gamma5,gsub5,fs5,V5,H5,beta5,eB5,eL5,base_ang5,ground_ang5)
                    store_result_state(st.session_state,"m5x_insitu_layer_result",
                        "m5x_insitu_layer_signature",layered_insitu,insitu_layer_sig)
                except Exception as exc:
                    logging.exception("Unhandled application calculation error")
                    st.error(f"原位試驗分層穿刺計算失敗：{exc}")
            insitu_layer_sig=(insitu_layer_csv5,insitu_layer_footing5,B5,L5,df5,dw5,
                gamma5,gsub5,fs5,V5,H5,beta5,eB5,eL5,base_ang5,ground_ang5)
            layered_insitu,insitu_layer_current=read_result_state(
                st.session_state,"m5x_insitu_layer_result","m5x_insitu_layer_signature",insitu_layer_sig)
            if layered_insitu and insitu_layer_current:
                _render_bearing_safety_check(
                    qult_kpa=layered_insitu["qult_kpa"],vertical_load_kN=V5,
                    width_m=B5,length_m=L5,depth_m=df5,water_depth_m=dw5,
                    footing_type=insitu_layer_footing5,complete_capacity_model=not insitu_layer_unsupported5,
                    incomplete_reason="原位試驗分層穿刺尚未包含目前輸入的水平力、偏心或斜坡／傾斜基底修正。",
                    load_confirmed=loads_confirmed5)
                st.write(f"控制模式：{layered_insitu['controlling_mode']}；控制層：第 {layered_insitu['controlling_layer']} 層")
                punch_candidates=[x for x in layered_insitu["candidates"] if x.get("spread_factor",1.0)>1.0]
                if punch_candidates:
                    st.write("穿刺擴散係數："+ "；".join(f"第 {x['controlling_layer']} 層：{x['spread_factor']:.3f}" for x in punch_candidates))
                layer_view=pd.DataFrame(layered_insitu["layers"]).rename(columns={
                    "layer":"層次","thickness_m":"層厚 (m)","top_depth_m":"層頂深度 (m)",
                    "test_type":"試驗類型","drainage":"排水條件","measurement_count":"試驗點數",
                    "geometric_mean":"幾何平均","s_parameter_kpa":"等效參數 s (kPa)",
                    "k":"k","qult_kpa":"該層極限承載力 (kPa)"})
                st.dataframe(layer_view,hide_index=True,use_container_width=True)
                if layered_insitu.get("warning"):
                    st.warning(layered_insitu["warning"])
                st.caption(layered_insitu["limitations"])
            elif layered_insitu:
                st.warning("輸入已變更，請重新執行原位試驗分層穿刺計算。")

        with st.expander("擴充分析公式依據與適用限制",expanded=False):
            st.markdown("""
    - **斜坡地表／傾斜基底**：USACE [EM 1110-1-1905（2025）](https://publibrary.sec.usace.army.mil/api/download?filename=EM+1110-1-1905_Geotechincal+Design+of+Shallow+Foundations+on+Soils_2025+07+22+-+Final.pdf&id=54658636-77d2-48df-f26b-5295a01899a7&preview=true)，Table 5-3、5-4、Eqs. 5-21／5-22。
    - **多層穿刺承載力**：同手冊 Eqs. 5-17／5-18、Figure 5-6；採 2V:1H 應力擴散。
    - **地震承載力**：同手冊 Chapter 9 §9-10、Eqs. 9-3／9-4（Day, 2012）；另參考 [Fishman, Richards & Yao (2003), Inclination Factors for Seismic Bearing Capacity](https://doi.org/10.1061/(ASCE)1090-0241(2003)129:9(861))。
    - **基底滑動**：USACE 2025 Eqs. 5-28／5-30、§5-6；可使用 Eqs. 5-31 至 5-35 依 developed strength 估算 Rankine 主動／被動土壓，或手動輸入已折減土壓。
    - **整體穩定**：USACE [EM 1110-2-1902, Slope Stability](https://www.publications.usace.army.mil/Portals/76/Publications/EngineerManuals/EM_1110-2-1902.pdf)；本頁採 Bishop simplified，另提供圓弧搜尋。Bishop 以外仍應以 Spencer／Morgenstern–Price 交叉檢核。
            """)
