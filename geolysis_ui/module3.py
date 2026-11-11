"""Streamlit UI for engineering module 3."""
import streamlit as st
import logging
import pandas as pd
import plotly.graph_objects as go
from io import StringIO
from geolysis_engine import spt_correct, spt_profile


def render_module_3(expanded=False):
    # ==============================================================================
    # 模組三：SPT 標準貫入試驗全修正
    # ==============================================================================
    with st.expander("🔨 模組三：SPT 標準貫入試驗全修正", expanded):
        st.subheader("🔨 SPT 標準貫入試驗全修正")
        st.caption("N60 = N × CE × CB × CS × CR；(N1)60 = CN × N60。N 值須為標準貫入試驗最後 300 mm 的擊數，拒錘／未貫入須另註記，不可當作一般 N 值。")
        a,b,c=st.columns(3)
        with a:
            n_measured=st.number_input("現場量測 N 值",0,200,18,1,key="m3_n")
            er=st.number_input("錘擊能量比 ETR／ER [%]（依 ASTM D4633 實測或設備紀錄）",20.0,150.0,60.0,1.0,key="m3_er")
            st.caption("尚無能量校正報告時，60% 僅作標準化暫定假設；請取得設備實測 ETR 後更新，不可視為現場實測值。")
            cb_label=st.selectbox("鑽孔直徑（CB）",["65–115 mm（1.00）","150 mm（1.05）","200 mm（1.15）"],index=0,key="m3_cb_label")
            cb={"65–115 mm（1.00）":1.00,"150 mm（1.05）":1.05,"200 mm（1.15）":1.15}[cb_label]
        with b:
            cs_label=st.selectbox("取樣器內襯修正 CS",["有內襯（1.00）","無內襯／一般（1.10）","無內襯／較高修正（1.20）","無內襯／最高修正（1.30）"],index=0,key="m3_cs_label")
            cs={"有內襯（1.00）":1.00,"無內襯／一般（1.10）":1.10,"無內襯／較高修正（1.20）":1.20,"無內襯／最高修正（1.30）":1.30}[cs_label]
            rod_len=st.number_input("鑽桿長度 [m]",0.5,60.0,8.0,0.5,key="m3_rod")
            st.caption("CR 依鑽桿長度自動採建議值；仍須依設備型式與採用規範核對。")
            if rod_len>30:
                st.warning("鑽桿長度超過 30 m；USACE EM 1110-1-1905（2025）表 4-6 的 CR 參考範圍為 10–30 m。本工具目前仍以 CR=1.00 延用計算，但此範圍屬表列範圍外推，請依實際設備與採用規範確認。")
        with c:
            sigma_v=st.number_input("有效覆土應力 σ'v [kPa]",1.0,2000.0,95.0,5.0,key="m3_sv")
            soil_behavior=st.selectbox("土層性質",["砂土／非凝聚性土壤","黏土／凝聚性土壤"],key="m3_soil_behavior")
            soil_behavior_code="cohesionless" if soil_behavior.startswith("砂土") else "cohesive"
            cn_method=st.selectbox("覆土壓力修正 CN",["Liao & Whitman","Seed & Idriss","Skempton","不修正"],key="m3_cnmethod",disabled=(soil_behavior_code=="cohesive"))
            cn_cap=st.number_input("CN 上限（USACE 2025：最高 2.0；Seed–Idriss 液化法自動不超過 1.7）",1.0,2.0,2.0,0.1,key="m3_cncap")
            st.caption("Liao & Whitman 與 Seed & Idriss 的 CN 基本式均為 √(Pa/σ′v)；兩者在本工具的差別是 Seed & Idriss 液化評估慣例另將 CN 上限限制為 1.7。選擇方法時請依分析目的與採用文獻，不代表兩者是不同的基本公式。")
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
            except Exception as exc:
                logging.exception("Unhandled application calculation error")
                st.error(f"SPT 修正失敗：{exc}")
        st.markdown("**鑽孔逐深度資料（CSV）**")
        st.caption("必要欄位：Depth_m、N、Effective_Stress_kPa；可選填 Rod_Length_m（該深度實際鑽桿長度）、Refusal（true/false）及 Penetration_mm。若提供 Rod_Length_m，逐列依實際鑽桿長度計算 CR；未提供才使用上方共用值。拒錘列會保留但不計算一般 N60。")
        csv_file=st.file_uploader("上傳逐深度 SPT CSV（UTF-8）",type=['csv'],key='m3_csv_upload')
        default_csv="Depth_m,N,Effective_Stress_kPa,Rod_Length_m\n5,12,50,6\n10,18,95,11\n15,25,140,16"
        csv_text=st.text_area("或貼上 CSV 內容",default_csv,height=100,key="m3_profile")
        # Clear any previous profile before validating current inputs to prevent stale Module 4 linkage.
        st.session_state.pop("m3_profile_result",None)
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
        except Exception as exc:
            logging.exception("Unhandled application calculation error")
            st.error(f"逐深度資料檢核失敗：{exc}")
        st.caption("依 USACE EM 1110-1-1905（2025）：CN 僅建議用於非凝聚性土壤；黏土不作覆土修正，黏土類 CB 採 1.0。一般淺基礎設計可採 CN≤2.0；液化評估常見文獻上限 1.7，應依分析目的選擇。")
        st.info("飽和細砂／粉土的膨脹修正必須在覆土修正後進行，僅適用於地下水位以下且 (N1)60 > 15；粗砂不適用。")
        with st.expander("SPT 修正依據與文獻",expanded=False):
            st.markdown("- [USACE EM 1110-1-1905（2025）：Geotechnical Design of Shallow Foundations on Soils](https://publibrary.sec.usace.army.mil/api/download?filename=EM+1110-1-1905_Geotechincal+Design+of+Shallow+Foundations+on+Soils_2025+07+22+-+Final.pdf&id=54658636-77d2-48df-f26b-5295a01899a7&preview=true)\n- [ASTM D1586：Standard Penetration Test (SPT)](https://www.astm.org/d1586_d1586m.html)\n- [Youd et al. (2001)：NCEER SPT 液化評估修正建議](https://doi.org/10.1061/(ASCE)1090-0241(2001)127:10(817))")
