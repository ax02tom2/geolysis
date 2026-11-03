import streamlit as st
import io
import pandas as pd
# 匯入所需套件 (需與 requirements.txt 對應)
try:
    from geolysis.bearing_capacity import TerzaghiBearingCapacity
    from geolysis.spt import spt_n_60
except ImportError:
    pass # 避免雲端尚未安裝完成時報錯

try:
    import pygeoda
except ImportError:
    pass

try:
    from docxtpl import DocxTemplate
except ImportError:
    pass


# ==========================================
# 頁面 1：大地參數與承載力推估 (geolysis)
# ==========================================
def page_geolysis():
    st.title("🧱 大地參數與承載力推估工具")
    st.markdown("基於 `geolysis` 套件，提供自動化的大地工程參數換算與基礎承載力評估。")
    
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
                st.warning("雲端環境尚未載入 geolysis，或公式參數需依最新版調整。")
                st.code(str(e))

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
                st.warning("計算過程發生錯誤，請確認套件版本。")
                st.code(str(e))


# ==========================================
# 頁面 2：空間熱區與聚集分析 (pygeoda)
# ==========================================
def page_pygeoda():
    st.title("🗺️ 空間數據熱區分析 (LISA)")
    st.markdown("基於 `pygeoda` 套件，上傳點位或多邊形 Shapefile，自動找出顯著的空間聚集熱區 (如異常降雨集中區)。")
    
    uploaded_geo = st.file_uploader("請上傳 Shapefile 檔案 (目前僅為介面展示，需配合 .shx, .dbf 一同讀取)", type=["shp", "geojson"])
    
    if uploaded_geo is not None:
        st.info(f"已讀取檔案：{uploaded_geo.name}")
        st.markdown("*(註：Streamlit 處理多檔連動的 Shapefile 較複雜，實務上建議上傳 GeoJSON)*")
        
        if st.button("執行局部空間自相關分析 (LISA)"):
            try:
                # 概念性展示，實際需正確讀取地理檔案
                geoda_obj = pygeoda.open(uploaded_geo.name)
                knn_weights = pygeoda.knn_weights(geoda_obj, k=4)
                rainfall_data = geoda_obj.GetRealCol("Rainfall")
                lisa = pygeoda.local_moran(knn_weights, rainfall_data)
                
                st.success("分析完成！")
                st.write("各點位熱區分類結果 (0=不顯著, 1=熱區, 2=冷區)：", lisa.GetClusterIndicators())
            except Exception as e:
                st.warning("分析暫未執行，請確認上傳的檔案格式是否包含必要欄位。")


# ==========================================
# 頁面 3：自動化 Word 報告產出 (docxtpl)
# ==========================================
def page_docxtpl():
    st.title("📄 自動化 Word 報告產出")
    st.markdown("結合你的分析結果，直接將數據填入預先設定好的 Word 模板中，免去人工複製貼上。")
    
    st.subheader("1. 填寫報告變數")
    project_name = st.text_input("專案名稱", "秀巒邊坡穩定性檢核報告")
    report_date = st.date_input("報告日期")
    spt_value = st.text_input("代表性 SPT-N60 值", "15")
    q_ult_value = st.text_input("極限承載力 (kPa)", "250.5")
    conclusion = st.text_area("工程結論與建議", "本區域發現 3 處顯著異常降雨熱區，建議加強傾斜管監測頻率。")
    
    st.subheader("2. 生成與下載")
    if st.button("產出 Word 報告"):
        try:
            # 建立一個空白模板作為測試 (實務上你會讀取 GitHub 裡的 .docx 模板)
            # doc = DocxTemplate("template_report.docx") 
            # 這裡為了讓你直接貼上就能跑，先不強制讀取外部檔案，而是提示用法
            st.info("💡 實務運作邏輯：程式會讀取你放在 GitHub 的 `template_report.docx`，將下方字典填入並匯出。")
            
            context = {
                'project_name': project_name,
                'date': str(report_date),
                'spt_n60': spt_value,
                'q_ult': q_ult_value,
                'conclusion': conclusion
            }
            
            st.json(context)
            st.success("✅ 報告生成成功！(此為展示，實際部署時會出現下方的下載按鈕)")
            
            # 實務上產生下載按鈕的語法 (無伺服器記憶體串流)
            # bio = io.BytesIO()
            # doc.save(bio)
            # st.download_button("📥 下載 Word 報告", data=bio.getvalue(), file_name=f"{project_name}.docx")
            
        except Exception as e:
            st.error("生成失敗，請確認是否有上傳模板檔案。")


# ==========================================
# 主程式：側邊欄導覽邏輯
# ==========================================
def main():
    st.set_page_config(page_title="工程與分析自動化工具集", layout="wide")
    
    st.sidebar.title("🛠️ 工具切換選單")
    # 使用 radio 按鈕作為網頁切換器
    page_selection = st.sidebar.radio(
        "請選擇你要使用的功能：",
        ["1. 大地參數與承載力 (geolysis)", 
         "2. 空間熱區分析 (pygeoda)", 
         "3. 自動化 Word 報告 (docxtpl)"]
    )
    
    st.sidebar.divider()
    st.sidebar.caption("👨‍💻 專為 GitHub & Streamlit Cloud 設計")
    
    # 根據選單執行對應的頁面函數
    if "geolysis" in page_selection:
        page_geolysis()
    elif "pygeoda" in page_selection:
        page_pygeoda()
    elif "docxtpl" in page_selection:
        page_docxtpl()

if __name__ == "__main__":
    main()