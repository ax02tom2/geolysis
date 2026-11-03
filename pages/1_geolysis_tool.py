import streamlit as st
import pandas as pd
import plotly.express as px

# 嘗試匯入 geolysis，若雲端尚未安裝則顯示友善提示
try:
    from geolysis.bearing_capacity import TerzaghiBearingCapacity
    from geolysis.spt import spt_n_60
    GEOLYSIS_READY = True
except ImportError:
    GEOLYSIS_READY = False

st.set_page_config(page_title="進階承載力推估", page_icon="🧱", layout="wide")
st.title("🧱 進階大地參數與承載力分析系統")
st.markdown("支援連續地層 SPT-N 值批次修正、深度剖面視覺化，以及基礎承載力試算。")

if not GEOLYSIS_READY:
    st.warning("⚠️ 系統正在背景安裝 `geolysis` 套件，請稍候重整網頁。")
    st.stop()

# ==========================================
# 區塊 1：連續地層 SPT-N 值批次處理
# ==========================================
st.header("1. 鑽孔數據輸入與 N 值修正")
st.markdown("請直接在下方表格修改數據，或從 Excel 複製貼上：")

# 預設提供一個簡單的鑽孔數據範例
default_data = pd.DataFrame({
    "深度_m": [1.5, 3.0, 4.5, 6.0, 7.5, 9.0],
    "現場_N值": [8, 12, 15, 7, 25, 30],
    "打擊能量比_%": [60, 60, 60, 60, 60, 60]
})

# 使用 st.data_editor 讓表格具備互動編輯能力
edited_df = st.data_editor(
    default_data, 
    num_rows="dynamic", # 允許使用者動態新增/刪除行
    use_container_width=True,
    key="borehole_editor"
)

# 批次運算按鈕
if st.button("🚀 執行全深度 N60 修正與繪圖", type="primary"):
    try:
        # 使用 geolysis 進行批次修正
        # 注意：實務上 N 值可能會有大於 50 的拒戳情況，此處做基礎防呆
        edited_df['修正後_N60'] = edited_df.apply(
            lambda row: spt_n_60(row['現場_N值'], row['打擊能量比_%']), axis=1
        )
        
        col_table, col_chart = st.columns([1, 1])
        
        with col_table:
            st.subheader("📊 運算結果表")
            st.dataframe(edited_df, use_container_width=True)
            
        with col_chart:
            st.subheader("📉 深度 vs. N60 剖面圖")
            # 使用 Plotly 繪製工程習慣的鑽孔 N 值圖 (深度在 Y 軸且反轉往下)
            fig = px.line(
                edited_df, 
                x="修正後_N60", 
                y="深度_m", 
                markers=True,
                title="SPT-N60 地層剖面"
            )
            fig.update_layout(yaxis=dict(autorange="reversed")) # 深度越深數值越大，Y軸反轉
            fig.update_traces(line_color='#d62728', marker=dict(size=8))
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"運算發生錯誤，請檢查輸入數值是否合理。錯誤訊息：{e}")

st.divider()

# ==========================================
# 區塊 2：Terzaghi 基礎承載力試算
# ==========================================
st.header("2. 基礎承載力估算 (Terzaghi)")
st.markdown("提取代表性土層參數，進行連續基礎之極限承載力估算。")

col_geo, col_found = st.columns(2)

with col_geo:
    st.info("🌱 土壤力學參數")
    cohesion = st.number_input("凝聚力 (c) [kPa]", min_value=0.0, value=0.0, step=5.0)
    friction_angle = st.number_input("內摩擦角 (ϕ) [度]", min_value=0.0, value=30.0, step=1.0)
    unit_weight = st.number_input("土壤單位重 (γ) [kN/m³]", min_value=0.0, value=18.0, step=0.5)

with col_found:
    st.info("🏗️ 基礎設計參數")
    depth = st.number_input("基礎埋置深度 (Df) [m]", min_value=0.0, value=1.5, step=0.1)
    width = st.number_input("基礎寬度 (B) [m]", min_value=0.1, value=2.0, step=0.1)

if st.button("⚖️ 計算極限承載力 (q_ult)"):
    try:
        # 初始化 Terzaghi 承載力物件
        tbc = TerzaghiBearingCapacity(
            cohesion=cohesion, 
            friction_angle=friction_angle, 
            unit_weight=unit_weight
        )
        # 計算結果 (此處為條形/連續基礎)
        q_ult = tbc.ultimate_bearing_capacity(depth=depth, width=width)
        
        st.success("計算完成！")
        st.metric(label="極限承載力 (q_ult)", value=f"{q_ult:.2f} kPa")
        
        # 補充工程師需要的承載力係數資訊 (若 geolysis 支援)
        with st.expander("查看承載力係數 (Nc, Nq, Nγ)"):
            st.write(f"- **Nc**: {tbc.nc:.2f}")
            st.write(f"- **Nq**: {tbc.nq:.2f}")
            st.write(f"- **Nγ**: {tbc.ngamma:.2f}")
            
    except Exception as e:
        st.error(f"承載力計算發生錯誤：{e}")
