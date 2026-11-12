"""Streamlit UI for engineering module 2."""
import streamlit as st
import logging
from .state import clear_result_state, read_result_state, store_result_state
import pandas as pd
from geolysis_engine import classify_uscs_aashto


def render_module_2(expanded=False):
    # ==============================================================================
    # 模組二：土壤分類系統
    # ==============================================================================
    with st.expander("🌱 模組二：土壤分類系統 (USCS & AASHTO)", expanded):
        st.subheader("🌱 土壤分類系統")
        st.caption("依 ASTM D2487 與 AASHTO M 145 判別邏輯進行工程初判。篩分析通過率必須符合 P4 ≥ P10 ≥ P40 ≥ P200；分類百分比以通過 3 in（75 mm）篩的土樣為基準。LL／PL 應採通過 #40（0.425 mm）篩的細料試驗值；若含卵石／漂石須另加描述。")
        peat=st.checkbox("泥炭／高度有機土（依現場外觀、纖維質與有機特徵辨識）",key="m2_peat")
        if peat:
            st.info("泥炭依現場辨識分類為 USCS PT、AASHTO A-8；此分類不需要篩分析、LL 或 PL。下列試驗欄位暫停使用。")
        a,b,c=st.columns(3)
        with a:
            p4=st.number_input("#4 篩通過率 P4 [%]",0.0,100.0,85.0,1.0,key="m2_p4",disabled=peat)
            p10=st.number_input("#10 篩通過率 P10 [%]",0.0,100.0,75.0,1.0,key="m2_p10",disabled=peat)
            p40=st.number_input("#40 篩通過率 P40 [%]",0.0,100.0,55.0,1.0,key="m2_p40",disabled=peat)
            p200=st.number_input("#200 篩通過率 P200 [%]",0.0,100.0,12.0,1.0,key="m2_p200",disabled=peat)
        with b:
            ll=st.number_input("液性限度 LL [%]",0.0,200.0,42.0,1.0,key="m2_ll",disabled=peat)
            np_flag=st.checkbox("NP（無塑性）",key="m2_np",disabled=peat)
            pl=None if np_flag or peat else st.number_input("塑性限度 PL [%]",0.0,200.0,22.0,1.0,key="m2_pl",disabled=peat)
            organic=st.checkbox("疑似有機土（需另行確認）",key="m2_org",disabled=peat)
            organic_test_done=st.checkbox("已完成烘乾前後 LL 比值試驗",value=False,disabled=(not organic or peat),key='m2_org_test_done')
            ll_od=st.number_input("烘乾後 LL [%]（有機土確認用）",0.0,200.0,25.0,1.0,key="m2_llod",disabled=(not organic or not organic_test_done or peat))
        with c:
            coarse_soil=(p200<50) and not peat
            use_grad=st.checkbox("輸入粒徑曲線 D10/D30/D60（僅粗粒土級配判定）",value=False,key="m2_use_grad",disabled=not coarse_soil)
            if use_grad and coarse_soil:
                d10=st.number_input("D10 [mm]",min_value=0.0,value=0.0,format="%.4f",key="m2_d10")
                d30=st.number_input("D30 [mm]",min_value=0.0,value=0.0,format="%.4f",key="m2_d30")
                d60=st.number_input("D60 [mm]",min_value=0.0,value=0.0,format="%.4f",key="m2_d60")
            else:
                d10=d30=d60=None
            if not peat and p200>=50:
                st.caption("目前 P200 ≥ 50%，屬細粒土；USCS 細粒土分類不使用 Cu／Cc，故不要求 D10/D30/D60。")
        m2_input_signature=(float(p4),float(p10),float(p40),float(p200),float(ll),
            None if pl is None else float(pl),bool(np_flag),
            None if d10 is None else float(d10),None if d30 is None else float(d30),
            None if d60 is None else float(d60),bool(organic),
            bool(organic_test_done),float(ll_od),bool(peat))
        data_confirm=st.checkbox("已確認上方為本次試驗數據（非預設示範值）",value=False,key="m2_data_confirm")
        if st.button("執行土壤分類",key="m2_run",disabled=not data_confirm):
            clear_result_state(st.session_state, 'm2_result', 'm2_result_signature')
            try:
                result=classify_uscs_aashto(p4=p4,p10=p10,p40=p40,p200=p200,ll=ll,pl=pl,np_flag=np_flag,
                    d10=d10,d30=d30,d60=d60,organic=organic,ll_oven_dried=(ll_od if organic and organic_test_done else None),peat=peat)
                store_result_state(st.session_state, 'm2_result', 'm2_result_signature', result, m2_input_signature)
            except Exception as exc:
                logging.exception("Unhandled application calculation error")
                st.error(f"資料檢核未通過：{exc}")
        if not data_confirm:
            clear_result_state(st.session_state, 'm2_result', 'm2_result_signature')
            result, result_is_current = None, False
        else:
            result, result_is_current = read_result_state(
                st.session_state, 'm2_result', 'm2_result_signature', m2_input_signature
            )
        if result and not result_is_current:
            st.warning("土壤分類輸入已變更；目前顯示的舊結果不再對應現有試驗值。請重新按「執行土壤分類」更新。")
            result=None
        if result:
            r1,r2,r3=st.columns(3)
            r1.success(f"USCS：{result['USCS']}")
            r2.success(f"AASHTO：{result['AASHTO']}")
            r3.metric("群指數 GI",result['GI'])
            st.caption(f"USCS 組別意義：{result['USCS_description']}")
            st.caption(f"AASHTO 組別意義：{result['AASHTO_description']}")
            if result['peat']:
                st.caption("泥炭／高度有機土：PI、Cu、Cc 與篩分析比例不適用。")
            else:
                st.write(f"PI = {result['PI']:.1f}% ｜ Cu = {result['Cu'] if result['Cu'] is not None else '未計算'} ｜ Cc = {result['Cc'] if result['Cc'] is not None else '未計算'}")
                st.dataframe(pd.DataFrame([{'礫粒(%)':result['gravel_pct'],'砂粒(%)':result['sand_pct'],'細料(%)':result['fines_pct'],'A-line PI':result['A_line_PI'],'U-line PI':result['U_line_PI']}]),hide_index=True,use_container_width=True)
            if result['plasticity_warning']: st.warning(result['plasticity_warning'])
            if result['organic_note']: st.warning(result['organic_note'])
            st.caption("USCS：ASTM D2487 A-line：LL≤25.5 時 PI=4，之後 PI=0.73(LL−20)；LL<50 時 PI<4 或位於 A 線下判 ML，PI>7 且位於 A 線上判 CL，4–7 的 A 線上區為 CL-ML。U-line 為 LL=16 垂直至 PI=7，之後 PI=0.9(LL−8)；位於 U-line 左側或上方會警示複驗。細料 >12% 且屬 CL-ML 時，粗粒土採 GC-GM／SC-SM；5–12% 細料仍依 ASTM 規則採雙重符號。未輸入 D10/D30/D60 時，不會虛構 GW/GP 或 SW/SP。AASHTO 限值依 M 145 將小數試驗值先四捨五入至整數；GI 依 AASHTO M 145 計算並四捨五入至整數，負值歸零（不強制封頂 20）；A-2-6／A-2-7 僅採 PI 部分。")
            st.warning("分類結果仍須由完整粒徑曲線、液塑限試驗及有機土試驗確認；本工具不取代 ASTM/AASHTO 正式試驗與工程師判釋。")
        with st.expander("分類依據與文獻",expanded=False):
            st.markdown("- [ASTM D2487：Unified Soil Classification System](https://www.astm.org/d2487.html)\n- [AASHTO M 145：Classification of Soils and Soil-Aggregate Mixtures](https://store.transportation.org/)")
