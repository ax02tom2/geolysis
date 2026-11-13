import streamlit as st
import logging
from geolysis_ui import (
    render_module_1,
    render_module_2,
    render_module_3,
    render_module_4,
    render_module_5,
)
logging.basicConfig(level=logging.ERROR)

st.set_page_config(page_title="geolysis 大地工程分析系統", page_icon="🧱", layout="wide")

# 展開區版面修正：避免 expander 內容因內層容器溢出設定而被裁切。
# 所有模組仍可獨立收合／展開；不改動計算欄位或分析流程。
st.markdown("""
<style>
/* Streamlit expander：內容高度依實際內容延伸，不限制在固定高度 */
div[data-testid="stExpander"],
div[data-testid="stExpander"] details,
div[data-testid="stExpander"] details > div,
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
}
/* 避免巢狀 expander 與欄位容器截斷圖表、說明或表單下緣 */
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] > div {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
    min-height: 0 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🧱 geolysis 大地工程分析系統")
st.caption("岩土工程參數初估與分析｜選擇模組後輸入必要資料即可計算。")

# ==============================================================================
# 側邊欄：保留模組快速選擇；預設全部收合
# ==============================================================================
st.sidebar.title("🛠️ 分析模組")
display_mode = st.sidebar.radio(
    "選擇要展開的模組：",
    [
        "全部收合",
        "全部展開",
        "模組一：岩體參數分析",
        "模組二：土壤分類",
        "模組三：SPT 全修正",
        "模組四：容許承載力",
        "模組五：極限承載力"
    ],
    index=0,
    key="analysis_module_display_mode"
)

exp_1 = display_mode in ["全部展開", "模組一：岩體參數分析"]
exp_2 = display_mode in ["全部展開", "模組二：土壤分類"]
exp_3 = display_mode in ["全部展開", "模組三：SPT 全修正"]
exp_4 = display_mode in ["全部展開", "模組四：容許承載力"]
exp_5 = display_mode in ["全部展開", "模組五：極限承載力"]

# 模組 UI 已分離至 geolysis_ui；保留原本單頁與側邊欄收合行為。
render_module_1(expanded=exp_1)
render_module_2(expanded=exp_2)
render_module_3(expanded=exp_3)
render_module_4(expanded=exp_4)
render_module_5(expanded=exp_5)
