import streamlit as st
import pandas as pd
import plotly.express as px
import math

st.set_page_config(page_title="進階承載力推估", page_icon="🧱", layout="wide")

# ==========================================
# 核心演算法：純 Python 實作 (擺脫外部套件依賴)
# ==========================================
def calc_spt_n60(n, energy_ratio):
    """計算修正後 N60"""
    return n * (energy_ratio / 60.0)

def calc_bearing_capacity(c, phi_deg, gamma, df, b, method="Meyerhof"):
    """計算極限承載力 (包含承載力係數推導)"""
    if phi_deg == 0:
        Nc, Nq, Ng = 5.7, 1.0, 0.0
    else:
        phi_rad = math.radians(phi_deg)
        # Nq 基於 Reissner 理論
        Nq = math.exp(math.pi * math.tan(phi_rad)) * (math.tan(math.radians(45) + phi_rad / 2)) ** 2
        # Nc
        Nc = (Nq - 1) / math.tan(phi_rad)
        # Ngamma 依據不同學者有不同經驗式
        if method == "Meyerhof":
            Ng = (Nq - 1) * math.tan(1.4 * phi_rad)
        else: # Terzaghi / Vesic 通用近似
            Ng = 2 * (Nq + 1) * math.tan(phi_rad)
            
    # 連續基礎 (Strip Footing) 極限承載力公式
    q_ult = (c * Nc) + (gamma * df * Nq) + (0.5 * gamma * b * Ng)
    return q_ult, Nc, Nq, Ng

# ==========================================
# 介面設計與互動邏輯
# ==========================================
st.title("🧱 進階大地參數與承載力分析系統")
st.markdown("🛡️ **系統狀態**：已移除 `geolysis` 套件依賴，啟用原生 Python 工程運算核心。")

# --- 區塊 1：連續地層 SPT-N 值批次處理 ---
st.header("1. 鑽孔數據輸入與 N 值修正")
default_data = pd.DataFrame({
    "深度_m": [1.5, 3.0, 4.5, 6.0, 7.5, 9.0],
    "現場_N值": [8, 12, 15, 7, 25, 30],
    "打擊能量比_%": [60, 60, 60, 60, 60, 60]
})

edited_df = st.data_editor(default_data, num_rows="dynamic", use_container_width=True)

if st.button("🚀 執行全深度 N60 修正與繪圖", type="primary"):
    edited_df['修正後_N60'] = edited_df.apply(
        lambda row: calc_spt_n60(row['現場_N值'], row['打擊能量比_%']), axis=1
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

st.divider()

# --- 區塊 2：基礎承載力試算 (多公式切換) ---
st.header("2. 基礎承載力估算")
method_choice = st.radio("選擇承載力理論公式：", ["Meyerhof", "Terzaghi / Vesic (通用)"], horizontal=True)

col_geo, col_found = st.columns(2)
with col_geo:
    st.info("🌱 土壤力學參數")
    cohesion = st.number_input("凝聚力 (c) [kPa]", value=0.0, step=5.0)
    friction_angle = st.number_input("內摩擦角 (ϕ) [度]", value=30.0, step=1.0)
    unit_weight = st.number_input("土壤單位重 (γ) [kN/m³]", value=18.0, step=0.5)

with col_found:
    st.info("🏗️ 基礎設計參數 (假設為連續基礎)")
    depth = st.number_input("基礎埋置深度 (Df) [m]", value=1.5, step=0.1)
    width = st.number_input("基礎寬度 (B) [m]", value=2.0, step=0.1)

if st.button(f"⚖️ 使用 {method_choice} 計算極限承載力 (q_ult)"):
    # 呼叫自行定義的運算核心
    method_param = "Meyerhof" if "Meyerhof" in method_choice else "Terzaghi"
    q_ult, Nc, Nq, Ng = calc_bearing_capacity(cohesion, friction_angle, unit_weight, depth, width, method=method_param)
    
    st.success("計算完成！")
    st.metric(label=f"極限承載力 (q_ult) - {method_param}", value=f"{q_ult:.2f} kPa")
    
    with st.expander("查看推導之承載力係數 (Nc, Nq, Nγ)"):
        st.write(f"- **Nc**: {Nc:.2f}")
        st.write(f"- **Nq**: {Nq:.2f}")
        st.write(f"- **Nγ**: {Ng:.2f}")
