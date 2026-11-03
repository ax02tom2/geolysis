import streamlit as st
try:
    from geolysis.bearing_capacity import TerzaghiBearingCapacity
    from geolysis.spt import spt_n_60
except ImportError:
    pass 

st.set_page_config(page_title="承載力推估", page_icon="🧱")
st.title("🧱 大地參數與承載力推估工具")
st.markdown("這是一支獨立的程式，專門處理 `geolysis` 相關的大地工程公式運算。")

col1, col2 = st.columns(2)
with col1:
    st.subheader("SPT-N 值修正")
    n_val = st.number_input("輸入現場 SPT-N 值", min_value=1, value=15, step=1)
    energy_ratio = st.number_input("輸入打擊能量比 (%)", min_value=1, max_value=100, value=60)
    
    if st.button("計算修正後 N60"):
        try:
            n60 = spt_n_60(n_val, energy_ratio)
            st.success(f"修正後 N60 = {n60}")
        except Exception as e:
            st.error(f"運算錯誤: {e}")

with col2:
    st.subheader("Terzaghi 極限承載力估算")
    depth = st.number_input("輸入基礎深度 Df (m)", min_value=0.0, value=1.5, step=0.1)
    width = st.number_input("輸入基礎寬度 B (m)", min_value=0.1, value=2.0, step=0.1)
    
    if st.button("計算極限承載力 (q_ult)"):
        try:
            tbc = TerzaghiBearingCapacity(cohesion=0, friction_angle=30, unit_weight=18)
            q_ult = tbc.ultimate_bearing_capacity(depth=depth, width=width)
            st.info(f"極限承載力估算 (q_ult) = {q_ult:.2f} kPa")
        except Exception as e:
            st.error(f"運算錯誤: {e}")
