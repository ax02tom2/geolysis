import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="進階承載力推估", page_icon="🧱", layout="wide")

# ==========================================
# 抓漏專用：顯示真正的載入錯誤
# ==========================================
try:
    from geolysis.bearing_capacity import TerzaghiBearingCapacity
    from geolysis.spt import spt_n_60
    GEOLYSIS_READY = True
except Exception as e:
    GEOLYSIS_READY = False
    st.error("🚨 抓到真正的錯誤了！套件已經安裝，但載入失敗，原因是：")
    st.code(str(e))
    st.info("💡 請把上面紅框內的這段錯誤訊息複製給 Gemini，我們馬上就能對症下藥！")
    st.stop()

# ==========================================
# 下方為原本的主程式 (只有成功載入才會執行)
# ==========================================
st.title("🧱 進階大地參數與承載力分析系統")
st.markdown("支援連續地層 SPT-N 值批次修正、深度剖面視覺化，以及基礎承載力試算。")

st.header("1. 鑽孔數據輸入與 N 值修正")
default_data = pd.DataFrame({
    "深度_m": [1.5, 3.0, 4.5, 6.0, 7.5, 9.0],
    "現場_N值": [8, 12, 15, 7, 25, 30],
    "打擊能量比_%": [60, 60, 60, 60, 60, 60]
})

edited_df = st.data_editor(
    default_data, 
    num_rows="dynamic",
    use_container_width=True,
    key="borehole_editor"
)

if st.button("🚀 執行全深度 N60 修正與繪圖", type="primary"):
    try:
        edited_df['修正後_N60'] = edited_df.apply(
            lambda row: spt_n_60(row['現場_N值'], row['打擊能量比_%']), axis=1
        )
        col_table, col_chart = st.columns([1, 1])
        with col_table:
            st.subheader("📊 運算結果表")
            st.dataframe(edited_df, use_container_width=True)
        with col_chart:
            st.subheader("📉 深度 vs. N60 剖面圖")
            fig = px.line(edited_df, x="修正後_N60", y="深度_m", markers=True, title="SPT-N60 地層剖面")
            fig.update_layout(yaxis=dict(autorange="reversed")) 
            fig.update_traces(line_color='#d62728', marker=dict(size=8))
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"運算發生錯誤：{e}")

st.divider()

st.header("2. 基礎承載力估算 (Terzaghi)")
col_geo, col_found = st.columns(2)
with col_geo:
    cohesion = st.number_input("凝聚力 (c) [kPa]", value=0.0, step=5.0)
    friction_angle = st.number_input("內摩擦角 (ϕ) [度]", value=30.0, step=1.0)
    unit_weight = st.number_input("土壤單位重 (γ) [kN/m³]", value=18.0, step=0.5)

with col_found:
    depth = st.number_input("基礎埋置深度 (Df) [m]", value=1.5, step=0.1)
    width = st.number_input("基礎寬度 (B) [m]", value=2.0, step=0.1)

if st.button("⚖️ 計算極限承載力 (q_ult)"):
    try:
        tbc = TerzaghiBearingCapacity(cohesion=cohesion, friction_angle=friction_angle, unit_weight=unit_weight)
        q_ult = tbc.ultimate_bearing_capacity(depth=depth, width=width)
        st.success("計算完成！")
        st.metric(label="極限承載力 (q_ult)", value=f"{q_ult:.2f} kPa")
    except Exception as e:
        st.error(f"計算錯誤：{e}")
