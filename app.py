import streamlit as st

st.set_page_config(page_title="工程自動化首頁", page_icon="🏠", layout="wide")

st.title("🏠 大地工程與空間分析工具集")
st.markdown("---")
st.markdown("""
### 歡迎使用！
請從 **左側邊欄** 選擇你要執行的獨立工具。

**目前已拆分的獨立模組：**
* 🧱 **1_geolysis_tool**: 大地參數與承載力推估
* 🗺️ **2_pygeoda_tool**: 空間數據熱區分析 (LISA)
* 📄 **3_docxtpl_tool**: 自動化 Word 報告產出

*💡 開發者提示：這樣的 `pages/` 資料夾架構讓每支程式碼互相獨立，未來若要新增工具，只要在 `pages/` 底下新增 Python 檔案，左側邊欄就會自動更新，互不干擾。*
""")
