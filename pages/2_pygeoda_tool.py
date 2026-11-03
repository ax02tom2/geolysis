import streamlit as st
try:
    import pygeoda
except ImportError:
    pass

st.set_page_config(page_title="空間熱區分析", page_icon="🗺️")
st.title("🗺️ 空間數據熱區分析 (LISA)")
st.markdown("這是一支獨立的程式，專門處理 `pygeoda` 的點位空間自相關與聚集效應分析。")

uploaded_geo = st.file_uploader("請上傳 Shapefile 或 GeoJSON", type=["shp", "geojson"])

if uploaded_geo is not None:
    st.info(f"已讀取檔案：{uploaded_geo.name}")
    
    if st.button("執行局部空間自相關分析 (LISA)"):
        try:
            # 實務上 Streamlit 需要將上傳檔案暫存，這裡展示框架邏輯
            geoda_obj = pygeoda.open(uploaded_geo.name)
            knn_weights = pygeoda.knn_weights(geoda_obj, k=4)
            rainfall_data = geoda_obj.GetRealCol("Rainfall")
            lisa = pygeoda.local_moran(knn_weights, rainfall_data)
            
            st.success("分析完成！")
            st.write("各點位熱區分類結果：", lisa.GetClusterIndicators())
        except Exception as e:
            st.warning("分析暫未執行，請確認上傳檔案是否包含正確的屬性欄位，或補齊 .shx 等附屬檔案。")
            st.code(str(e))